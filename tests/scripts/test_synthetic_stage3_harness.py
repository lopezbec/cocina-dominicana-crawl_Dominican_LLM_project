import importlib.util
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from dominican_llm_scraper.core.processor.deduplication.stage_01_exact import run_exact_deduplication
from dominican_llm_scraper.core.processor.deduplication.stage_02_near_duplicate import run_near_duplicate_deduplication
from dominican_llm_scraper.core.processor.deduplication.stage_03_semantic import run_semantic_deduplication


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "data" / "synthetic_stage3"
PROCESSED = FIXTURE / "processed"
MANIFEST = FIXTURE / "manifest.json"


def _load_script_module(script_path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module from {script_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _ollama_available(url: str = "http://127.0.0.1:11434/api/tags") -> bool:
    request = urllib.request.Request(url=url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=2):
            return True
    except (urllib.error.URLError, TimeoutError):
        return False


def test_fixture_files_exist_and_manifest_is_resolvable() -> None:
    assert (PROCESSED / "metadata_plaintext.jsonl").exists()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    for pair in manifest["pairs"]:
        left = pair["left_doc_id"]
        right = pair["right_doc_id"]
        rows = [json.loads(line) for line in (PROCESSED / "metadata_plaintext.jsonl").read_text(encoding="utf-8").splitlines()]
        by_id = {row["doc_id"]: row for row in rows}
        assert left in by_id
        assert right in by_id
        assert (PROCESSED / by_id[left]["filename"]).exists()
        assert (PROCESSED / by_id[right]["filename"]).exists()


def test_parse_pairs_validation() -> None:
    module = _load_script_module(ROOT / "scripts" / "generate_semantic_pairs_pdf.py", "semantic_pairs_report")
    parsed = module.parse_pairs("9001:9002,9003:9004")
    assert parsed == [("9001", "9002"), ("9003", "9004")]

    try:
        module.parse_pairs("9001-9002")
        assert False, "Expected ValueError for malformed pair"
    except ValueError:
        pass


def test_pair_a_collapses_pair_b_remains_distinct(tmp_path: Path) -> None:
    if not _ollama_available():
        pytest.skip("Integration test requires Ollama running on http://127.0.0.1:11434")

    for path in PROCESSED.glob("*.txt"):
        (tmp_path / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "metadata_plaintext.jsonl").write_text(
        (PROCESSED / "metadata_plaintext.jsonl").read_text(encoding="utf-8"), encoding="utf-8"
    )

    run_exact_deduplication(tmp_path)
    run_near_duplicate_deduplication(tmp_path, threshold=0.95)

    run_semantic_deduplication(
        tmp_path,
        eps_list=[0.9],
        ncentroids=1,
        kmeans_niter=20,
        seed=42,
        min_token_count=20,
        chunk_token_count=200,
        max_docs_for_stage3=50,
    )

    rows = [json.loads(line) for line in (tmp_path / "dedup_stage_03_semantic.jsonl").read_text(encoding="utf-8").splitlines()]
    by_id = {row["doc_id"]: row for row in rows}

    a1 = by_id["9001"]
    a2 = by_id["9002"]
    b1 = by_id["9003"]
    b2 = by_id["9004"]

    assert a1["canonical_doc_id"] == a2["canonical_doc_id"]
    assert a1["is_duplicate"] or a2["is_duplicate"]

    assert b1["canonical_doc_id"] != b2["canonical_doc_id"]
    assert not (b1["is_duplicate"] and b2["is_duplicate"])
