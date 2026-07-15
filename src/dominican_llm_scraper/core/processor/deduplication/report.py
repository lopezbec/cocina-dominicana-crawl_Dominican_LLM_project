import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List


STAGE_PRIORITY = {
    "exact": 1,
    "near_duplicate": 2,
    "semantic": 3,
    "sentence_span": 4,
}


def load_metadata(input_dir: Path) -> List[Dict[str, Any]]:
    metadata_path = input_dir / "metadata_plaintext.jsonl"
    rows: List[Dict[str, Any]] = []
    with open(metadata_path, "r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def _score_for_row(row: Dict[str, Any]) -> float | None:
    for key in ("stage3_similarity", "semantic_similarity", "jaccard_similarity"):
        value = row.get(key)
        if value is not None:
            return float(value)
    return None


def _evidence_for_row(row: Dict[str, Any]) -> Dict[str, Any]:
    evidence_keys = (
        "hash",
        "candidate_doc_id",
        "matched_span_hash",
        "matched_span_text",
        "matched_sentence_start",
        "candidate_epsilon",
        "span_sentence_count",
        "threshold",
    )
    return {key: row[key] for key in evidence_keys if key in row and row[key] is not None}


def _duplicate_entry(
    row: Dict[str, Any],
    stage: str,
    metadata_by_doc_id: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    doc = metadata_by_doc_id.get(row["doc_id"], {})
    canonical_doc_id = row.get("canonical_doc_id")
    canonical = metadata_by_doc_id.get(str(canonical_doc_id), {}) if canonical_doc_id is not None else {}
    return {
        "doc_id": row["doc_id"],
        "domain": doc.get("domain", "unknown"),
        "title": doc.get("title", ""),
        "url": doc.get("url", ""),
        "filename": doc.get("filename", ""),
        "canonical_doc_id": row.get("canonical_doc_id"),
        "canonical_domain": canonical.get("domain", "unknown"),
        "canonical_title": canonical.get("title", ""),
        "canonical_url": canonical.get("url", ""),
        "canonical_filename": canonical.get("filename", ""),
        "stage": stage,
        "match_type": row.get("match_type"),
        "score": _score_for_row(row),
        "evidence": _evidence_for_row(row),
    }


def build_dedup_report(
    metadata_rows: List[Dict[str, Any]],
    stage_results: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    metadata_by_doc_id = {row["doc_id"]: row for row in metadata_rows}
    chosen_duplicates: Dict[str, Dict[str, Any]] = {}

    by_stage = {stage: result["summary"] for stage, result in stage_results.items()}

    for stage, result in stage_results.items():
        for row in result.get("rows", []):
            if not row.get("is_duplicate", False):
                continue

            entry = _duplicate_entry(row, stage, metadata_by_doc_id)
            existing = chosen_duplicates.get(row["doc_id"])
            if existing is None or STAGE_PRIORITY[stage] >= STAGE_PRIORITY[existing["stage"]]:
                chosen_duplicates[row["doc_id"]] = entry

    duplicate_entries = sorted(chosen_duplicates.values(), key=lambda item: item["doc_id"])
    duplicate_doc_ids = {entry["doc_id"] for entry in duplicate_entries}
    duplicate_domains = Counter(entry["domain"] for entry in duplicate_entries)
    documents_by_domain = Counter(row.get("domain", "unknown") for row in metadata_rows)

    by_domain = []
    for domain in sorted(documents_by_domain):
        scanned = documents_by_domain[domain]
        duplicates = duplicate_domains[domain]
        kept = scanned - duplicates
        by_domain.append(
            {
                "domain": domain,
                "documents_scanned": scanned,
                "duplicate_documents": duplicates,
                "kept_documents": kept,
                "duplicate_rate": round(duplicates / scanned, 6) if scanned else 0.0,
            }
        )

    diagnostics = {
        stage: result["diagnostics"] for stage, result in stage_results.items() if result.get("diagnostics")
    }

    return {
        "summary": {
            "documents_scanned": len(metadata_rows),
            "duplicate_documents": len(duplicate_doc_ids),
            "kept_documents": len(metadata_rows) - len(duplicate_doc_ids),
            "duplicate_groups": len({entry["canonical_doc_id"] for entry in duplicate_entries}),
        },
        "by_stage": by_stage,
        "by_domain": by_domain,
        "duplicates": duplicate_entries,
        "diagnostics": diagnostics,
    }


def write_dedup_report(output_dir: Path, report: Dict[str, Any]) -> Path:
    output_path = output_dir / "dedup_report.json"
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return output_path
