import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple

import faiss
import numpy as np
import pandas as pd


DEFAULT_MODEL_NAME = "qwen3-embedding:0.6b"
DEFAULT_MIN_TOKEN_COUNT = 50
DEFAULT_CHUNK_TOKEN_COUNT = 200
DEFAULT_EPS_LIST = (0.90, 0.92, 0.95)
DEFAULT_NCENTROIDS = 8
DEFAULT_KMEANS_NITER = 30
DEFAULT_SEED = 42
DEFAULT_MAX_DOCS_FOR_STAGE3 = 50


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
    matrix = np.asarray(vectors, dtype=np.float32)
    if matrix.size == 0:
        raise ValueError("Cannot average an empty list of vectors")
    return matrix.mean(axis=0).astype(np.float32).tolist()


def _sanitize_eps_value(eps: float) -> str:
    return f"{eps:.4f}".rstrip("0").rstrip(".").replace(".", "p")


def _connected_components(nodes: Sequence[str], edges: Dict[str, set[str]]) -> List[List[str]]:
    visited: set[str] = set()
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


def _kmeans_cluster(vectors: np.ndarray, ncentroids: int, kmeans_niter: int, seed: int) -> np.ndarray:
    if vectors.ndim != 2:
        raise ValueError("vectors must be a 2D matrix")
    n_docs, emb_dim = vectors.shape
    if n_docs == 0:
        return np.empty((0,), dtype=np.int64)

    ncentroids = max(1, min(ncentroids, n_docs))

    faiss_vectors = vectors.astype(np.float32, copy=True)
    faiss.normalize_L2(faiss_vectors)
    kmeans = faiss.Kmeans(
        emb_dim,
        ncentroids,
        niter=kmeans_niter,
        verbose=False,
        seed=seed,
        spherical=True,
        gpu=False,
    )
    kmeans.train(faiss_vectors)
    _, nearest = kmeans.index.search(faiss_vectors, 1)
    return nearest.reshape(-1).astype(np.int64)


def _build_cluster_graph(
    cluster_doc_ids: Sequence[str],
    sim_matrix: np.ndarray,
    eps: float,
    doc_order: Dict[str, int],
) -> Tuple[Dict[str, set[str]], Dict[str, str], set[str]]:
    edges: Dict[str, set[str]] = {doc_id: set() for doc_id in cluster_doc_ids}
    for i in range(len(cluster_doc_ids)):
        for j in range(i + 1, len(cluster_doc_ids)):
            if float(sim_matrix[i, j]) >= eps:
                left_doc_id = cluster_doc_ids[i]
                right_doc_id = cluster_doc_ids[j]
                edges[left_doc_id].add(right_doc_id)
                edges[right_doc_id].add(left_doc_id)

    components = _connected_components(cluster_doc_ids, edges)
    canonical_by_doc_id: Dict[str, str] = {}
    duplicate_doc_ids: set[str] = set()

    for component in components:
        canonical_doc_id = min(component, key=lambda item: doc_order[item])
        for doc_id in component:
            canonical_by_doc_id[doc_id] = canonical_doc_id
            if doc_id != canonical_doc_id:
                duplicate_doc_ids.add(doc_id)

    return edges, canonical_by_doc_id, duplicate_doc_ids


