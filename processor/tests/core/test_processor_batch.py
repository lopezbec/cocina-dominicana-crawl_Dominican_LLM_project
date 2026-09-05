import json

from dominican_llm_processor import batch


def _write_scraped_document(input_dir, doc_id: str, slug: str) -> None:
    metadata = {
        "doc_id": doc_id,
        "domain": "example.com",
        "url_slug": slug,
        "title": slug,
        "url": f"https://example.com/{slug}",
    }
    with open(input_dir / "metadata.jsonl", "a", encoding="utf-8") as metadata_file:
        metadata_file.write(json.dumps(metadata) + "\n")

    (input_dir / f"{doc_id}_example_com_{slug}.md").write_text(slug, encoding="utf-8")


def test_process_all_files_removes_documents_with_50_or_fewer_characters(tmp_path, monkeypatch) -> None:
    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "processed"
    input_dir.mkdir()

    _write_scraped_document(input_dir, "doc1", "short")
    _write_scraped_document(input_dir, "doc2", "boundary")
    _write_scraped_document(input_dir, "doc3", "kept")

    processed_text = {
        "short": "x" * 49,
        "boundary": "x" * 50,
        "kept": "x" * 51,
    }

    def fake_process_markdown_to_plain_text(content: str):
        return {}, processed_text[content]

    empty_result = {"summary": {"duplicate_documents": 0, "duplicate_groups": 0}, "rows": []}

    monkeypatch.setattr(batch, "process_markdown_to_plain_text", fake_process_markdown_to_plain_text)
    monkeypatch.setattr(batch, "run_exact_deduplication", lambda output: empty_result)
    monkeypatch.setattr(batch, "run_near_duplicate_deduplication", lambda output, stage_01_rows: empty_result)
    monkeypatch.setattr(
        batch,
        "run_semantic_deduplication",
        lambda output, stage_01_rows, stage_02_rows: {**empty_result, "pair_edges": []},
    )
    monkeypatch.setattr(
        batch,
        "run_sentence_span_deduplication",
        lambda output, stage_01_rows, stage_02_rows, pair_edges: empty_result,
    )

    batch.process_all_files(input_dir, output_dir, min_content_length=50)

    metadata_rows = [
        json.loads(line)
        for line in (output_dir / "metadata_plaintext.jsonl").read_text(encoding="utf-8").splitlines()
    ]

    assert [row["doc_id"] for row in metadata_rows] == ["doc3"]
    assert not (output_dir / "doc1_example_com_short.txt").exists()
    assert not (output_dir / "doc2_example_com_boundary.txt").exists()
    assert (output_dir / "doc3_example_com_kept.txt").exists()
    assert (output_dir / "dedup_report.json").exists()
    assert not list(output_dir.glob("dedup_stage_*"))
