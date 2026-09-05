import json
from pathlib import Path
from typing import Dict, List

from dominican_llm_processor.deduplication import (
    run_exact_deduplication,
    run_near_duplicate_deduplication,
    run_sentence_span_deduplication,
    run_semantic_deduplication,
)
from dominican_llm_processor.deduplication.report import build_dedup_report, write_dedup_report
from dominican_llm_processor.pipeline import process_markdown_to_plain_text
from dominican_llm_processor.file_utils import create_safe_filename


def process_all_files(
    input_dir: Path,
    output_dir: Path,
    min_content_length: int = 50,
) -> None:

    metadata_file = input_dir / "metadata.jsonl"
    if not metadata_file.exists():
        raise FileNotFoundError(
            f"Raw metadata file not found: {metadata_file}. Run the crawler before processing."
        )

    output_dir.mkdir(parents=True, exist_ok=True)

    metadata_entries: List[Dict] = []
    with open(metadata_file, "r", encoding="utf-8") as f:
        for line in f:
            metadata_entries.append(json.loads(line))

    processed_metadata: List[Dict] = []
    total = len(metadata_entries)
    processed = 0
    missing = 0
    failed = 0

    for index, meta in enumerate(metadata_entries, start=1):
        doc_id = meta["doc_id"]
        domain = meta.get("domain", "unknown")
        domain_slug = domain.replace(".", "_")
        safe_slug = create_safe_filename(meta["url_slug"])
        filename = f"{doc_id}_{domain_slug}_{safe_slug}.md"
        print(f"Processing {index}/{total}: {filename}")

        md_file = input_dir / filename
        if not md_file.exists():
            print(f"Warning: File not found: {filename}")
            missing += 1
            continue

        try:
            with open(md_file, "r", encoding="utf-8") as f:
                content = f.read()

            _frontmatter, plain_text = process_markdown_to_plain_text(content)

            if len(plain_text.strip()) <= min_content_length:
                print(f"Skipping {filename}: content too short")
                continue

            output_filename = f"{doc_id}_{domain_slug}_{safe_slug}.txt"
            output_file = output_dir / output_filename

            with open(output_file, "w", encoding="utf-8") as f:
                f.write(plain_text)

            processed += 1
            processed_metadata.append(
                {
                    "doc_id": doc_id,
                    "domain": domain,
                    "filename": output_filename,
                    "source_md": filename,
                    "title": meta.get("title", ""),
                    "url": meta.get("url", ""),
                    "word_count": len(plain_text.split()),
                    "char_count": len(plain_text),
                }
            )
        except (OSError, ValueError, KeyError) as exc:
            print(f"Error processing {filename}: {exc}")
            failed += 1
            continue

    metadata_output = output_dir / "metadata_plaintext.jsonl"
    with open(metadata_output, "w", encoding="utf-8") as f:
        for entry in processed_metadata:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print("\nProcessing complete")
    print(f"Processed: {processed}")
    print(f"Missing: {missing}")
    print(f"Failed: {failed}")
    print(f"Metadata: {metadata_output}")

    # Comment out individual stage calls below while validating a single dedup stage in isolation.
    exact_result = run_exact_deduplication(output_dir)
    print(f"Exact dedup duplicates: {exact_result['summary']['duplicate_documents']}")

    near_result = run_near_duplicate_deduplication(output_dir, exact_result["rows"])
    print(f"Near dedup duplicates: {near_result['summary']['duplicate_documents']}")

    semantic_result = run_semantic_deduplication(output_dir, exact_result["rows"], near_result["rows"])
    print(f"Semantic dedup duplicates: {semantic_result['summary']['duplicate_documents']}")

    sentence_span_result = run_sentence_span_deduplication(
        output_dir,
        exact_result["rows"],
        near_result["rows"],
        semantic_result["pair_edges"],
    )
    print(f"Sentence span dedup duplicates: {sentence_span_result['summary']['duplicate_documents']}")

    dedup_report = build_dedup_report(
        processed_metadata,
        {
            "exact": exact_result,
            "near_duplicate": near_result,
            "semantic": semantic_result,
            "sentence_span": sentence_span_result,
        },
    )
    dedup_report_path = write_dedup_report(output_dir, dedup_report)
    print(f"Dedup report: {dedup_report_path}")
