from dominican_llm_scraper.core.processor.deduplication.report import build_dedup_report


def test_dedup_report_answers_counts_by_domain_and_locations() -> None:
    metadata_rows = [
        {
            "doc_id": "0001",
            "domain": "a.com",
            "title": "Original A",
            "url": "https://a.com/original",
            "filename": "0001.txt",
        },
        {
            "doc_id": "0002",
            "domain": "a.com",
            "title": "Duplicate A",
            "url": "https://a.com/duplicate",
            "filename": "0002.txt",
        },
        {
            "doc_id": "0003",
            "domain": "b.com",
            "title": "Unique B",
            "url": "https://b.com/unique",
            "filename": "0003.txt",
        },
    ]
    stage_results = {
        "exact": {
            "summary": {"duplicate_documents": 1, "duplicate_groups": 1},
            "rows": [
                {
                    "doc_id": "0001",
                    "canonical_doc_id": "0001",
                    "is_duplicate": False,
                    "match_type": "exact_text_hash",
                },
                {
                    "doc_id": "0002",
                    "canonical_doc_id": "0001",
                    "is_duplicate": True,
                    "match_type": "exact_text_hash",
                    "hash": "abc123",
                },
            ],
        },
        "near_duplicate": {"summary": {"duplicate_documents": 0, "duplicate_groups": 0}, "rows": []},
    }

    report = build_dedup_report(metadata_rows, stage_results)

    assert report["summary"] == {
        "documents_scanned": 3,
        "duplicate_documents": 1,
        "kept_documents": 2,
        "duplicate_groups": 1,
    }
    assert report["by_domain"] == [
        {
            "domain": "a.com",
            "documents_scanned": 2,
            "duplicate_documents": 1,
            "kept_documents": 1,
            "duplicate_rate": 0.5,
        },
        {
            "domain": "b.com",
            "documents_scanned": 1,
            "duplicate_documents": 0,
            "kept_documents": 1,
            "duplicate_rate": 0.0,
        },
    ]

    duplicate = report["duplicates"][0]
    assert duplicate["url"] == "https://a.com/duplicate"
    assert duplicate["filename"] == "0002.txt"
    assert duplicate["canonical_url"] == "https://a.com/original"
    assert duplicate["canonical_filename"] == "0001.txt"
    assert duplicate["stage"] == "exact"
    assert duplicate["evidence"] == {"hash": "abc123"}
