import json
from pathlib import Path

from dominican_llm_scraper.core.processor.deduplication.stage_01_exact import run_exact_deduplication
from dominican_llm_scraper.core.processor.pipeline import process_markdown_to_plain_text


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


def test_stage_01_exact_detects_duplicate_texts(tmp_path: Path) -> None:
    _write_processed_corpus(
        tmp_path,
        [
            {"doc_id": "0001", "filename": "0001.txt", "text": "Texto igual\n"},
            {"doc_id": "0002", "filename": "0002.txt", "text": "Texto igual\n"},
            {"doc_id": "0003", "filename": "0003.txt", "text": "Texto distinto\n"},
        ],
    )

    summary = run_exact_deduplication(tmp_path)

    assert summary == {
        "documents_scanned": 3,
        "unique_documents": 2,
        "duplicate_documents": 1,
        "duplicate_groups": 1,
    }

    report_rows = [
        json.loads(line) for line in (tmp_path / "dedup_stage_01_exact.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert report_rows[0]["canonical_doc_id"] == "0001"
    assert report_rows[0]["is_duplicate"] is False
    assert report_rows[1]["canonical_doc_id"] == "0001"
    assert report_rows[1]["is_duplicate"] is True
    assert report_rows[2]["canonical_doc_id"] == "0003"
    assert report_rows[2]["is_duplicate"] is False


def test_stage_01_exact_preserves_unique_documents(tmp_path: Path) -> None:
    _write_processed_corpus(
        tmp_path,
        [
            {"doc_id": "0001", "filename": "0001.txt", "text": "Uno"},
            {"doc_id": "0002", "filename": "0002.txt", "text": "Dos"},
        ],
    )

    summary = run_exact_deduplication(tmp_path)

    assert summary["duplicate_documents"] == 0
    assert summary["duplicate_groups"] == 0
    assert summary["unique_documents"] == 2


def test_stage_01_exact_uses_processed_pipeline_output(tmp_path: Path) -> None:
    markdown_one = "# Titulo\n\nHola    mundo\r\n"
    markdown_two = "# Titulo\n\nHola mundo\n"

    _meta, plain_one = process_markdown_to_plain_text(markdown_one)
    _meta, plain_two = process_markdown_to_plain_text(markdown_two)

    _write_processed_corpus(
        tmp_path,
        [
            {"doc_id": "0001", "filename": "0001.txt", "text": plain_one, "title": "A"},
            {"doc_id": "0002", "filename": "0002.txt", "text": plain_two, "title": "B"},
        ],
    )

    summary = run_exact_deduplication(tmp_path)

    assert summary["duplicate_documents"] == 1
    report_rows = [
        json.loads(line) for line in (tmp_path / "dedup_stage_01_exact.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert report_rows[1]["canonical_doc_id"] == "0001"
    assert report_rows[1]["is_duplicate"] is True


def test_stage_01_exact_does_not_use_title_only(tmp_path: Path) -> None:
    _write_processed_corpus(
        tmp_path,
        [
            {"doc_id": "0001", "filename": "0001.txt", "text": "Texto A", "title": "Mismo titulo"},
            {"doc_id": "0002", "filename": "0002.txt", "text": "Texto B", "title": "Mismo titulo"},
        ],
    )

    summary = run_exact_deduplication(tmp_path)

    assert summary["duplicate_documents"] == 0


def test_stage_01_exact_writes_expected_report_files(tmp_path: Path) -> None:
    _write_processed_corpus(
        tmp_path,
        [
            {"doc_id": "0001", "filename": "0001.txt", "text": "Texto igual"},
            {"doc_id": "0002", "filename": "0002.txt", "text": "Texto igual"},
        ],
    )

    run_exact_deduplication(tmp_path)

    summary_path = tmp_path / "dedup_stage_01_exact_summary.json"
    report_path = tmp_path / "dedup_stage_01_exact.jsonl"

    assert report_path.exists()
    assert summary_path.exists()

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert set(summary) == {
        "documents_scanned",
        "unique_documents",
        "duplicate_documents",
        "duplicate_groups",
    }
