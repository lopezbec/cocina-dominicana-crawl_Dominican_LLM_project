#!/usr/bin/env python3
"""Generate deterministic continuations for processed documents through Ollama."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import requests

from llm_eval_common import append_jsonl, ns_to_seconds, repo_root, reset_output, safe_rate, validate_output

LOGGER = logging.getLogger("ollama_eval")
DEFAULT_INPUT_PATH = repo_root() / "crawler" / "data" / "processed"
DEFAULT_OUTPUT_PATH = repo_root() / "model-evaluation" / "outputs" / "ollama_runtime_results.jsonl"


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run deterministic generation and runtime measurements on processed text documents."
    )
    parser.add_argument("--base-url", default=os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434"))
    parser.add_argument("--model", default="qwen3:4b")
    parser.add_argument("--input-path", default=str(DEFAULT_INPUT_PATH))
    parser.add_argument("--output-jsonl", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--max-new-tokens", type=int, default=64)
    parser.add_argument("--max-prompt-characters", type=int, default=0)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"), default="INFO")
    return parser.parse_args(argv)


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(repo_root()).as_posix()
    except ValueError:
        return str(resolved)


def load_documents(input_path: Path, limit: int) -> List[Dict[str, str]]:
    if input_path.is_dir():
        paths = sorted(path for path in input_path.rglob("*.txt") if path.is_file())
    elif input_path.is_file() and input_path.suffix.lower() == ".txt":
        paths = [input_path]
    else:
        raise ValueError(f"Input must be an existing .txt file or directory: {input_path}")
    if not paths:
        raise ValueError(f"No .txt files found under {input_path}")
    if limit > 0:
        paths = paths[:limit]
    return [
        {
            "sample_id": path.relative_to(input_path).with_suffix("").as_posix()
            if input_path.is_dir()
            else path.stem,
            "source_path": display_path(path),
            "text": path.read_text(encoding="utf-8"),
        }
        for path in paths
    ]


def parse_response(sample: Dict[str, str], model: str, payload: Dict[str, Any], wall: float) -> Dict[str, Any]:
    required = (
        "response",
        "done",
        "total_duration",
        "load_duration",
        "prompt_eval_count",
        "prompt_eval_duration",
        "eval_count",
        "eval_duration",
    )
    missing = [field for field in required if field not in payload]
    if missing:
        raise ValueError("Ollama response missing fields: " + ", ".join(missing))
    if not isinstance(payload["response"], str):
        raise ValueError("Ollama response must be text")
    total = ns_to_seconds(payload["total_duration"])
    load = ns_to_seconds(payload["load_duration"])
    prompt_duration = ns_to_seconds(payload["prompt_eval_duration"])
    eval_duration = ns_to_seconds(payload["eval_duration"])
    return {
        "model": model,
        "sample_id": sample["sample_id"],
        "source_path": sample["source_path"],
        "task_type": "document_continuation",
        "status": "success",
        "duration_unit": "nanoseconds",
        "total_duration": payload["total_duration"],
        "load_duration": payload["load_duration"],
        "prompt_eval_count": payload["prompt_eval_count"],
        "prompt_eval_duration": payload["prompt_eval_duration"],
        "eval_count": payload["eval_count"],
        "eval_duration": payload["eval_duration"],
        "total_duration_seconds": total,
        "load_duration_seconds": load,
        "prompt_eval_duration_seconds": prompt_duration,
        "eval_duration_seconds": eval_duration,
        "tokens_per_second": safe_rate(payload["eval_count"], eval_duration),
        "prompt_tokens_per_second": safe_rate(payload["prompt_eval_count"], prompt_duration),
        "wall_clock_seconds": wall,
        "response": payload["response"],
        "done": payload["done"],
        "done_reason": payload.get("done_reason"),
        "error_message": None,
    }


def error_row(sample: Dict[str, str], model: str, message: str, wall: Optional[float] = None) -> Dict[str, Any]:
    return {
        "model": model,
        "sample_id": sample["sample_id"],
        "source_path": sample["source_path"],
        "task_type": "document_continuation",
        "status": "error",
        "total_duration_seconds": None,
        "load_duration_seconds": None,
        "prompt_eval_duration_seconds": None,
        "eval_duration_seconds": None,
        "tokens_per_second": None,
        "prompt_tokens_per_second": None,
        "wall_clock_seconds": wall,
        "response": None,
        "done": None,
        "done_reason": None,
        "error_message": message,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(asctime)s | %(levelname)s | %(message)s")
    try:
        samples = load_documents(Path(args.input_path).expanduser().resolve(), args.limit)
        output = Path(args.output_jsonl).expanduser().resolve()
        validate_output(output, args.overwrite)
    except Exception as exc:
        LOGGER.error("Preflight failed: %s", exc)
        return 1

    try:
        response = requests.get(args.base_url.rstrip("/") + "/api/tags", timeout=args.timeout)
        response.raise_for_status()
        tags = response.json()
        names = {item.get("name") for item in tags.get("models", []) if isinstance(item, dict)}
        if args.model not in names:
            raise RuntimeError(f"Requested Ollama model is not installed: {args.model}")
    except Exception as exc:
        message = f"Ollama preflight failed: {exc}"
        LOGGER.error("%s", message)
        reset_output(output)
        for sample in samples:
            append_jsonl(output, error_row(sample, args.model, message))
        return 1

    reset_output(output)
    errors = 0
    for sample in samples:
        prompt = sample["text"]
        if args.max_prompt_characters > 0:
            prompt = prompt[: args.max_prompt_characters]
        started = time.perf_counter()
        try:
            response = requests.post(
                args.base_url.rstrip("/") + "/api/generate",
                json={
                    "model": args.model,
                    "prompt": prompt,
                    "stream": False,
                    "think": False,
                    "options": {
                        "temperature": 0,
                        "seed": args.seed,
                        "num_predict": args.max_new_tokens,
                    },
                },
                timeout=args.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("Ollama response JSON must be an object")
            row = parse_response(sample, args.model, payload, time.perf_counter() - started)
        except Exception as exc:
            LOGGER.error("Sample %s failed: %s", sample["sample_id"], exc)
            row = error_row(sample, args.model, str(exc), time.perf_counter() - started)
            errors += 1
        append_jsonl(output, row)
    return 2 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