def run_semantic_deduplication(
    input_dir: Path,
    output_jsonl: Optional[Path] = None,
    output_summary: Optional[Path] = None,
    embedding_provider: Optional[EmbeddingProvider] = None,
    model_name: str = DEFAULT_MODEL_NAME,
    min_token_count: int = DEFAULT_MIN_TOKEN_COUNT,
    chunk_token_count: int = DEFAULT_CHUNK_TOKEN_COUNT,
    eps_list: Sequence[float] = DEFAULT_EPS_LIST,
    ncentroids: int = DEFAULT_NCENTROIDS,
    kmeans_niter: int = DEFAULT_KMEANS_NITER,
    seed: int = DEFAULT_SEED,
    max_docs_for_stage3: int = DEFAULT_MAX_DOCS_FOR_STAGE3,
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

    sorted_eps = sorted({float(eps) for eps in eps_list})
    if not sorted_eps:
        raise ValueError("eps_list must contain at least one epsilon")

    metadata_rows = _load_jsonl(metadata_path)
    metadata_by_doc_id = {row["doc_id"]: row for row in metadata_rows}

    stage_01_duplicates = {row["doc_id"] for row in _load_jsonl(stage_01_report_path) if row.get("is_duplicate", False)}
    stage_02_survivors = [
        row["doc_id"]
        for row in _load_jsonl(stage_02_report_path)
        if not row.get("is_duplicate", False) and row["doc_id"] not in stage_01_duplicates
    ]

    selected_doc_ids = sorted(stage_02_survivors)[:max_docs_for_stage3]
    doc_order = {doc_id: index for index, doc_id in enumerate(selected_doc_ids)}

    if embedding_provider is None:
        embedding_provider = OllamaEmbeddingProvider(model_name=model_name)

    token_counts: Dict[str, int] = {}
    vectors_by_doc_id: Dict[str, np.ndarray] = {}
    skipped_short_doc_ids: set[str] = set()

    for doc_id in selected_doc_ids:
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
        vectors_by_doc_id[doc_id] = np.asarray(_average_vectors(chunk_embeddings), dtype=np.float32)

    vector_doc_ids = [doc_id for doc_id in selected_doc_ids if doc_id in vectors_by_doc_id]

    if vector_doc_ids:
        vector_matrix = np.vstack([vectors_by_doc_id[doc_id] for doc_id in vector_doc_ids]).astype(np.float32)
        cluster_labels = _kmeans_cluster(vector_matrix, ncentroids=ncentroids, kmeans_niter=kmeans_niter, seed=seed)
    else:
        vector_matrix = np.empty((0, 0), dtype=np.float32)
        cluster_labels = np.empty((0,), dtype=np.int64)

    cluster_to_doc_ids: Dict[int, List[str]] = {}
    for idx, doc_id in enumerate(vector_doc_ids):
        cluster_id = int(cluster_labels[idx])
        cluster_to_doc_ids.setdefault(cluster_id, []).append(doc_id)

    doc_metrics: List[Dict[str, Any]] = []
    cluster_metrics: List[Dict[str, Any]] = []
    pair_edges: List[Dict[str, Any]] = []

    nn_doc_by_id: Dict[str, Optional[str]] = {doc_id: None for doc_id in selected_doc_ids}
    nn_sim_by_id: Dict[str, Optional[float]] = {doc_id: None for doc_id in selected_doc_ids}
    sim_to_centroid_by_id: Dict[str, Optional[float]] = {doc_id: None for doc_id in selected_doc_ids}
    semdedup_score_by_id: Dict[str, Optional[float]] = {doc_id: None for doc_id in selected_doc_ids}
    cluster_id_by_doc_id: Dict[str, Optional[int]] = {doc_id: None for doc_id in selected_doc_ids}

    canonical_by_doc_for_eps: Dict[float, Dict[str, str]] = {eps: {} for eps in sorted_eps}
    duplicate_doc_ids_for_eps: Dict[float, set[str]] = {eps: set() for eps in sorted_eps}
    candidate_pairs_for_eps: Dict[float, int] = {eps: 0 for eps in sorted_eps}

    for cluster_id, cluster_doc_ids in cluster_to_doc_ids.items():
        if not cluster_doc_ids:
            continue

        indices = [vector_doc_ids.index(doc_id) for doc_id in cluster_doc_ids]
        vectors = vector_matrix[indices]
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0.0] = 1.0
        vectors_norm = vectors / norms

        centroid = vectors_norm.mean(axis=0)
        centroid_norm = np.linalg.norm(centroid)
        if centroid_norm > 0:
            centroid = centroid / centroid_norm

        sim_to_centroid = vectors_norm @ centroid
        sim_matrix = vectors_norm @ vectors_norm.T

        for i, doc_id in enumerate(cluster_doc_ids):
            cluster_id_by_doc_id[doc_id] = cluster_id
            sim_to_centroid_by_id[doc_id] = float(sim_to_centroid[i])

            row_sims = sim_matrix[i].copy()
            row_sims[i] = -1.0
            best_index = int(np.argmax(row_sims)) if len(row_sims) > 1 else -1
            best_similarity = float(row_sims[best_index]) if best_index >= 0 else None

            if best_index >= 0 and best_similarity >= 0:
                nn_doc_by_id[doc_id] = cluster_doc_ids[best_index]
                nn_sim_by_id[doc_id] = best_similarity
                semdedup_score_by_id[doc_id] = best_similarity
            else:
                nn_doc_by_id[doc_id] = None
                nn_sim_by_id[doc_id] = None
                semdedup_score_by_id[doc_id] = 0.0

        for i in range(len(cluster_doc_ids)):
            for j in range(i + 1, len(cluster_doc_ids)):
                similarity = float(sim_matrix[i, j])
                triggered_eps = [eps for eps in sorted_eps if similarity >= eps]
                pair_edges.append(
                    {
                        "cluster_id": cluster_id,
                        "doc_id_a": cluster_doc_ids[i],
                        "doc_id_b": cluster_doc_ids[j],
                        "similarity": similarity,
                        "eps_triggered": ",".join(str(eps) for eps in triggered_eps),
                    }
                )

        cluster_summary: Dict[str, Any] = {
            "cluster_id": cluster_id,
            "cluster_size": len(cluster_doc_ids),
            "mean_sim": float(np.mean(sim_matrix)) if sim_matrix.size else 0.0,
            "p50_sim": float(np.percentile(sim_matrix, 50)) if sim_matrix.size else 0.0,
            "p90_sim": float(np.percentile(sim_matrix, 90)) if sim_matrix.size else 0.0,
            "std_sim": float(np.std(sim_matrix)) if sim_matrix.size else 0.0,
        }

        for eps in sorted_eps:
            edges, canonical_map, duplicate_doc_ids = _build_cluster_graph(cluster_doc_ids, sim_matrix, eps, doc_order)
            candidate_pairs_for_eps[eps] += sum(len(neighbors) for neighbors in edges.values()) // 2

            for doc_id, canonical_doc_id in canonical_map.items():
                canonical_by_doc_for_eps[eps][doc_id] = canonical_doc_id
            duplicate_doc_ids_for_eps[eps].update(duplicate_doc_ids)

            cluster_summary[f"kept_count_eps_{_sanitize_eps_value(eps)}"] = len(cluster_doc_ids) - len(duplicate_doc_ids)
            cluster_summary[f"pruned_count_eps_{_sanitize_eps_value(eps)}"] = len(duplicate_doc_ids)
            cluster_summary[f"prune_rate_eps_{_sanitize_eps_value(eps)}"] = (
                float(len(duplicate_doc_ids)) / len(cluster_doc_ids) if cluster_doc_ids else 0.0
            )

        cluster_metrics.append(cluster_summary)

    selected_default_eps = sorted_eps[-1]
    report_rows: List[Dict[str, Any]] = []

    for doc_id in selected_doc_ids:
        match_type = "semdedup_faiss_kmeans"
        if doc_id in skipped_short_doc_ids:
            match_type = "skipped_short_document"

        canonical_doc_id = canonical_by_doc_for_eps[selected_default_eps].get(doc_id, doc_id)
        is_duplicate = doc_id in duplicate_doc_ids_for_eps[selected_default_eps]

        report_rows.append(
            {
                "doc_id": doc_id,
                "canonical_doc_id": canonical_doc_id,
                "is_duplicate": is_duplicate,
                "match_type": match_type,
                "candidate_doc_id": nn_doc_by_id.get(doc_id),
                "semantic_similarity": round(nn_sim_by_id[doc_id], 6) if nn_sim_by_id[doc_id] is not None else None,
                "threshold": selected_default_eps,
            }
        )

        doc_metric_row: Dict[str, Any] = {
            "doc_id": doc_id,
            "cluster_id": cluster_id_by_doc_id.get(doc_id),
            "cluster_size": len(cluster_to_doc_ids.get(cluster_id_by_doc_id.get(doc_id), []))
            if cluster_id_by_doc_id.get(doc_id) is not None
            else 1,
            "token_count": token_counts.get(doc_id),
            "sim_to_centroid": sim_to_centroid_by_id.get(doc_id),
            "nearest_neighbor_doc_id": nn_doc_by_id.get(doc_id),
            "nearest_neighbor_similarity": nn_sim_by_id.get(doc_id),
            "semdedup_score": semdedup_score_by_id.get(doc_id),
            "canonical_doc_id": canonical_doc_id,
        }
        for eps in sorted_eps:
            key = f"keep_at_eps_{_sanitize_eps_value(eps)}"
            doc_metric_row[key] = doc_id not in duplicate_doc_ids_for_eps[eps]
        doc_metrics.append(doc_metric_row)

    with open(output_jsonl, "w", encoding="utf-8") as handle:
        for row in report_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    doc_metrics_df = pd.DataFrame(doc_metrics).sort_values("doc_id") if doc_metrics else pd.DataFrame()
    cluster_metrics_df = pd.DataFrame(cluster_metrics).sort_values("cluster_id") if cluster_metrics else pd.DataFrame()
    pair_edges_df = pd.DataFrame(pair_edges)

    doc_metrics_path = input_dir / "dedup_stage_03_doc_metrics.parquet"
    cluster_metrics_path = input_dir / "dedup_stage_03_cluster_metrics.parquet"
    pair_edges_path = input_dir / "dedup_stage_03_pair_edges.parquet"
    run_summary_path = input_dir / "dedup_stage_03_run_summary.json"

    doc_metrics_df.to_parquet(doc_metrics_path, index=False)
    cluster_metrics_df.to_parquet(cluster_metrics_path, index=False)
    pair_edges_df.to_parquet(pair_edges_path, index=False)

    per_epsilon_summary: Dict[str, Dict[str, Any]] = {}
    for eps in sorted_eps:
        eps_key = str(eps)
        kept_doc_ids = [doc_id for doc_id in selected_doc_ids if doc_id not in duplicate_doc_ids_for_eps[eps]]
        manifest_path = input_dir / f"dedup_stage_03_keep_manifest_eps_{_sanitize_eps_value(eps)}.txt"
        manifest_path.write_text("\n".join(kept_doc_ids) + ("\n" if kept_doc_ids else ""), encoding="utf-8")

        per_epsilon_summary[eps_key] = {
            "documents_scanned": len(selected_doc_ids),
            "documents_skipped_short": len(skipped_short_doc_ids),
            "candidate_pairs_evaluated": candidate_pairs_for_eps[eps],
            "duplicate_documents": len(duplicate_doc_ids_for_eps[eps]),
            "kept_documents": len(kept_doc_ids),
            "prune_rate": (float(len(duplicate_doc_ids_for_eps[eps])) / len(selected_doc_ids)) if selected_doc_ids else 0.0,
            "manifest_path": str(manifest_path),
        }

    summary = {
        "documents_scanned": len(selected_doc_ids),
        "documents_skipped_short": len(skipped_short_doc_ids),
        "candidate_pairs_evaluated": candidate_pairs_for_eps[selected_default_eps],
        "duplicate_documents": len(duplicate_doc_ids_for_eps[selected_default_eps]),
        "duplicate_groups": len({
            canonical_by_doc_for_eps[selected_default_eps].get(doc_id, doc_id)
            for doc_id in selected_doc_ids
            if doc_id in duplicate_doc_ids_for_eps[selected_default_eps]
        }),
        "model_name": model_name,
        "top_k": None,
        "threshold": selected_default_eps,
        "default_epsilon": selected_default_eps,
        "eps_list": sorted_eps,
        "ncentroids": ncentroids,
        "kmeans_niter": kmeans_niter,
        "seed": seed,
        "max_docs_for_stage3": max_docs_for_stage3,
        "selected_documents_count": len(selected_doc_ids),
        "total_stage_2_survivors": len(stage_02_survivors),
        "selection_strategy": "sorted_doc_id_first_n",
        "selected_doc_ids": selected_doc_ids,
        "artifacts": {
            "doc_metrics": str(doc_metrics_path),
            "cluster_metrics": str(cluster_metrics_path),
            "pair_edges": str(pair_edges_path),
            "run_summary": str(run_summary_path),
        },
        "per_epsilon": per_epsilon_summary,
    }

    with open(output_summary, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, ensure_ascii=False)

    run_summary = {
        "config": {
            "model_name": model_name,
            "min_token_count": min_token_count,
            "chunk_token_count": chunk_token_count,
            "eps_list": sorted_eps,
            "ncentroids": ncentroids,
            "kmeans_niter": kmeans_niter,
            "seed": seed,
            "max_docs_for_stage3": max_docs_for_stage3,
        },
        "selection": {
            "strategy": "sorted_doc_id_first_n",
            "selected_count": len(selected_doc_ids),
            "total_stage_2_survivors": len(stage_02_survivors),
            "selected_doc_ids": selected_doc_ids,
        },
        "metrics": per_epsilon_summary,
    }
    run_summary_path.write_text(json.dumps(run_summary, indent=2, ensure_ascii=False), encoding="utf-8")

    return summary
