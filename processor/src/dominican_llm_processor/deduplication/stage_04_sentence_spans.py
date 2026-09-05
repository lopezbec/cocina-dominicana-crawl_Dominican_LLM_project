import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple


DEFAULT_CANDIDATE_EPSILON = 0.90
DEFAULT_SPAN_SENTENCE_COUNT = 3


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def _normalize_sentence(sentence: str) -> str:
    return re.sub(r"\s+", " ", sentence).strip()


def _split_sentences(text: str) -> List[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if not normalized:
        return []

    sentences = re.split(r"(?<=[.!?])\s+", normalized)
    return [_normalize_sentence(sentence) for sentence in sentences if _normalize_sentence(sentence)]


def _build_sentence_spans(sentences: Sequence[str], span_sentence_count: int) -> Dict[str, List[Dict[str, Any]]]:
    spans: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    if span_sentence_count <= 0:
        raise ValueError("span_sentence_count must be greater than zero")
    if len(sentences) < span_sentence_count:
        return spans

    for start in range(len(sentences) - span_sentence_count + 1):
        span_sentences = sentences[start : start + span_sentence_count]
        span_text = " ".join(span_sentences)
        span_hash = hashlib.sha256(span_text.encode("utf-8")).hexdigest()
        spans[span_hash].append(
            {
                "matched_span_hash": span_hash,
                "matched_span_text": span_text,
                "matched_sentence_start": start,
            }
        )
    return spans


def _connected_components(nodes: Sequence[str], edges: Dict[str, Set[str]]) -> List[List[str]]:
    visited: Set[str] = set()
    components: List[List[str]] = []

    for node in nodes:
        if node in visited:
            continue
        stack = [node]
        component: List[str] = []
        visited.add(node)

        while stack:
            current = stack.pop()
            component.append(current)
            for neighbor in edges.get(current, set()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)

        components.append(component)

    return components


def _select_stage2_survivors(stage_01_rows: List[Dict[str, Any]], stage_02_rows: List[Dict[str, Any]]) -> List[str]:
    stage_01_duplicates = {row["doc_id"] for row in stage_01_rows if row.get("is_duplicate", False)}
    return [
        row["doc_id"]
        for row in stage_02_rows
        if not row.get("is_duplicate", False) and row["doc_id"] not in stage_01_duplicates
    ]


def _find_shared_span(
    left_spans: Dict[str, List[Dict[str, Any]]],
    right_spans: Dict[str, List[Dict[str, Any]]],
) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
    for span_hash in sorted(set(left_spans) & set(right_spans)):
        return left_spans[span_hash][0], right_spans[span_hash][0]
    return None


def run_sentence_span_deduplication(
    input_dir: Path,
    stage_01_rows: List[Dict[str, Any]],
    stage_02_rows: List[Dict[str, Any]],
    stage_03_pair_edges: List[Dict[str, Any]],
    candidate_epsilon: float = DEFAULT_CANDIDATE_EPSILON,
    span_sentence_count: int = DEFAULT_SPAN_SENTENCE_COUNT,
    same_domain_only: bool = True,
    max_pairs: Optional[int] = None,
) -> Dict[str, Any]:
    metadata_path = input_dir / "metadata_plaintext.jsonl"
    if not metadata_path.exists():
        raise FileNotFoundError(f"Processed metadata file not found: {metadata_path}")

    metadata_rows = _load_jsonl(metadata_path)
    metadata_by_doc_id = {row["doc_id"]: row for row in metadata_rows}
    survivor_doc_ids = _select_stage2_survivors(stage_01_rows, stage_02_rows)
    survivor_doc_id_set = set(survivor_doc_ids)
    doc_order = {doc_id: index for index, doc_id in enumerate(survivor_doc_ids)}

    if not stage_03_pair_edges:
        return {
            "summary": {
                "documents_scanned": len(survivor_doc_ids),
                "candidate_pairs_scanned": 0,
                "matched_pairs": 0,
                "duplicate_documents": 0,
                "duplicate_groups": 0,
                "candidate_epsilon": candidate_epsilon,
                "span_sentence_count": span_sentence_count,
                "same_domain_only": same_domain_only,
            },
            "rows": [],
        }

    required_columns = {"doc_id_a", "doc_id_b", "similarity"}
    for edge in stage_03_pair_edges:
        missing_columns = required_columns - set(edge)
        if missing_columns:
            raise ValueError(f"Stage 3 pair edge missing required columns: {sorted(missing_columns)}")

    candidate_pairs: List[Tuple[str, str, float]] = []
    sorted_edges = sorted(
        stage_03_pair_edges,
        key=lambda row: (-float(row["similarity"]), str(row["doc_id_a"]), str(row["doc_id_b"])),
    )
    for row in sorted_edges:
        left_doc_id = str(row["doc_id_a"])
        right_doc_id = str(row["doc_id_b"])
        similarity = float(row["similarity"])
        if similarity < candidate_epsilon:
            continue
        if left_doc_id not in survivor_doc_id_set or right_doc_id not in survivor_doc_id_set:
            continue
        if same_domain_only:
            left_domain = metadata_by_doc_id.get(left_doc_id, {}).get("domain")
            right_domain = metadata_by_doc_id.get(right_doc_id, {}).get("domain")
            if left_domain != right_domain:
                continue
        candidate_pairs.append((left_doc_id, right_doc_id, similarity))
        if max_pairs is not None and len(candidate_pairs) >= max_pairs:
            break

    spans_by_doc_id: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}

    def spans_for_doc(doc_id: str) -> Dict[str, List[Dict[str, Any]]]:
        if doc_id not in spans_by_doc_id:
            row = metadata_by_doc_id.get(doc_id)
            if row is None:
                raise ValueError(f"Metadata row not found for doc_id={doc_id}")
            text_path = input_dir / row["filename"]
            if not text_path.exists():
                raise FileNotFoundError(f"Processed text file not found: {text_path}")
            sentences = _split_sentences(text_path.read_text(encoding="utf-8"))
            spans_by_doc_id[doc_id] = _build_sentence_spans(sentences, span_sentence_count)
        return spans_by_doc_id[doc_id]

    edges: Dict[str, Set[str]] = defaultdict(set)
    evidence_by_pair: Dict[Tuple[str, str], Dict[str, Any]] = {}

    for left_doc_id, right_doc_id, similarity in candidate_pairs:
        shared_span = _find_shared_span(spans_for_doc(left_doc_id), spans_for_doc(right_doc_id))
        if shared_span is None:
            continue

        left_span, right_span = shared_span
        earlier_doc_id, later_doc_id = sorted((left_doc_id, right_doc_id), key=lambda item: doc_order[item])
        duplicate_span = left_span if later_doc_id == left_doc_id else right_span

        edges[left_doc_id].add(right_doc_id)
        edges[right_doc_id].add(left_doc_id)
        evidence_by_pair[(earlier_doc_id, later_doc_id)] = {
            "candidate_doc_id": earlier_doc_id,
            "stage3_similarity": similarity,
            **duplicate_span,
        }

    components = _connected_components(survivor_doc_ids, edges)
    report_rows: List[Dict[str, Any]] = []
    duplicate_groups = 0

    for component in components:
        if len(component) <= 1:
            continue
        duplicate_groups += 1
        canonical_doc_id = min(component, key=lambda item: doc_order[item])
        for doc_id in sorted(component, key=lambda item: doc_order[item]):
            if doc_id == canonical_doc_id:
                continue

            evidence = evidence_by_pair.get((canonical_doc_id, doc_id))
            if evidence is None:
                evidence = next(
                    value
                    for (left_doc_id, right_doc_id), value in sorted(evidence_by_pair.items())
                    if doc_id in {left_doc_id, right_doc_id} and left_doc_id in component and right_doc_id in component
                )

            report_rows.append(
                {
                    "doc_id": doc_id,
                    "canonical_doc_id": canonical_doc_id,
                    "is_duplicate": True,
                    "match_type": "exact_3_sentence_span",
                    "candidate_doc_id": evidence["candidate_doc_id"],
                    "stage3_similarity": round(float(evidence["stage3_similarity"]), 6),
                    "matched_span_hash": evidence["matched_span_hash"],
                    "matched_span_text": evidence["matched_span_text"],
                    "matched_sentence_start": evidence["matched_sentence_start"],
                    "candidate_epsilon": candidate_epsilon,
                    "span_sentence_count": span_sentence_count,
                }
            )

    summary = {
        "documents_scanned": len(survivor_doc_ids),
        "candidate_pairs_scanned": len(candidate_pairs),
        "matched_pairs": len(evidence_by_pair),
        "duplicate_documents": len(report_rows),
        "duplicate_groups": duplicate_groups,
        "candidate_epsilon": candidate_epsilon,
        "span_sentence_count": span_sentence_count,
        "same_domain_only": same_domain_only,
    }

    return {"summary": summary, "rows": report_rows}
