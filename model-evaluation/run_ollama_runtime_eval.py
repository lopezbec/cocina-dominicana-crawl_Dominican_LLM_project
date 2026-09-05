#!/usr/bin/env python3
"""Generate deterministic, chunk-level continuations through Ollama."""

from __future__ import annotations

import argparse
import hashlib
import logging
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import requests
from transformers import AutoTokenizer

from llm_eval_common import append_jsonl, ns_to_seconds, repo_root, reset_output, safe_rate, validate_output

LOGGER = logging.getLogger("ollama_eval")
DEFAULT_INPUT_PATH = repo_root() / "processor" / "data" / "processed"
DEFAULT_OUTPUT_PATH = repo_root() / "model-evaluation" / "outputs" / "ollama_runtime_results.jsonl"
DEFAULT_CONTEXT_UTILIZATION = 0.80
DEFAULT_TOKENIZER_ID = "Qwen/Qwen3-4B"


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run deterministic, chunk-level generation and runtime measurements on processed text documents."
    )
    parser.add_argument("--base-url", default=os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434"))
    parser.add_argument("--model", default="qwen3:4b")
    parser.add_argument(
        "--tokenizer-id",
        default=DEFAULT_TOKENIZER_ID,
        help="Hugging Face tokenizer corresponding exactly to the Ollama model.",
    )
    parser.add_argument("--input-path", default=str(DEFAULT_INPUT_PATH))
    parser.add_argument("--output-jsonl", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--max-new-tokens", type=int, default=64)
    parser.add_argument("--context-utilization", type=float, default=DEFAULT_CONTEXT_UTILIZATION)
    parser.add_argument(
        "--special-token-reserve",
        type=int,
        default=32,
        help="Prompt-token safety reserve for BOS, templates, and tokenizer-boundary differences.",
    )
    parser.add_argument(
        "--stride",
        type=int,
        default=0,
        help="Chunk advance in tokens; 0 uses half of the computed prompt budget.",
    )
    parser.add_argument("--max-prompt-characters", type=int, default=0)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--trust-remote-code", action="store_true")
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


def extract_ollama_context(payload: Dict[str, Any]) -> Dict[str, Any]:
    model_info = payload.get("model_info")
    if not isinstance(model_info, dict):
        raise ValueError("Ollama /api/show response does not contain model_info")

    candidates = []
    for key, raw_value in model_info.items():
        normalized_key = str(key).lower()
        if not normalized_key.endswith("context_length"):
            continue
        try:
            value = int(raw_value)
        except (TypeError, ValueError, OverflowError):
            continue
        if value >= 2:
            candidates.append({"source": f"model_info.{key}", "tokens": value})

    if not candidates:
        raise ValueError("Could not find a *.context_length value in Ollama /api/show model_info")
    return {
        "maximum_context_length": min(candidate["tokens"] for candidate in candidates),
        "context_length_candidates": candidates,
    }


def resolve_context_policy(
    maximum_context_length: int,
    context_utilization: float,
    max_new_tokens: int,
    special_token_reserve: int,
    requested_stride: int,
) -> Dict[str, Any]:
    if not 0 < context_utilization <= 1:
        raise ValueError("--context-utilization must be greater than 0 and at most 1")
    if max_new_tokens < 1:
        raise ValueError("--max-new-tokens must be at least 1")
    if special_token_reserve < 0:
        raise ValueError("--special-token-reserve cannot be negative")

    effective_context_length = math.floor(maximum_context_length * context_utilization)
    prompt_token_budget = effective_context_length - max_new_tokens - special_token_reserve
    if prompt_token_budget < 2:
        raise ValueError("The 80% context allocation is too small after reserving generation and special tokens")

    stride = requested_stride or max(1, prompt_token_budget // 2)
    if stride < 1 or stride >= prompt_token_budget:
        raise ValueError("--stride must be at least 1 and smaller than the prompt token budget")

    return {
        "maximum_context_length": maximum_context_length,
        "context_utilization": context_utilization,
        "effective_context_length": effective_context_length,
        "prompt_token_budget": prompt_token_budget,
        "special_token_reserve": special_token_reserve,
        "max_new_tokens": max_new_tokens,
        "stride": stride,
    }


def build_text_chunks(text: str, tokenizer: Any, prompt_token_budget: int, stride: int) -> List[Dict[str, Any]]:
    if not text:
        raise ValueError("Input text is empty")
    encoded = tokenizer(
        text,
        add_special_tokens=False,
        return_offsets_mapping=True,
        verbose=False,
    )
    token_ids = list(encoded["input_ids"])
    offsets = list(encoded["offset_mapping"])
    if not token_ids:
        raise ValueError("Input text produced no tokens")
    if len(token_ids) != len(offsets):
        raise ValueError("Tokenizer returned mismatched input_ids and offset_mapping lengths")

    chunks: List[Dict[str, Any]] = []
    for chunk_index, token_start in enumerate(range(0, len(token_ids), stride), start=1):
        token_end = min(token_start + prompt_token_budget, len(token_ids))
        character_start = 0 if token_start == 0 else int(offsets[token_start][0])
        character_end = len(text) if token_end == len(token_ids) else int(offsets[token_end - 1][1])
        prompt = text[character_start:character_end]
        chunks.append(
            {
                "chunk_index": chunk_index,
                "token_start_index": token_start,
                "token_end_index_exclusive": token_end,
                "planned_prompt_token_count": token_end - token_start,
                "character_start_index": character_start,
                "character_end_index_exclusive": character_end,
                "character_count": len(prompt),
                "text_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                "_prompt": prompt,
            }
        )
        if token_end == len(token_ids):
            break
    return chunks


def parse_chunk_response(
    chunk: Dict[str, Any],
    model: str,
    payload: Dict[str, Any],
    wall_clock_seconds: float,
    context_policy: Dict[str, Any],
) -> Dict[str, Any]:
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

    prompt_eval_count = int(payload["prompt_eval_count"])
    if prompt_eval_count + context_policy["max_new_tokens"] > context_policy["effective_context_length"]:
        raise ValueError(
            "Ollama prompt plus reserved generation exceeds the effective 80% context allocation: "
            f"{prompt_eval_count} + {context_policy['max_new_tokens']} > "
            f"{context_policy['effective_context_length']}"
        )

    total = ns_to_seconds(payload["total_duration"])
    load = ns_to_seconds(payload["load_duration"])
    prompt_duration = ns_to_seconds(payload["prompt_eval_duration"])
    eval_duration = ns_to_seconds(payload["eval_duration"])
    public_chunk = {key: value for key, value in chunk.items() if not key.startswith("_")}
    return {
        **public_chunk,
        "model": model,
        "status": "success",
        "duration_unit": "nanoseconds",
        "total_duration": int(payload["total_duration"]),
        "load_duration": int(payload["load_duration"]),
        "prompt_eval_duration": int(payload["prompt_eval_duration"]),
        "eval_duration": int(payload["eval_duration"]),
        "prompt_eval_count": prompt_eval_count,
        "eval_count": int(payload["eval_count"]),
        "generated_token_count": int(payload["eval_count"]),
        "total_duration_seconds": total,
        "load_duration_seconds": load,
        "prompt_eval_duration_seconds": prompt_duration,
        "eval_duration_seconds": eval_duration,
        "generation_duration_seconds": eval_duration,
        "prompt_tokens_per_second": safe_rate(prompt_eval_count, prompt_duration),
        "tokens_per_second": safe_rate(payload["eval_count"], eval_duration),
        "generation_tokens_per_second": safe_rate(payload["eval_count"], eval_duration),
        "wall_clock_seconds": wall_clock_seconds,
        "response": payload["response"],
        "done": payload["done"],
        "done_reason": payload.get("done_reason"),
        "error_message": None,
    }


def chunk_error(chunk: Dict[str, Any], message: str, wall_clock_seconds: Optional[float] = None) -> Dict[str, Any]:
    public_chunk = {key: value for key, value in chunk.items() if not key.startswith("_")}
    return {
        **public_chunk,
        "status": "error",
        "duration_unit": "nanoseconds",
        "total_duration": None,
        "load_duration": None,
        "prompt_eval_duration": None,
        "eval_duration": None,
        "prompt_eval_count": None,
        "eval_count": None,
        "generated_token_count": None,
        "total_duration_seconds": None,
        "load_duration_seconds": None,
        "prompt_eval_duration_seconds": None,
        "eval_duration_seconds": None,
        "generation_duration_seconds": None,
        "prompt_tokens_per_second": None,
        "tokens_per_second": None,
        "generation_tokens_per_second": None,
        "wall_clock_seconds": wall_clock_seconds,
        "response": None,
        "done": None,
        "done_reason": None,
        "error_message": message,
    }


def aggregate_file_result(
    sample: Dict[str, str],
    args: argparse.Namespace,
    context_policy: Dict[str, Any],
    context_candidates: List[Dict[str, Any]],
    chunks: List[Dict[str, Any]],
    source_was_truncated: bool,
    wall_clock_seconds: float,
) -> Dict[str, Any]:
    successful = [chunk for chunk in chunks if chunk["status"] == "success"]
    error_count = len(chunks) - len(successful)
    prompt_tokens = sum(int(chunk["prompt_eval_count"]) for chunk in successful)
    generated_tokens = sum(int(chunk["generated_token_count"]) for chunk in successful)
    total_seconds = sum(float(chunk["total_duration_seconds"]) for chunk in successful)
    load_seconds = sum(float(chunk["load_duration_seconds"]) for chunk in successful)
    prompt_seconds = sum(float(chunk["prompt_eval_duration_seconds"]) for chunk in successful)
    generation_seconds = sum(float(chunk["generation_duration_seconds"]) for chunk in successful)
    if not successful:
        status = "error"
    elif error_count:
        status = "partial_error"
    else:
        status = "success"

    return {
        "record_type": "document",
        "backend": "ollama",
        "model": args.model,
        "tokenizer_id": args.tokenizer_id,
        "sample_id": sample["sample_id"],
        "source_path": sample["source_path"],
        "task_type": "document_continuation",
        "status": status,
        **context_policy,
        "context_length_candidates": context_candidates,
        "source_was_truncated_by_character_limit": source_was_truncated,
        "window_count": len(chunks),
        "successful_chunk_count": len(successful),
        "error_chunk_count": error_count,
        "prompt_eval_count": prompt_tokens,
        "eval_count": generated_tokens,
        "generated_token_count": generated_tokens,
        "total_duration_seconds": total_seconds,
        "load_duration_seconds": load_seconds,
        "prompt_eval_duration_seconds": prompt_seconds,
        "eval_duration_seconds": generation_seconds,
        "generation_duration_seconds": generation_seconds,
        "prompt_tokens_per_second": safe_rate(prompt_tokens, prompt_seconds),
        "tokens_per_second": safe_rate(generated_tokens, generation_seconds),
        "generation_tokens_per_second": safe_rate(generated_tokens, generation_seconds),
        "wall_clock_seconds": wall_clock_seconds,
        "chunks": chunks,
        "error_message": "; ".join(
            str(chunk["error_message"]) for chunk in chunks if chunk.get("error_message")
        )
        or None,
    }


def preflight_error_row(sample: Dict[str, str], model: str, message: str) -> Dict[str, Any]:
    return {
        "record_type": "document",
        "backend": "ollama",
        "model": model,
        "sample_id": sample["sample_id"],
        "source_path": sample["source_path"],
        "task_type": "document_continuation",
        "status": "error",
        "window_count": 0,
        "chunks": [],
        "error_message": message,
    }


def evaluate_document(
    sample: Dict[str, str],
    args: argparse.Namespace,
    tokenizer: Any,
    context_policy: Dict[str, Any],
    context_candidates: List[Dict[str, Any]],
) -> Dict[str, Any]:
    original_text = sample["text"]
    text = original_text
    if args.max_prompt_characters > 0:
        text = text[: args.max_prompt_characters]
    source_was_truncated = len(text) != len(original_text)
    plans = build_text_chunks(text, tokenizer, context_policy["prompt_token_budget"], context_policy["stride"])

    started_document = time.perf_counter()
    results: List[Dict[str, Any]] = []
    for plan in plans:
        started_chunk = time.perf_counter()
        try:
            response = requests.post(
                args.base_url.rstrip("/") + "/api/generate",
                json={
                    "model": args.model,
                    "prompt": plan["_prompt"],
                    "stream": False,
                    "think": False,
                    "options": {
                        "temperature": 0,
                        "seed": args.seed,
                        "num_ctx": context_policy["effective_context_length"],
                        "num_predict": args.max_new_tokens,
                    },
                },
                timeout=args.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("Ollama response JSON must be an object")
            result = parse_chunk_response(
                plan,
                args.model,
                payload,
                time.perf_counter() - started_chunk,
                context_policy,
            )
        except Exception as exc:
            LOGGER.error("Sample %s chunk %s failed: %s", sample["sample_id"], plan["chunk_index"], exc)
            result = chunk_error(plan, str(exc), time.perf_counter() - started_chunk)
        results.append(result)

    return aggregate_file_result(
        sample,
        args,
        context_policy,
        context_candidates,
        results,
        source_was_truncated,
        time.perf_counter() - started_document,
    )


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

        show_response = requests.post(
            args.base_url.rstrip("/") + "/api/show",
            json={"model": args.model},
            timeout=args.timeout,
        )
        show_response.raise_for_status()
        show_payload = show_response.json()
        if not isinstance(show_payload, dict):
            raise ValueError("Ollama /api/show response JSON must be an object")
        context = extract_ollama_context(show_payload)
        context_policy = resolve_context_policy(
            maximum_context_length=context["maximum_context_length"],
            context_utilization=args.context_utilization,
            max_new_tokens=args.max_new_tokens,
            special_token_reserve=args.special_token_reserve,
            requested_stride=args.stride,
        )
        tokenizer = AutoTokenizer.from_pretrained(
            args.tokenizer_id,
            local_files_only=args.local_files_only,
            trust_remote_code=args.trust_remote_code,
            use_fast=True,
        )
        if not getattr(tokenizer, "is_fast", False):
            raise ValueError("Ollama chunk planning requires a fast tokenizer with offset mappings")
    except Exception as exc:
        message = f"Ollama/tokenizer preflight failed: {exc}"
        LOGGER.error("%s", message)
        reset_output(output)
        for sample in samples:
            append_jsonl(output, preflight_error_row(sample, args.model, message))
        return 1

    LOGGER.info(
        "Using %.0f%% of Ollama model context: %s/%s tokens; prompt budget=%s; stride=%s",
        context_policy["context_utilization"] * 100,
        context_policy["effective_context_length"],
        context_policy["maximum_context_length"],
        context_policy["prompt_token_budget"],
        context_policy["stride"],
    )
    reset_output(output)
    errors = 0
    for sample in samples:
        row = evaluate_document(sample, args, tokenizer, context_policy, context["context_length_candidates"])
        if row["status"] != "success":
            errors += 1
        append_jsonl(output, row)
    return 2 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
