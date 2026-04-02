import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from datasketch import MinHash, MinHashLSH


DEFAULT_SHINGLE_SIZE = 5
DEFAULT_NUM_PERM = 128
DEFAULT_THRESHOLD = 0.85
DEFAULT_MIN_TOKEN_COUNT = 30


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def _normalize_near_duplicate_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").lower()
    return re.sub(r"\s+", " ", text).strip()


def _tokenize(text: str) -> List[str]:
    return re.findall(r"\w+", text, flags=re.UNICODE)


def _build_shingles(tokens: List[str], shingle_size: int) -> Set[str]:
    if len(tokens) < shingle_size:
        return set()
    return {" ".join(tokens[index : index + shingle_size]) for index in range(len(tokens) - shingle_size + 1)}


def _build_minhash(shingles: Set[str], num_perm: int) -> MinHash:
    minhash = MinHash(num_perm=num_perm)
    for shingle in sorted(shingles):
        minhash.update(shingle.encode("utf-8"))
    return minhash


def _compute_jaccard_similarity(left: Set[str], right: Set[str]) -> float:
    if not left or not right:
        return 0.0
    intersection = len(left & right)
    union = len(left | right)
    return intersection / union if union else 0.0


def _connected_components(doc_ids: List[str], edges: Dict[str, Set[str]]) -> List[List[str]]:
    visited: Set[str] = set()
    components: List[List[str]] = []

    for doc_id in doc_ids:
        if doc_id in visited:
            continue
        stack = [doc_id]
        component: List[str] = []
        visited.add(doc_id)

        while stack:
            current = stack.pop()
            component.append(current)
            for neighbor in edges.get(current, set()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)

        components.append(component)

    return components


