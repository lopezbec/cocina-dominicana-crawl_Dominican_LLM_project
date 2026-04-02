import json
from pathlib import Path

from dominican_llm_scraper.core.processor.deduplication.stage_01_exact import run_exact_deduplication
from dominican_llm_scraper.core.processor.deduplication.stage_02_near_duplicate import run_near_duplicate_deduplication


def _write_processed_corpus(base_dir: Path, documents: list[dict]) -> None:
    metadata_path = base_dir / "metadata_plaintext.jsonl"
    with open(metadata_path, "w", encoding="utf-8") as metadata_handle:
        for document in documents:
            (base_dir / document["filename"]).write_text(document["text"], encoding="utf-8")
            metadata_row = {
                "doc_id": document["doc_id"],
                "filename": document["filename"],
                "title": document.get("title", ""),
                "url": document.get("url", ""),
                "domain": document.get("domain", "example.com"),
            }
            metadata_handle.write(json.dumps(metadata_row, ensure_ascii=False) + "\n")


def _run_stage_01(base_dir: Path) -> None:
    run_exact_deduplication(base_dir)


def test_stage_02_detects_near_duplicates(tmp_path: Path) -> None:
    _write_processed_corpus(
        tmp_path,
        [
            {
                "doc_id": "0001",
                "filename": "0001.txt",
                "text": "uno dos tres cuatro cinco seis siete ocho nueve diez once doce trece catorce quince dieciseis "
                "diecisiete dieciocho diecinueve veinte veintiuno veintidos veintitres veinticuatro veinticinco "
                "veintiseis veintisiete veintiocho veintinueve treinta treintauno",
            },
            {
                "doc_id": "0002",
                "filename": "0002.txt",
                "text": "uno dos tres cuatro cinco seis siete ocho nueve diez once doce trece catorce quince dieciseis "
                "diecisiete dieciocho diecinueve veinte veintiuno veintidos veintitres veinticuatro veinticinco "
                "veintiseis veintisiete veintiocho treinta treintauno treintados",
            },
        ],
    )
    _run_stage_01(tmp_path)

    summary = run_near_duplicate_deduplication(tmp_path, threshold=0.8)

    assert summary["duplicate_documents"] == 1
    report_rows = [
        json.loads(line)
        for line in (tmp_path / "dedup_stage_02_near_duplicate.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert report_rows[1]["canonical_doc_id"] == "0001"
    assert report_rows[1]["is_duplicate"] is True
    assert report_rows[1]["jaccard_similarity"] >= 0.8


def test_stage_02_ignores_stage_01_duplicates(tmp_path: Path) -> None:
    _write_processed_corpus(
        tmp_path,
        [
            {"doc_id": "0001", "filename": "0001.txt", "text": "texto identico " * 40},
            {"doc_id": "0002", "filename": "0002.txt", "text": "texto identico " * 40},
            {"doc_id": "0003", "filename": "0003.txt", "text": "otro documento diferente " * 40},
        ],
    )
    _run_stage_01(tmp_path)

    summary = run_near_duplicate_deduplication(tmp_path)

    assert summary["documents_scanned"] == 2
    report_rows = [
        json.loads(line)
        for line in (tmp_path / "dedup_stage_02_near_duplicate.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert {row["doc_id"] for row in report_rows} == {"0001", "0003"}


def test_stage_02_preserves_distinct_documents(tmp_path: Path) -> None:
    _write_processed_corpus(
        tmp_path,
        [
            {
                "doc_id": "0001",
                "filename": "0001.txt",
                "text": "arroz habichuelas pollo platano yuca cocina sazón mesa familia receta dominicana caribe sabor "
                * 3,
            },
            {
                "doc_id": "0002",
                "filename": "0002.txt",
                "text": "economia banco moneda credito interes inflacion mercado exportacion reservas financiera politica fiscal "
                * 3,
            },
        ],
    )
    _run_stage_01(tmp_path)

    summary = run_near_duplicate_deduplication(tmp_path)

    assert summary["duplicate_documents"] == 0


def test_stage_02_builds_connected_components(tmp_path: Path) -> None:
    _write_processed_corpus(
        tmp_path,
        [
            {
                "doc_id": "0001",
                "filename": "0001.txt",
                "text": "a1 a2 a3 a4 a5 a6 a7 a8 a9 a10 a11 a12 a13 a14 a15 a16 a17 a18 a19 a20 a21 a22 a23 a24 a25 a26 a27 a28 a29 a30 a31 a32",
            },
            {
                "doc_id": "0002",
                "filename": "0002.txt",
                "text": "a1 a2 a3 a4 a5 a6 a7 a8 a9 a10 a11 a12 a13 a14 a15 a16 a17 a18 a19 a20 a21 a22 a23 a24 a25 a26 a27 a28 b29 b30 b31 b32",
            },
            {
                "doc_id": "0003",
                "filename": "0003.txt",
                "text": "a1 a2 a3 a4 a5 a6 a7 a8 a9 a10 a11 a12 a13 a14 a15 a16 a17 a18 a19 a20 a21 a22 a23 a24 c25 c26 c27 c28 c29 c30 c31 c32",
            },
        ],
    )
    _run_stage_01(tmp_path)

    summary = run_near_duplicate_deduplication(tmp_path, threshold=0.5)

    assert summary["duplicate_groups"] == 1
    report_rows = {
        row["doc_id"]: row
        for row in [
            json.loads(line)
            for line in (tmp_path / "dedup_stage_02_near_duplicate.jsonl").read_text(encoding="utf-8").splitlines()
        ]
    }
    assert report_rows["0002"]["canonical_doc_id"] == "0001"
    assert report_rows["0003"]["canonical_doc_id"] == "0001"


def test_stage_02_skips_short_documents(tmp_path: Path) -> None:
    _write_processed_corpus(
        tmp_path,
        [
            {"doc_id": "0001", "filename": "0001.txt", "text": "texto corto uno dos tres"},
            {"doc_id": "0002", "filename": "0002.txt", "text": "texto corto uno dos tres cuatro"},
        ],
    )
    _run_stage_01(tmp_path)

    summary = run_near_duplicate_deduplication(tmp_path, min_token_count=30)

    assert summary["documents_skipped_short"] == 2
    report_rows = [
        json.loads(line)
        for line in (tmp_path / "dedup_stage_02_near_duplicate.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert all(row["match_type"] == "skipped_short_document" for row in report_rows)


def test_stage_02_writes_expected_report_files(tmp_path: Path) -> None:
    _write_processed_corpus(
        tmp_path,
        [
            {"doc_id": "0001", "filename": "0001.txt", "text": "texto uno " * 40},
            {"doc_id": "0002", "filename": "0002.txt", "text": "texto dos " * 40},
        ],
    )
    _run_stage_01(tmp_path)

    run_near_duplicate_deduplication(tmp_path)

    summary_path = tmp_path / "dedup_stage_02_near_duplicate_summary.json"
    report_path = tmp_path / "dedup_stage_02_near_duplicate.jsonl"
    assert report_path.exists()
    assert summary_path.exists()

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert set(summary) == {
        "documents_scanned",
        "documents_skipped_short",
        "candidate_pairs_evaluated",
        "duplicate_documents",
        "duplicate_groups",
        "shingle_size",
        "num_perm",
        "threshold",
    }
