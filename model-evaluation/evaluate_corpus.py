#!/usr/bin/env python3
"""Evaluate causal language models on processed text documents."""

from __future__ import annotations

import argparse
import json
import logging
import math
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd
import psutil
import torch
import transformers
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from llm_eval_common import safe_exp

LOGGER = logging.getLogger("corpus_eval")
PROJECT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_DIR.parent
DEFAULT_INPUT_PATH = REPO_ROOT / "crawler" / "data" / "processed"
DEFAULT_OUTPUT_PATH = PROJECT_DIR / "outputs" / "corpus_metrics.jsonl"
DEFAULT_MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Measure per-token cross-entropy, perplexity, bits per UTF-8 byte, "
            "and tokenizer fertility on text files, a directory of text files, CSV, JSON, or JSONL."
        )
    )
    parser.add_argument("--input-path", default=str(DEFAULT_INPUT_PATH))
    parser.add_argument("--output-jsonl", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--text-column", default="text")
    parser.add_argument("--id-column", default="document_id")
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--revision", default="main")
    parser.add_argument("--max-length", type=int, default=2048)
    parser.add_argument("--stride", type=int, default=1024)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda", "mps"), default="auto")
    parser.add_argument("--load-4bit", action="store_true")
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--trust-remote-code", action="store_true")
    parser.add_argument("--save-token-logprobs", action="store_true")
    parser.add_argument("--save-final-probability-vector", action="store_true")
    parser.add_argument("--save-final-logits", action="store_true")
    parser.add_argument("--artifacts-dir", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"), default="INFO")
    return parser.parse_args(argv)


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def load_tabular_rows(
    input_path: Path,
    text_column: str,
    id_column: str,
) -> List[Dict[str, Any]]:
    suffix = input_path.suffix.lower()
    if suffix == ".csv":
        frame = pd.read_csv(input_path)
    elif suffix == ".jsonl":
        frame = pd.read_json(input_path, lines=True)
    elif suffix == ".json":
        frame = pd.read_json(input_path)
    else:
        raise ValueError("Input must be a directory, .txt, .csv, .json, or .jsonl file")

    missing = [column for column in (text_column, id_column) if column not in frame.columns]
    if missing:
        raise ValueError("Missing required column(s): " + ", ".join(sorted(missing)))

    rows: List[Dict[str, Any]] = []
    for row_index, row in frame.iterrows():
        raw_id = row[id_column]
        raw_text = row[text_column]
        sample_id = f"row_{row_index}" if pd.isna(raw_id) else str(raw_id)
        text = "" if pd.isna(raw_text) else str(raw_text)
        rows.append(
            {
                "sample_id": sample_id,
                "source_path": display_path(input_path),
                "text": text,
            }
        )
    return rows


def load_input_rows(
    input_path: Path,
    text_column: str,
    id_column: str,
    limit: int,
) -> List[Dict[str, Any]]:
    if input_path.is_dir():
        text_paths = sorted(path for path in input_path.rglob("*.txt") if path.is_file())
        if not text_paths:
            raise ValueError(f"No .txt files found under {input_path}")
        rows = [
            {
                "sample_id": path.relative_to(input_path).with_suffix("").as_posix(),
                "source_path": display_path(path),
                "text": path.read_text(encoding="utf-8"),
            }
            for path in text_paths
        ]
    elif input_path.is_file() and input_path.suffix.lower() == ".txt":
        rows = [
            {
                "sample_id": input_path.stem,
                "source_path": display_path(input_path),
                "text": input_path.read_text(encoding="utf-8"),
            }
        ]
    elif input_path.is_file():
        rows = load_tabular_rows(input_path, text_column, id_column)
    else:
        raise ValueError(f"Input path does not exist: {input_path}")

    return rows[:limit] if limit > 0 else rows


def resolve_device(requested: str) -> str:
    if requested == "auto":
        if torch.cuda.is_available():
            return "cuda"
        if torch.backends.mps.is_available():
            return "mps"
        return "cpu"
    if requested == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is unavailable")
    if requested == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("MPS was requested but is unavailable")
    return requested


def preferred_dtype(device: str) -> torch.dtype:
    if device == "cuda":
        return torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    if device == "mps":
        return torch.float16
    return torch.float32


def synchronize(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    elif device.type == "mps":
        torch.mps.synchronize()


def load_model_and_tokenizer(args: argparse.Namespace, device: str) -> Tuple[Any, Any, torch.device, str]:
    tokenizer = AutoTokenizer.from_pretrained(
        args.model_id,
        revision=args.revision,
        local_files_only=args.local_files_only,
        trust_remote_code=args.trust_remote_code,
    )
    if tokenizer.pad_token is None and tokenizer.eos_token is not None:
        tokenizer.pad_token = tokenizer.eos_token

    dtype = preferred_dtype(device)
    model_kwargs: Dict[str, Any] = {
        "revision": args.revision,
        "local_files_only": args.local_files_only,
        "trust_remote_code": args.trust_remote_code,
        "low_cpu_mem_usage": True,
    }
    quantization = "none"
    if args.load_4bit:
        if device != "cuda":
            raise RuntimeError("--load-4bit requires CUDA")
        model_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=dtype,
        )
        model_kwargs["device_map"] = "auto"
        quantization = "bitsandbytes-nf4-4bit"
    else:
        model_kwargs["dtype"] = dtype

    model = AutoModelForCausalLM.from_pretrained(args.model_id, **model_kwargs)
    if not args.load_4bit:
        model.to(device)
    model.eval()
    input_device = next(model.parameters()).device
    return tokenizer, model, input_device, quantization


def sanitize_name(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", value).strip("_")
    return cleaned[:120] or "sample"


def top_k_predictions(tokenizer: Any, final_logits: torch.Tensor, top_k: int) -> List[Dict[str, Any]]:
    final_log_probs = torch.log_softmax(final_logits, dim=-1, dtype=torch.float32)
    k = min(top_k, final_log_probs.shape[-1])
    values, indices = torch.topk(final_log_probs, k=k, dim=-1)
    return [
        {
            "rank": rank,
            "token_id": int(token_id),
            "token": tokenizer.convert_ids_to_tokens(int(token_id)),
            "decoded_token": tokenizer.decode([int(token_id)], skip_special_tokens=False),
            "log_probability": float(log_probability),
            "probability": float(math.exp(log_probability)),
        }
        for rank, (token_id, log_probability) in enumerate(
            zip(indices.squeeze(0).detach().cpu().tolist(), values.squeeze(0).detach().cpu().tolist()),
            start=1,
        )
    ]


def score_document(
    token_ids: List[int],
    model: Any,
    input_device: torch.device,
    max_length: int,
    stride: int,
    collect_token_logprobs: bool,
) -> Dict[str, Any]:
    if len(token_ids) < 2:
        raise ValueError("At least two tokens are required for causal scoring")
    if max_length < 2:
        raise ValueError("--max-length must be at least 2")
    if stride < 1 or stride >= max_length:
        raise ValueError("--stride must be at least 1 and smaller than --max-length")

    total_negative_log_likelihood = 0.0
    predicted_token_count = 0
    token_logprobs: List[Dict[str, Any]] = []
    previous_end = 0
    final_logits: Optional[torch.Tensor] = None

    for begin in range(0, len(token_ids), stride):
        end = min(begin + max_length, len(token_ids))
        target_length = end - previous_end
        chunk = torch.tensor([token_ids[begin:end]], dtype=torch.long, device=input_device)
        labels = chunk.clone()
        context_length = chunk.shape[1] - target_length
        if context_length > 0:
            labels[:, :context_length] = -100

        with torch.inference_mode():
            logits = model(input_ids=chunk, use_cache=False, return_dict=True).logits
            shifted_logits = logits[:, :-1, :]
            shifted_labels = labels[:, 1:]
            mask = shifted_labels.ne(-100)
            log_probs = torch.log_softmax(shifted_logits, dim=-1, dtype=torch.float32)
            safe_labels = shifted_labels.masked_fill(~mask, 0)
            selected = log_probs.gather(-1, safe_labels.unsqueeze(-1)).squeeze(-1)[mask]

        count = int(mask.sum().item())
        if count:
            total_negative_log_likelihood += float(-selected.sum().item())
            predicted_token_count += count
            if collect_token_logprobs:
                local_positions = torch.arange(1, chunk.shape[1], device=input_device)[mask.squeeze(0)]
                selected_ids = shifted_labels[mask]
                for local_position, token_id, log_probability in zip(
                    local_positions.detach().cpu().tolist(),
                    selected_ids.detach().cpu().tolist(),
                    selected.detach().cpu().tolist(),
                ):
                    token_logprobs.append(
                        {
                            "position": begin + int(local_position) + 1,
                            "token_id": int(token_id),
                            "log_probability": float(log_probability),
                        }
                    )

        final_logits = logits[:, -1, :]
        previous_end = end
        if end == len(token_ids):
            break

    if predicted_token_count != len(token_ids) - 1:
        raise RuntimeError(
            f"Scored {predicted_token_count} tokens, expected {len(token_ids) - 1}; check window accounting"
        )
    if final_logits is None:
        raise RuntimeError("No model window was evaluated")

    return {
        "total_negative_log_likelihood": total_negative_log_likelihood,
        "predicted_token_count": predicted_token_count,
        "final_logits": final_logits,
        "token_logprobs": token_logprobs,
    }


def write_json(path: Path, payload: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
    return display_path(path)


def save_tensor(path: Path, payload: Dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, path)
    return display_path(path)


def build_error_result(row: Dict[str, Any], model_id: str, message: str) -> Dict[str, Any]:
    return {
        "record_type": "document",
        "sample_id": row["sample_id"],
        "source_path": row["source_path"],
        "model_id": model_id,
        "status": "error",
        "error_message": message,
    }


def evaluate_row(
    row: Dict[str, Any],
    args: argparse.Namespace,
    tokenizer: Any,
    model: Any,
    input_device: torch.device,
    quantization: str,
    artifacts_dir: Path,
) -> Dict[str, Any]:
    text = str(row["text"])
    if not text.strip():
        raise ValueError("Input text is empty")

    token_ids = list(tokenizer(text, add_special_tokens=False, verbose=False)["input_ids"])
    word_count = len(text.split())
    byte_count = len(text.encode("utf-8"))
    if word_count == 0 or byte_count == 0:
        raise ValueError("Input text has no words or UTF-8 bytes")

    ram_before_mb = psutil.Process().memory_info().rss / (1024 * 1024)
    if input_device.type == "cuda":
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats(input_device)
    synchronize(input_device)
    started = time.perf_counter()
    scored = score_document(
        token_ids=token_ids,
        model=model,
        input_device=input_device,
        max_length=args.max_length,
        stride=args.stride,
        collect_token_logprobs=args.save_token_logprobs,
    )
    synchronize(input_device)
    runtime_seconds = time.perf_counter() - started
    ram_after_mb = psutil.Process().memory_info().rss / (1024 * 1024)

    total_nll = float(scored["total_negative_log_likelihood"])
    predicted_count = int(scored["predicted_token_count"])
    cross_entropy = total_nll / predicted_count
    sample_stem = f"{sanitize_name(str(row['sample_id']))}_{sanitize_name(args.model_id.split('/')[-1])}"

    result: Dict[str, Any] = {
        "record_type": "document",
        "sample_id": row["sample_id"],
        "source_path": row["source_path"],
        "model_id": args.model_id,
        "model_revision": args.revision,
        "status": "success",
        "character_count": len(text),
        "word_count": word_count,
        "utf8_byte_count": byte_count,
        "token_count": len(token_ids),
        "predicted_token_count": predicted_count,
        "tokenizer_fertility": len(token_ids) / word_count,
        "total_negative_log_likelihood": total_nll,
        "per_token_cross_entropy_loss": cross_entropy,
        "mean_negative_log_likelihood": cross_entropy,
        "perplexity": safe_exp(cross_entropy),
        "bits_per_byte": total_nll / (math.log(2) * byte_count),
        "max_length": args.max_length,
        "stride": args.stride,
        "window_count": math.ceil(max(1, len(token_ids) - args.max_length) / args.stride) + 1
        if len(token_ids) > args.max_length
        else 1,
        "runtime_seconds": runtime_seconds,
        "scoring_tokens_per_second": predicted_count / runtime_seconds if runtime_seconds > 0 else None,
        "ram_before_mb": ram_before_mb,
        "ram_after_mb": ram_after_mb,
        "peak_cuda_memory_allocated_mb": (
            torch.cuda.max_memory_allocated(input_device) / (1024 * 1024)
            if input_device.type == "cuda"
            else None
        ),
        "device": str(input_device),
        "dtype": str(next(model.parameters()).dtype).replace("torch.", ""),
        "quantization": quantization,
        "torch_version": torch.__version__,
        "transformers_version": transformers.__version__,
        "top_k_next_token_predictions": top_k_predictions(tokenizer, scored["final_logits"], args.top_k),
        "target_token_logprobs_path": None,
        "final_logits_path": None,
        "final_probability_vector_path": None,
        "error_message": None,
    }

    if args.save_token_logprobs:
        result["target_token_logprobs_path"] = write_json(
            artifacts_dir / "target_token_logprobs" / f"{sample_stem}.json",
            scored["token_logprobs"],
        )
    final_logits = scored["final_logits"].detach().cpu().squeeze(0).float()
    if args.save_final_logits:
        result["final_logits_path"] = save_tensor(
            artifacts_dir / "final_logits" / f"{sample_stem}.pt",
            {"sample_id": row["sample_id"], "model_id": args.model_id, "final_logits": final_logits},
        )
    if args.save_final_probability_vector:
        result["final_probability_vector_path"] = save_tensor(
            artifacts_dir / "final_probability_vectors" / f"{sample_stem}.pt",
            {
                "sample_id": row["sample_id"],
                "model_id": args.model_id,
                "final_probabilities": torch.softmax(final_logits, dim=-1),
            },
        )
    return result


def build_summary(results: Sequence[Dict[str, Any]], args: argparse.Namespace) -> Dict[str, Any]:
    successful = [row for row in results if row.get("status") == "success"]
    if not successful:
        raise ValueError("No documents were evaluated successfully")
    total_nll = sum(float(row["total_negative_log_likelihood"]) for row in successful)
    predicted_tokens = sum(int(row["predicted_token_count"]) for row in successful)
    token_count = sum(int(row["token_count"]) for row in successful)
    word_count = sum(int(row["word_count"]) for row in successful)
    byte_count = sum(int(row["utf8_byte_count"]) for row in successful)
    cross_entropy = total_nll / predicted_tokens
    return {
        "record_type": "corpus_summary",
        "model_id": args.model_id,
        "model_revision": args.revision,
        "input_path": display_path(Path(args.input_path)),
        "document_count": len(successful),
        "error_count": len(results) - len(successful),
        "word_count": word_count,
        "utf8_byte_count": byte_count,
        "token_count": token_count,
        "predicted_token_count": predicted_tokens,
        "total_negative_log_likelihood": total_nll,
        "per_token_cross_entropy_loss": cross_entropy,
        "mean_negative_log_likelihood": cross_entropy,
        "perplexity": safe_exp(cross_entropy),
        "bits_per_byte": total_nll / (math.log(2) * byte_count),
        "tokenizer_fertility": token_count / word_count,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(asctime)s | %(levelname)s | %(message)s")
    input_path = Path(args.input_path).expanduser().resolve()
    output_path = Path(args.output_jsonl).expanduser().resolve()
    summary_path = output_path.with_name(f"{output_path.stem}_summary.json")
    artifacts_dir = (
        Path(args.artifacts_dir).expanduser().resolve()
        if args.artifacts_dir
        else output_path.parent / f"{output_path.stem}_artifacts"
    )

    try:
        rows = load_input_rows(input_path, args.text_column, args.id_column, args.limit)
        if output_path.exists() and not args.overwrite:
            raise FileExistsError(f"Output exists; pass --overwrite to replace it: {output_path}")
        if summary_path.exists() and not args.overwrite:
            raise FileExistsError(f"Summary exists; pass --overwrite to replace it: {summary_path}")
        device = resolve_device(args.device)
    except Exception as exc:
        LOGGER.error("Preflight failed: %s", exc)
        return 1

    LOGGER.info("Loaded %s document(s) from %s", len(rows), input_path)
    LOGGER.info("Loading %s on %s", args.model_id, device)
    try:
        tokenizer, model, input_device, quantization = load_model_and_tokenizer(args, device)
    except Exception as exc:
        LOGGER.error("Model/tokenizer load failed: %s", exc)
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    results: List[Dict[str, Any]] = []
    with output_path.open("w", encoding="utf-8") as output_handle:
        for row in rows:
            try:
                result = evaluate_row(row, args, tokenizer, model, input_device, quantization, artifacts_dir)
            except Exception as exc:
                LOGGER.exception("Document %s failed", row["sample_id"])
                result = build_error_result(row, args.model_id, str(exc))
            results.append(result)
            output_handle.write(json.dumps(result, ensure_ascii=False, allow_nan=False) + "\n")

    try:
        summary = build_summary(results, args)
        write_json(summary_path, summary)
    except Exception as exc:
        LOGGER.error("Summary failed: %s", exc)
        return 2

    LOGGER.info("Wrote document metrics to %s", output_path)
    LOGGER.info("Wrote corpus metrics to %s", summary_path)
    return 2 if any(row["status"] != "success" for row in results) else 0


if __name__ == "__main__":
    sys.exit(main())