def run_near_duplicate_deduplication(
    input_dir: Path,
    output_jsonl: Optional[Path] = None,
    output_summary: Optional[Path] = None,
    shingle_size: int = DEFAULT_SHINGLE_SIZE,
    num_perm: int = DEFAULT_NUM_PERM,
    threshold: float = DEFAULT_THRESHOLD,
    min_token_count: int = DEFAULT_MIN_TOKEN_COUNT,
) -> Dict[str, Any]:
    metadata_path = input_dir / "metadata_plaintext.jsonl"
    stage_01_report_path = input_dir / "dedup_stage_01_exact.jsonl"
    if not metadata_path.exists():
        raise FileNotFoundError(f"Processed metadata file not found: {metadata_path}")
    if not stage_01_report_path.exists():
        raise FileNotFoundError(f"Stage 1 report file not found: {stage_01_report_path}")

    if output_jsonl is None:
        output_jsonl = input_dir / "dedup_stage_02_near_duplicate.jsonl"
    if output_summary is None:
        output_summary = input_dir / "dedup_stage_02_near_duplicate_summary.json"

    metadata_rows = _load_jsonl(metadata_path)
    metadata_by_doc_id = {row["doc_id"]: row for row in metadata_rows}
    stage_01_rows = _load_jsonl(stage_01_report_path)

    survivor_doc_ids = [row["doc_id"] for row in stage_01_rows if not row.get("is_duplicate", False)]
    survivor_rows = [metadata_by_doc_id[doc_id] for doc_id in survivor_doc_ids if doc_id in metadata_by_doc_id]

    shingles_by_doc_id: Dict[str, Set[str]] = {}
    minhash_by_doc_id: Dict[str, MinHash] = {}
    skipped_short_doc_ids: Set[str] = set()

    for row in survivor_rows:
        doc_id = row["doc_id"]
        text_path = input_dir / row["filename"]
        if not text_path.exists():
            raise FileNotFoundError(f"Processed text file not found: {text_path}")

        normalized_text = _normalize_near_duplicate_text(text_path.read_text(encoding="utf-8"))
        tokens = _tokenize(normalized_text)
        if len(tokens) < min_token_count:
            skipped_short_doc_ids.add(doc_id)
            continue

        shingles = _build_shingles(tokens, shingle_size)
        if not shingles:
            skipped_short_doc_ids.add(doc_id)
            continue

        shingles_by_doc_id[doc_id] = shingles
        minhash_by_doc_id[doc_id] = _build_minhash(shingles, num_perm)

    lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)
    for doc_id in survivor_doc_ids:
        if doc_id in minhash_by_doc_id:
            lsh.insert(doc_id, minhash_by_doc_id[doc_id])

    candidate_pairs: Set[Tuple[str, str]] = set()
    doc_order = {doc_id: index for index, doc_id in enumerate(survivor_doc_ids)}

    for doc_id in survivor_doc_ids:
        if doc_id not in minhash_by_doc_id:
            continue
        for neighbor_id in lsh.query(minhash_by_doc_id[doc_id]):
            if neighbor_id == doc_id:
                continue
            left, right = sorted((doc_id, neighbor_id), key=lambda item: doc_order[item])
            candidate_pairs.add((left, right))

    edges: Dict[str, Set[str]] = defaultdict(set)
    best_match_by_doc_id: Dict[str, Tuple[str, float]] = {}
    candidate_pairs_evaluated = 0

    for left_doc_id, right_doc_id in sorted(candidate_pairs, key=lambda pair: (doc_order[pair[0]], doc_order[pair[1]])):
        similarity = _compute_jaccard_similarity(shingles_by_doc_id[left_doc_id], shingles_by_doc_id[right_doc_id])
        candidate_pairs_evaluated += 1
        if similarity < threshold:
            continue

        edges[left_doc_id].add(right_doc_id)
        edges[right_doc_id].add(left_doc_id)

        for source_doc_id, target_doc_id in ((left_doc_id, right_doc_id), (right_doc_id, left_doc_id)):
            existing = best_match_by_doc_id.get(source_doc_id)
            if (
                existing is None
                or similarity > existing[1]
                or (similarity == existing[1] and doc_order[target_doc_id] < doc_order[existing[0]])
            ):
                best_match_by_doc_id[source_doc_id] = (target_doc_id, similarity)

    components = _connected_components(survivor_doc_ids, edges)
    canonical_by_doc_id: Dict[str, str] = {}
    duplicate_doc_ids: Set[str] = set()
    duplicate_groups = 0

    for component in components:
        canonical_doc_id = min(component, key=lambda item: doc_order[item])
        if len(component) > 1:
            duplicate_groups += 1
        for doc_id in component:
            canonical_by_doc_id[doc_id] = canonical_doc_id
            if doc_id != canonical_doc_id:
                duplicate_doc_ids.add(doc_id)

    report_rows: List[Dict[str, Any]] = []
    for doc_id in survivor_doc_ids:
        if doc_id in skipped_short_doc_ids:
            report_rows.append(
                {
                    "doc_id": doc_id,
                    "canonical_doc_id": doc_id,
                    "is_duplicate": False,
                    "match_type": "skipped_short_document",
                    "candidate_doc_id": None,
                    "jaccard_similarity": None,
                    "threshold": threshold,
                }
            )
            continue

        best_match = best_match_by_doc_id.get(doc_id)
        report_rows.append(
            {
                "doc_id": doc_id,
                "canonical_doc_id": canonical_by_doc_id.get(doc_id, doc_id),
                "is_duplicate": doc_id in duplicate_doc_ids,
                "match_type": "minhash_lsh_jaccard",
                "candidate_doc_id": best_match[0] if best_match else None,
                "jaccard_similarity": round(best_match[1], 6) if best_match else None,
                "threshold": threshold,
            }
        )

    with open(output_jsonl, "w", encoding="utf-8") as handle:
        for row in report_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = {
        "documents_scanned": len(survivor_doc_ids),
        "documents_skipped_short": len(skipped_short_doc_ids),
        "candidate_pairs_evaluated": candidate_pairs_evaluated,
        "duplicate_documents": len(duplicate_doc_ids),
        "duplicate_groups": duplicate_groups,
        "shingle_size": shingle_size,
        "num_perm": num_perm,
        "threshold": threshold,
    }

    with open(output_summary, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, ensure_ascii=False)

    return summary
