import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def normalize_exact_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def _load_processed_metadata(metadata_path: Path) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    with open(metadata_path, "r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                entries.append(json.loads(stripped))
    return entries


def _compute_content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_exact_deduplication(
    input_dir: Path,
    output_jsonl: Optional[Path] = None,
    output_summary: Optional[Path] = None,
) -> Dict[str, int]:
    metadata_path = input_dir / "metadata_plaintext.jsonl"
    if not metadata_path.exists():
        raise FileNotFoundError(f"Processed metadata file not found: {metadata_path}")

    if output_jsonl is None:
        output_jsonl = input_dir / "dedup_stage_01_exact.jsonl"
    if output_summary is None:
        output_summary = input_dir / "dedup_stage_01_exact_summary.json"

    entries = _load_processed_metadata(metadata_path)
    hash_to_canonical: Dict[str, str] = {}
    report_rows: List[Dict[str, Any]] = []
    duplicate_groups = set()
    duplicate_documents = 0

    for entry in entries:
        filename = entry.get("filename")
        doc_id = entry.get("doc_id")
        if not filename or not doc_id:
            raise ValueError("Each metadata entry must contain 'doc_id' and 'filename'")

        text_path = input_dir / filename
        if not text_path.exists():
            raise FileNotFoundError(f"Processed text file not found: {text_path}")

        with open(text_path, "r", encoding="utf-8") as handle:
            normalized_text = normalize_exact_text(handle.read())

        content_hash = _compute_content_hash(normalized_text)
        canonical_doc_id = hash_to_canonical.setdefault(content_hash, doc_id)
        is_duplicate = canonical_doc_id != doc_id

        if is_duplicate:
            duplicate_documents += 1
            duplicate_groups.add(canonical_doc_id)

        report_rows.append(
            {
                "doc_id": doc_id,
                "canonical_doc_id": canonical_doc_id,
                "is_duplicate": is_duplicate,
                "match_type": "exact_text_hash",
                "hash": content_hash,
            }
        )

    with open(output_jsonl, "w", encoding="utf-8") as handle:
        for row in report_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = {
        "documents_scanned": len(entries),
        "unique_documents": len(entries) - duplicate_documents,
        "duplicate_documents": duplicate_documents,
        "duplicate_groups": len(duplicate_groups),
    }

    with open(output_summary, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, ensure_ascii=False)

    return summary
