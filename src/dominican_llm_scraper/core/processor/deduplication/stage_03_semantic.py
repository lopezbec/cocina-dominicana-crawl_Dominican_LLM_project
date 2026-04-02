import json
import math
import re
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Sequence, Set, Tuple

import chromadb


DEFAULT_MODEL_NAME = "qwen3-embedding:0.6b"
DEFAULT_TOP_K = 10
DEFAULT_THRESHOLD = 0.92
DEFAULT_MIN_TOKEN_COUNT = 50
DEFAULT_CHUNK_TOKEN_COUNT = 200
DEFAULT_LENGTH_RATIO_MIN = 0.7


class EmbeddingProvider(Protocol):
    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]: ...


class OllamaEmbeddingProvider:
    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        base_url: str = "http://127.0.0.1:11434",
        timeout_seconds: int = 120,
    ) -> None:
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        payload = json.dumps({"model": self.model_name, "input": list(texts)}).encode("utf-8")
        request = urllib.request.Request(
            url=f"{self.base_url}/api/embed",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Failed to fetch embeddings from Ollama: {exc}") from exc

        parsed = json.loads(body)
        embeddings = parsed.get("embeddings")
        if not embeddings:
            raise RuntimeError("Ollama embedding response did not contain embeddings")
        return embeddings


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def _normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _tokenize(text: str) -> List[str]:
    return re.findall(r"\w+", text.lower(), flags=re.UNICODE)


def _chunk_tokens(tokens: Sequence[str], chunk_token_count: int) -> List[str]:
    return [" ".join(tokens[index : index + chunk_token_count]) for index in range(0, len(tokens), chunk_token_count)]


def _average_vectors(vectors: Sequence[Sequence[float]]) -> List[float]:
    if not vectors:
        raise ValueError("Cannot average an empty list of vectors")
    vector_length = len(vectors[0])
    averaged = [0.0] * vector_length
    for vector in vectors:
        if len(vector) != vector_length:
            raise ValueError("All vectors must have the same dimensionality")
        for index, value in enumerate(vector):
            averaged[index] += float(value)
    return [value / len(vectors) for value in averaged]


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    numerator = sum(float(a) * float(b) for a, b in zip(left, right))
    left_norm = math.sqrt(sum(float(a) * float(a) for a in left))
    right_norm = math.sqrt(sum(float(b) * float(b) for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return numerator / (left_norm * right_norm)


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


def run_semantic_deduplication(
    input_dir: Path,
    output_jsonl: Optional[Path] = None,
    output_summary: Optional[Path] = None,
    embedding_provider: Optional[EmbeddingProvider] = None,
    model_name: str = DEFAULT_MODEL_NAME,
    top_k: int = DEFAULT_TOP_K,
    threshold: float = DEFAULT_THRESHOLD,
    min_token_count: int = DEFAULT_MIN_TOKEN_COUNT,
    chunk_token_count: int = DEFAULT_CHUNK_TOKEN_COUNT,
    length_ratio_min: float = DEFAULT_LENGTH_RATIO_MIN,
) -> Dict[str, Any]:
    metadata_path = input_dir / "metadata_plaintext.jsonl"
    stage_01_report_path = input_dir / "dedup_stage_01_exact.jsonl"
    stage_02_report_path = input_dir / "dedup_stage_02_near_duplicate.jsonl"

    for path in (metadata_path, stage_01_report_path, stage_02_report_path):
        if not path.exists():
            raise FileNotFoundError(f"Required Stage 3 input file not found: {path}")

    if output_jsonl is None:
        output_jsonl = input_dir / "dedup_stage_03_semantic.jsonl"
    if output_summary is None:
        output_summary = input_dir / "dedup_stage_03_semantic_summary.json"

    metadata_rows = _load_jsonl(metadata_path)
    metadata_by_doc_id = {row["doc_id"]: row for row in metadata_rows}
    stage_01_duplicates = {row["doc_id"] for row in _load_jsonl(stage_01_report_path) if row.get("is_duplicate", False)}
    survivor_doc_ids = [
        row["doc_id"]
        for row in _load_jsonl(stage_02_report_path)
        if not row.get("is_duplicate", False) and row["doc_id"] not in stage_01_duplicates
    ]

    if embedding_provider is None:
        embedding_provider = OllamaEmbeddingProvider(model_name=model_name)

    token_counts: Dict[str, int] = {}
    vectors_by_doc_id: Dict[str, List[float]] = {}
    skipped_short_doc_ids: Set[str] = set()

    for doc_id in survivor_doc_ids:
        row = metadata_by_doc_id.get(doc_id)
        if row is None:
            continue
        text_path = input_dir / row["filename"]
        if not text_path.exists():
            raise FileNotFoundError(f"Processed text file not found: {text_path}")

        tokens = _tokenize(_normalize_text(text_path.read_text(encoding="utf-8")))
        token_counts[doc_id] = len(tokens)
        if len(tokens) < min_token_count:
            skipped_short_doc_ids.add(doc_id)
            continue

        chunks = _chunk_tokens(tokens, chunk_token_count)
        chunk_embeddings = embedding_provider.embed_texts(chunks)
        vectors_by_doc_id[doc_id] = _average_vectors(chunk_embeddings)

    vector_doc_ids = [doc_id for doc_id in survivor_doc_ids if doc_id in vectors_by_doc_id]
    chroma_path = input_dir / ".chroma_stage_03_semantic"
    client = chromadb.PersistentClient(path=str(chroma_path))
    collection_name = "dedup_stage_03_semantic"
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass
    collection = client.create_collection(name=collection_name, metadata={"hnsw:space": "cosine"})

    if vector_doc_ids:
        collection.add(
            ids=vector_doc_ids,
            embeddings=[vectors_by_doc_id[doc_id] for doc_id in vector_doc_ids],
            metadatas=[{"doc_id": doc_id} for doc_id in vector_doc_ids],
        )

    doc_order = {doc_id: index for index, doc_id in enumerate(survivor_doc_ids)}
    neighbor_map: Dict[str, Set[str]] = defaultdict(set)
    candidate_pairs: Set[Tuple[str, str]] = set()
    for doc_id in vector_doc_ids:
        results = collection.query(
            query_embeddings=[vectors_by_doc_id[doc_id]],
            n_results=min(top_k + 1, len(vector_doc_ids)),
        )
        ids = results.get("ids", [[]])[0]
        for neighbor_id in ids:
            if neighbor_id == doc_id:
                continue
            neighbor_map[doc_id].add(neighbor_id)

    for doc_id, neighbors in neighbor_map.items():
        for neighbor_id in neighbors:
            if doc_id not in neighbor_map.get(neighbor_id, set()):
                continue
            left, right = sorted((doc_id, neighbor_id), key=lambda item: doc_order[item])
            candidate_pairs.add((left, right))

    edges: Dict[str, Set[str]] = defaultdict(set)
    best_match_by_doc_id: Dict[str, Tuple[str, float]] = {}
    candidate_pairs_evaluated = 0

    for left_doc_id, right_doc_id in sorted(candidate_pairs, key=lambda pair: (doc_order[pair[0]], doc_order[pair[1]])):
        candidate_pairs_evaluated += 1
        left_count = token_counts[left_doc_id]
        right_count = token_counts[right_doc_id]
        length_ratio = min(left_count, right_count) / max(left_count, right_count)
        if length_ratio < length_ratio_min:
            continue

        similarity = _cosine_similarity(vectors_by_doc_id[left_doc_id], vectors_by_doc_id[right_doc_id])
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
                    "semantic_similarity": None,
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
                "match_type": "semantic_embedding_cosine",
                "candidate_doc_id": best_match[0] if best_match else None,
                "semantic_similarity": round(best_match[1], 6) if best_match else None,
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
        "model_name": model_name,
        "top_k": top_k,
        "threshold": threshold,
    }
    with open(output_summary, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, ensure_ascii=False)

    return summary
