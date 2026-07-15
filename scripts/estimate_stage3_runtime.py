#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import random
import time
from pathlib import Path
from statistics import mean
from typing import Any

import numpy as np

from dominican_llm_scraper.core.processor.deduplication.stage_01_exact import run_exact_deduplication
from dominican_llm_scraper.core.processor.deduplication.stage_02_near_duplicate import run_near_duplicate_deduplication
from dominican_llm_scraper.core.processor.deduplication.stage_03_semantic import (
    DEFAULT_MODEL_NAME,
    DEFAULT_NCENTROIDS,
    DEFAULT_SEED,
    OllamaEmbeddingProvider,
    _chunk_tokens,
    _kmeans_cluster,
    _load_jsonl,
    _normalize_text,
    _resolve_faiss_gpu_mode,
    _tokenize,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Estimate Stage 3 runtime from deterministic sample")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--sample-size", type=int, default=250)
    parser.add_argument("--model-name", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--chunk-token-count", type=int, default=200)
    parser.add_argument("--min-token-count", type=int, default=50)
    parser.add_argument("--ncentroids", type=int, default=DEFAULT_NCENTROIDS)
    parser.add_argument("--kmeans-niter", type=int, default=30)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--use-gpu", choices=["auto", "true", "false"], default="auto")
    parser.add_argument("--output-json", type=Path, default=None)
    return parser.parse_args()


def _parse_use_gpu(mode: str) -> bool | None:
    if mode == "auto":
        return None
    return mode == "true"


def _select_stage2_survivors(input_dir: Path) -> list[str]:
    stage_01_rows = run_exact_deduplication(input_dir)["rows"]
    stage_02_rows = run_near_duplicate_deduplication(input_dir, stage_01_rows)["rows"]
    stage_01_duplicates = {row["doc_id"] for row in stage_01_rows if row.get("is_duplicate", False)}
    survivors = [
        row["doc_id"]
        for row in stage_02_rows
        if not row.get("is_duplicate", False) and row["doc_id"] not in stage_01_duplicates
    ]
    return sorted(survivors)


def _estimate(input_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    metadata_rows = _load_jsonl(input_dir / "metadata_plaintext.jsonl")
    metadata_by_doc_id = {row["doc_id"]: row for row in metadata_rows}

    all_survivors = _select_stage2_survivors(input_dir)
    full_count = len(all_survivors)
    sample_size = min(args.sample_size, full_count)

    random_gen = random.Random(args.seed)
    sample_doc_ids = sorted(random_gen.sample(all_survivors, sample_size)) if sample_size > 0 else []

    gpu_mode = _resolve_faiss_gpu_mode(_parse_use_gpu(args.use_gpu))

    provider = OllamaEmbeddingProvider(model_name=args.model_name)
    preflight = provider.preflight(failfast_ollama=True, failfast_model=True)

    embeddings_by_doc: list[np.ndarray] = []
    embedding_seconds: list[float] = []
    token_counts: list[int] = []

    for doc_id in sample_doc_ids:
        row = metadata_by_doc_id.get(doc_id)
        if row is None:
            continue
        text_path = input_dir / row["filename"]
        tokens = _tokenize(_normalize_text(text_path.read_text(encoding="utf-8")))
        token_counts.append(len(tokens))
        if len(tokens) < args.min_token_count:
            continue

        chunks = _chunk_tokens(tokens, args.chunk_token_count)
        t0 = time.perf_counter()
        chunk_embeddings = provider.embed_texts(chunks)
        t1 = time.perf_counter()
        embedding_seconds.append(t1 - t0)

        vec = np.asarray(chunk_embeddings, dtype=np.float32).mean(axis=0)
        embeddings_by_doc.append(vec)

    if embeddings_by_doc:
        vectors = np.vstack(embeddings_by_doc).astype(np.float32)
    else:
        vectors = np.empty((0, 0), dtype=np.float32)

    t0 = time.perf_counter()
    if vectors.shape[0] > 0:
        _kmeans_cluster(
            vectors,
            ncentroids=args.ncentroids,
            kmeans_niter=args.kmeans_niter,
            seed=args.seed,
            use_gpu=bool(gpu_mode["gpu_effective"]),
        )
    t1 = time.perf_counter()
    clustering_seconds = t1 - t0

    # Approximate similarity phase as O(N^2) with one dense matrix multiply in normalized space.
    t0 = time.perf_counter()
    if vectors.shape[0] > 0:
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0.0] = 1.0
        vectors_norm = vectors / norms
        _ = vectors_norm @ vectors_norm.T
    t1 = time.perf_counter()
    similarity_seconds = t1 - t0

    effective_docs = max(1, len(embeddings_by_doc))
    embed_per_doc = mean(embedding_seconds) if embedding_seconds else 0.0

    full_embed_seconds = embed_per_doc * full_count
    sample_docs_float = float(effective_docs)
    cluster_scale = (full_count / sample_docs_float) if sample_docs_float > 0 else 1.0
    pair_scale = (full_count / sample_docs_float) ** 2 if sample_docs_float > 0 else 1.0

    full_cluster_seconds = clustering_seconds * cluster_scale
    full_similarity_seconds = similarity_seconds * pair_scale
    expected_total = full_embed_seconds + full_cluster_seconds + full_similarity_seconds

    estimate = {
        "input_dir": str(input_dir),
        "model_name": args.model_name,
        "sample_size_requested": args.sample_size,
        "sample_size_effective": sample_size,
        "effective_embedded_docs": effective_docs,
        "full_stage2_survivors": full_count,
        "token_count_avg": mean(token_counts) if token_counts else 0,
        "embedding_seconds_per_doc": embed_per_doc,
        "sample_embedding_seconds": sum(embedding_seconds),
        "sample_clustering_seconds": clustering_seconds,
        "sample_similarity_seconds": similarity_seconds,
        "estimated_full_embedding_seconds": full_embed_seconds,
        "estimated_full_clustering_seconds": full_cluster_seconds,
        "estimated_full_similarity_seconds": full_similarity_seconds,
        "estimated_total_seconds_expected": expected_total,
        "estimated_total_seconds_optimistic": expected_total * 0.8,
        "estimated_total_seconds_conservative": expected_total * 1.3,
        "estimated_total_minutes_expected": expected_total / 60.0,
        "estimated_total_hours_expected": expected_total / 3600.0,
        "recommended_ncentroids": max(8, int(math.sqrt(max(full_count, 1)))) if full_count else args.ncentroids,
        "faiss_mode": gpu_mode["faiss_mode"],
        "gpu_requested": gpu_mode["gpu_requested"],
        "gpu_effective": gpu_mode["gpu_effective"],
        "faiss_gpu_available": gpu_mode["faiss_gpu_available"],
        "faiss_gpu_count": gpu_mode["faiss_gpu_count"],
        "preflight": preflight,
        "sample_doc_ids": sample_doc_ids,
    }
    return estimate


def main() -> int:
    args = parse_args()
    estimate = _estimate(args.input_dir, args)

    output_path = args.output_json or (args.input_dir / "stage3_time_estimate.json")
    output_path.write_text(json.dumps(estimate, indent=2, ensure_ascii=False), encoding="utf-8")

    print("[estimate] output:", output_path)
    print("[estimate] full survivors:", estimate["full_stage2_survivors"])
    print("[estimate] expected seconds:", round(float(estimate["estimated_total_seconds_expected"]), 2))
    print("[estimate] faiss mode:", estimate["faiss_mode"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
