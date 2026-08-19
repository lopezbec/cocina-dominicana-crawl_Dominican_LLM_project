#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from dominican_llm_scraper.core.processor.deduplication.stage_01_exact import run_exact_deduplication
from dominican_llm_scraper.core.processor.deduplication.stage_02_near_duplicate import run_near_duplicate_deduplication
from dominican_llm_scraper.core.processor.deduplication.stage_03_semantic import run_semantic_deduplication


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FIXTURE = ROOT / "data" / "synthetic_stage3"
DEFAULT_INPUT_PROCESSED = DEFAULT_FIXTURE / "processed"
DEFAULT_OUTPUT = DEFAULT_FIXTURE / "output"
DEFAULT_MANIFEST = DEFAULT_FIXTURE / "manifest.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Stage 1/2/3 dedup on persistent synthetic fixture")
    parser.add_argument("--input-processed", type=Path, default=DEFAULT_INPUT_PROCESSED)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--epsilon", type=float, default=None)
    parser.add_argument("--ncentroids", type=int, default=2)
    parser.add_argument("--kmeans-niter", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-token-count", type=int, default=20)
    parser.add_argument("--chunk-token-count", type=int, default=200)
    parser.add_argument("--near-threshold", type=float, default=0.95)
    parser.add_argument("--reset-output", action="store_true")
    return parser.parse_args()


def _load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _copy_processed_fixture(input_processed: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for src in sorted(input_processed.glob("*.txt")):
        shutil.copy2(src, output_dir / src.name)
    shutil.copy2(input_processed / "metadata_plaintext.jsonl", output_dir / "metadata_plaintext.jsonl")


def main() -> int:
    args = parse_args()
    manifest = _load_manifest(args.manifest)
    epsilon = args.epsilon if args.epsilon is not None else float(manifest.get("default_epsilon", 0.9))

    if args.reset_output and args.output_dir.exists():
        shutil.rmtree(args.output_dir)

    _copy_processed_fixture(args.input_processed, args.output_dir)

    print(f"[synthetic] input={args.input_processed}")
    print(f"[synthetic] output={args.output_dir}")
    print(f"[synthetic] epsilon={epsilon}")

    stage1_result = run_exact_deduplication(args.output_dir)
    stage2_result = run_near_duplicate_deduplication(
        args.output_dir, stage1_result["rows"], threshold=args.near_threshold
    )
    stage3_result = run_semantic_deduplication(
        args.output_dir,
        stage1_result["rows"],
        stage2_result["rows"],
        eps_list=[epsilon],
        ncentroids=args.ncentroids,
        kmeans_niter=args.kmeans_niter,
        seed=args.seed,
        min_token_count=args.min_token_count,
        chunk_token_count=args.chunk_token_count,
        max_docs_for_stage3=50,
    )

    run_meta = {
        "stage1": stage1_result["summary"],
        "stage2": stage2_result["summary"],
        "stage3": stage3_result["summary"],
        "epsilon": epsilon,
        "manifest": str(args.manifest),
    }
    (args.output_dir / "synthetic_run_summary.json").write_text(
        json.dumps(run_meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print("[synthetic] stage1 duplicates:", stage1_result["summary"].get("duplicate_documents"))
    print("[synthetic] stage2 duplicates:", stage2_result["summary"].get("duplicate_documents"))
    print("[synthetic] stage3 duplicates:", stage3_result["summary"].get("duplicate_documents"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
