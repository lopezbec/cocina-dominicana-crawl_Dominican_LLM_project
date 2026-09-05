import json
import urllib.error
from pathlib import Path
from typing import Dict, List, Sequence

import pytest

from dominican_llm_processor.deduplication.stage_01_exact import run_exact_deduplication
from dominican_llm_processor.deduplication.stage_02_near_duplicate import run_near_duplicate_deduplication
from dominican_llm_processor.deduplication import stage_03_semantic
from dominican_llm_processor.deduplication.stage_03_semantic import run_semantic_deduplication


class FakeEmbeddingProvider:
    def __init__(self, mapping: Dict[str, List[float]]) -> None:
        self.mapping = mapping

    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        return [self.mapping[text.strip()] for text in texts]


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


def _run_stage_01_and_02(base_dir: Path, near_threshold: float = 0.95) -> tuple[list[dict], list[dict]]:
    stage_01_rows = run_exact_deduplication(base_dir)["rows"]
    stage_02_rows = run_near_duplicate_deduplication(base_dir, stage_01_rows, threshold=near_threshold)["rows"]
    return stage_01_rows, stage_02_rows


def test_stage_03_detects_semantic_duplicates_with_temp_txts(tmp_path: Path) -> None:
    text_a = "casa hogar vivienda barrio familia techo ventana puerta cocina descanso noche"
    text_b = "residencia morada domicilio vecindario parientes tejado ventanal entrada fogon reposo tarde"

    _write_processed_corpus(
        tmp_path,
        [
            {"doc_id": "0001", "filename": "0001.txt", "text": text_a},
            {"doc_id": "0002", "filename": "0002.txt", "text": text_b},
        ],
    )
    stage_01_rows, stage_02_rows = _run_stage_01_and_02(tmp_path)

    provider = FakeEmbeddingProvider({text_a: [1.0, 0.0], text_b: [0.999, 0.001]})
    result = run_semantic_deduplication(
        tmp_path,
        stage_01_rows,
        stage_02_rows,
        embedding_provider=provider,
        min_token_count=5,
        chunk_token_count=100,
        eps_list=[0.95],
        ncentroids=1,
        kmeans_niter=5,
        seed=7,
        max_docs_for_stage3=50,
    )
    summary = result["summary"]

    assert summary["duplicate_documents"] == 1
    rows = result["rows"]
    rows_by_id = {row["doc_id"]: row for row in rows}
    assert rows_by_id["0002"]["is_duplicate"] is True
    assert rows_by_id["0002"]["canonical_doc_id"] == "0001"


def test_stage_03_is_deterministic_with_fixed_seed(tmp_path: Path) -> None:
    docs = []
    embedding_map: Dict[str, List[float]] = {}
    for i in range(1, 8):
        doc_id = f"{i:04d}"
        text = f"documento semantico {i} " + "palabra " * 60
        docs.append({"doc_id": doc_id, "filename": f"{doc_id}.txt", "text": text})
        embedding_map[text.strip()] = [1.0, i / 100.0]

    _write_processed_corpus(tmp_path, docs)
    stage_01_rows, stage_02_rows = _run_stage_01_and_02(tmp_path)

    provider = FakeEmbeddingProvider(embedding_map)
    result_1 = run_semantic_deduplication(
        tmp_path,
        stage_01_rows,
        stage_02_rows,
        embedding_provider=provider,
        min_token_count=10,
        chunk_token_count=100,
        eps_list=[0.90, 0.95],
        ncentroids=2,
        kmeans_niter=10,
        seed=42,
        max_docs_for_stage3=50,
    )
    first_rows = result_1["rows"]

    result_2 = run_semantic_deduplication(
        tmp_path,
        stage_01_rows,
        stage_02_rows,
        embedding_provider=provider,
        min_token_count=10,
        chunk_token_count=100,
        eps_list=[0.90, 0.95],
        ncentroids=2,
        kmeans_niter=10,
        seed=42,
        max_docs_for_stage3=50,
    )
    second_rows = result_2["rows"]

    assert result_1["summary"]["duplicate_documents"] == result_2["summary"]["duplicate_documents"]
    assert first_rows == second_rows


def test_stage_03_epsilon_monotonicity(tmp_path: Path) -> None:
    text_a = "tema uno " + "palabra " * 80
    text_b = "tema dos " + "palabra " * 80
    text_c = "tema tres " + "palabra " * 80

    _write_processed_corpus(
        tmp_path,
        [
            {"doc_id": "0001", "filename": "0001.txt", "text": text_a},
            {"doc_id": "0002", "filename": "0002.txt", "text": text_b},
            {"doc_id": "0003", "filename": "0003.txt", "text": text_c},
        ],
    )
    stage_01_rows, stage_02_rows = _run_stage_01_and_02(tmp_path)

    provider = FakeEmbeddingProvider(
        {
            text_a.strip(): [1.0, 0.0],
            text_b.strip(): [0.995, 0.005],
            text_c.strip(): [0.6, 0.8],
        }
    )

    summary = run_semantic_deduplication(
        tmp_path,
        stage_01_rows,
        stage_02_rows,
        embedding_provider=provider,
        min_token_count=10,
        chunk_token_count=100,
        eps_list=[0.90, 0.95, 0.99],
        ncentroids=1,
        kmeans_niter=8,
        seed=9,
        max_docs_for_stage3=50,
    )["summary"]

    per_eps = summary["per_epsilon"]
    dup_090 = per_eps["0.9"]["duplicate_documents"]
    dup_095 = per_eps["0.95"]["duplicate_documents"]
    dup_099 = per_eps["0.99"]["duplicate_documents"]
    assert dup_090 >= dup_095 >= dup_099


def test_stage_03_excludes_previous_stage_duplicates(tmp_path: Path) -> None:
    repeated = "texto repetido " * 70
    unique = "contenido unico " * 70
    _write_processed_corpus(
        tmp_path,
        [
            {"doc_id": "0001", "filename": "0001.txt", "text": repeated},
            {"doc_id": "0002", "filename": "0002.txt", "text": repeated},
            {"doc_id": "0003", "filename": "0003.txt", "text": unique},
        ],
    )
    stage_01_rows, stage_02_rows = _run_stage_01_and_02(tmp_path)

    provider = FakeEmbeddingProvider({repeated.strip(): [1.0, 0.0], unique.strip(): [0.0, 1.0]})
    summary = run_semantic_deduplication(
        tmp_path,
        stage_01_rows,
        stage_02_rows,
        embedding_provider=provider,
        min_token_count=10,
        chunk_token_count=200,
        eps_list=[0.95],
        ncentroids=1,
        kmeans_niter=5,
        seed=11,
        max_docs_for_stage3=50,
    )["summary"]

    assert summary["documents_scanned"] == 2
    selected = set(summary["selected_doc_ids"])
    assert selected == {"0001", "0003"}


def test_stage_03_returns_eda_diagnostics_and_schema(tmp_path: Path) -> None:
    docs = []
    embedding_map: Dict[str, List[float]] = {}
    for i in range(1, 6):
        doc_id = f"{i:04d}"
        text = f"dataset pieza {i} " + "token " * 70
        docs.append({"doc_id": doc_id, "filename": f"{doc_id}.txt", "text": text})
        embedding_map[text.strip()] = [1.0, i / 10.0]

    _write_processed_corpus(tmp_path, docs)
    stage_01_rows, stage_02_rows = _run_stage_01_and_02(tmp_path)

    result = run_semantic_deduplication(
        tmp_path,
        stage_01_rows,
        stage_02_rows,
        embedding_provider=FakeEmbeddingProvider(embedding_map),
        min_token_count=10,
        chunk_token_count=100,
        eps_list=[0.9, 0.95],
        ncentroids=2,
        kmeans_niter=10,
        seed=42,
        max_docs_for_stage3=50,
    )

    assert not (tmp_path / "dedup_stage_03_doc_metrics.parquet").exists()
    assert not (tmp_path / "dedup_stage_03_cluster_metrics.parquet").exists()
    assert not (tmp_path / "dedup_stage_03_pair_edges.parquet").exists()
    assert not (tmp_path / "dedup_stage_03_run_summary.json").exists()
    assert not (tmp_path / "dedup_stage_03_keep_manifest_eps_0p9.txt").exists()
    assert not (tmp_path / "dedup_stage_03_keep_manifest_eps_0p95.txt").exists()

    doc_metrics = result["diagnostics"]["doc_metrics"]
    expected_doc_columns = {
        "doc_id",
        "cluster_id",
        "cluster_size",
        "token_count",
        "sim_to_centroid",
        "nearest_neighbor_doc_id",
        "nearest_neighbor_similarity",
        "semdedup_score",
        "canonical_doc_id",
        "keep_at_eps_0p9",
        "keep_at_eps_0p95",
    }
    assert expected_doc_columns.issubset(set(doc_metrics[0]))

    summary = result["summary"]
    assert "per_epsilon" in summary
    assert "0.9" in summary["per_epsilon"]


def test_stage_03_subsamples_to_50_docs_deterministically(tmp_path: Path) -> None:
    docs = []
    embedding_map: Dict[str, List[float]] = {}

    for i in range(1, 61):
        doc_id = f"{i:04d}"
        text = f"contenido doc {i} " + "palabra " * 60
        docs.append({"doc_id": doc_id, "filename": f"{doc_id}.txt", "text": text})
        embedding_map[text.strip()] = [1.0, i / 1000.0]

    _write_processed_corpus(tmp_path, docs)
    stage_01_rows, stage_02_rows = _run_stage_01_and_02(tmp_path)

    summary = run_semantic_deduplication(
        tmp_path,
        stage_01_rows,
        stage_02_rows,
        embedding_provider=FakeEmbeddingProvider(embedding_map),
        min_token_count=10,
        chunk_token_count=100,
        eps_list=[0.95],
        ncentroids=5,
        kmeans_niter=10,
        seed=1,
        max_docs_for_stage3=50,
    )["summary"]

    assert summary["documents_scanned"] == 50
    assert summary["selected_documents_count"] == 50
    assert summary["total_stage_2_survivors"] == 60
    assert summary["selected_doc_ids"][0] == "0001"
    assert summary["selected_doc_ids"][-1] == "0050"


def test_stage_03_defaults_to_full_survivor_selection(tmp_path: Path) -> None:
    docs = []
    embedding_map: Dict[str, List[float]] = {}
    for i in range(1, 16):
        doc_id = f"{i:04d}"
        text = f"texto completo {i} " + "token " * 40
        docs.append({"doc_id": doc_id, "filename": f"{doc_id}.txt", "text": text})
        embedding_map[text.strip()] = [1.0, i / 100.0]

    _write_processed_corpus(tmp_path, docs)
    stage_01_rows, stage_02_rows = _run_stage_01_and_02(tmp_path)

    summary = run_semantic_deduplication(
        tmp_path,
        stage_01_rows,
        stage_02_rows,
        embedding_provider=FakeEmbeddingProvider(embedding_map),
        min_token_count=10,
        chunk_token_count=100,
        eps_list=[0.95],
        ncentroids=2,
        kmeans_niter=10,
        seed=3,
    )["summary"]

    assert summary["documents_scanned"] == 15
    assert summary["selected_documents_count"] == 15
    assert summary["max_docs_for_stage3"] is None
    assert summary["selection_strategy"] == "sorted_doc_id_full_or_first_n"


def test_stage_03_failfast_when_ollama_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    text = "contenido de prueba " * 80
    _write_processed_corpus(tmp_path, [{"doc_id": "0001", "filename": "0001.txt", "text": text}])
    stage_01_rows, stage_02_rows = _run_stage_01_and_02(tmp_path)

    def _raise_urlerror(*args, **kwargs):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", _raise_urlerror)

    with pytest.raises(RuntimeError, match="Ollama endpoint unavailable"):
        run_semantic_deduplication(tmp_path, stage_01_rows, stage_02_rows, failfast_ollama=True)


def test_stage_03_failfast_when_model_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    text = "contenido de prueba " * 80
    _write_processed_corpus(tmp_path, [{"doc_id": "0001", "filename": "0001.txt", "text": text}])
    stage_01_rows, stage_02_rows = _run_stage_01_and_02(tmp_path)

    class _FakeResponse:
        def __init__(self, payload: str) -> None:
            self._payload = payload.encode("utf-8")

        def read(self):
            return self._payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

    def _fake_urlopen(request, timeout=0):
        url = getattr(request, "full_url", "")
        if str(url).endswith("/api/tags"):
            return _FakeResponse(json.dumps({"models": [{"name": "other-model:latest"}]}))
        raise AssertionError(f"Unexpected URL in test: {url}")

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)

    with pytest.raises(RuntimeError, match="not available"):
        run_semantic_deduplication(
            tmp_path,
            stage_01_rows,
            stage_02_rows,
            failfast_model=True,
            model_name="qwen3-embedding:0.6b",
        )


def test_stage_03_use_gpu_true_fails_without_gpu(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    text = "contenido de prueba " * 80
    _write_processed_corpus(tmp_path, [{"doc_id": "0001", "filename": "0001.txt", "text": text}])
    stage_01_rows, stage_02_rows = _run_stage_01_and_02(tmp_path)

    monkeypatch.setattr(stage_03_semantic.faiss, "get_num_gpus", lambda: 0, raising=False)

    provider = FakeEmbeddingProvider({text.strip(): [1.0, 0.0]})
    with pytest.raises(RuntimeError, match="GPU requested"):
        run_semantic_deduplication(tmp_path, stage_01_rows, stage_02_rows, embedding_provider=provider, use_gpu=True)


def test_stage_03_use_gpu_auto_falls_back_to_cpu(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    text = "contenido de prueba " * 80
    _write_processed_corpus(tmp_path, [{"doc_id": "0001", "filename": "0001.txt", "text": text}])
    stage_01_rows, stage_02_rows = _run_stage_01_and_02(tmp_path)

    monkeypatch.setattr(stage_03_semantic.faiss, "get_num_gpus", lambda: 0, raising=False)

    provider = FakeEmbeddingProvider({text.strip(): [1.0, 0.0]})
    summary = run_semantic_deduplication(
        tmp_path,
        stage_01_rows,
        stage_02_rows,
        embedding_provider=provider,
        use_gpu=None,
        chunk_token_count=5000,
    )["summary"]
    assert summary["faiss_mode"] == "cpu"
    assert summary["gpu_effective"] is False


def test_stage_03_real_ollama_embeddings_marks_semantic_pair(tmp_path: Path) -> None:
    """Integration test using real Ollama embeddings for confidence in production behavior."""
    text_a = ""
    text_a += "receta dominicana de arroz con pollo con sofrito de cebolla ajo y ajies. "
    text_a += "se cocina el arroz con caldo y se mezcla con pollo guisado hasta quedar jugoso. "
    text_a += "se sirve con ensalada y aguacate. "
    text_a *= 8

    text_b = ""
    text_b += "preparacion de arroz con pollo estilo republica dominicana con sazon de cebolla ajo y pimientos. "
    text_b += "el arroz se cuece en caldo y luego se integra el pollo guisado para un plato humedo y sabroso. "
    text_b += "acompanar con ensalada verde y aguacate. "
    text_b *= 8

    text_c = ""
    text_c += "informe tecnico sobre series de tiempo economicas, estacionalidad y autocorrelacion en modelos arima. "
    text_c += "se discuten metricas de validacion y estimacion de parametros con enfoque estadistico. "
    text_c *= 8

    _write_processed_corpus(
        tmp_path,
        [
            {"doc_id": "0001", "filename": "0001.txt", "text": text_a},
            {"doc_id": "0002", "filename": "0002.txt", "text": text_b},
            {"doc_id": "0003", "filename": "0003.txt", "text": text_c},
        ],
    )
    stage_01_rows, stage_02_rows = _run_stage_01_and_02(tmp_path)

    try:
        result = run_semantic_deduplication(
            tmp_path,
            stage_01_rows,
            stage_02_rows,
            min_token_count=20,
            chunk_token_count=120,
            eps_list=[0.80, 0.90],
            ncentroids=1,
            kmeans_niter=10,
            seed=42,
            max_docs_for_stage3=50,
        )
    except RuntimeError as exc:
        if "Ollama" in str(exc):
            pytest.skip(f"Ollama embedding backend unavailable: {exc}")
        raise

    summary = result["summary"]
    rows = result["rows"]
    rows_by_id = {row["doc_id"]: row for row in rows}

    pair_similarity = rows_by_id["0001"]["semantic_similarity"]
    control_similarity = rows_by_id["0003"]["semantic_similarity"]

    # Real-model confidence check: semantic pair must be clearly closer than unrelated control.
    assert pair_similarity is not None
    assert control_similarity is not None
    assert pair_similarity > control_similarity + 0.45

    # The pair should be deduplicated at eps=0.80, and not at eps=0.90 for this model snapshot.
    assert summary["per_epsilon"]["0.8"]["duplicate_documents"] >= 1
    assert summary["per_epsilon"]["0.9"]["duplicate_documents"] == 0

    # Default output still uses highest epsilon and should keep unrelated text.
    assert rows_by_id["0003"]["is_duplicate"] is False
    assert summary["documents_scanned"] == 3


def test_stage_03_real_ollama_same_domain_different_semantics_not_collapsed(tmp_path: Path) -> None:
    """Hard case: same high-level AI domain, but distinct semantic intent/content."""
    deep_learning_text = ""
    deep_learning_text += "deep learning training pipeline for vision transformers with adamw, warmup, and cosine decay. "
    deep_learning_text += "focus on gradient stability, regularization, batch size scaling, and representation learning. "
    deep_learning_text += "evaluation tracks top1 accuracy, calibration error, and ablation of augmentation policies. "
    deep_learning_text *= 7

    predictive_ai_text = ""
    predictive_ai_text += "predictive ai workflow for business demand forecasting and churn risk scoring in production. "
    predictive_ai_text += "focus on feature freshness, drift monitoring, threshold tuning, and decision support for operations. "
    predictive_ai_text += "evaluation tracks forecast bias, service levels, intervention costs, and weekly retraining cadence. "
    predictive_ai_text *= 7

    nlp_text = ""
    nlp_text += "natural language processing stack for retrieval augmented generation with chunking, indexing, and reranking. "
    nlp_text += "focus on query rewriting, context window budgeting, and answer grounding for user support tasks. "
    nlp_text += "evaluation tracks hit rate, citation precision, latency, and failure modes in ambiguous questions. "
    nlp_text *= 7

    _write_processed_corpus(
        tmp_path,
        [
            {"doc_id": "0101", "filename": "0101.txt", "text": deep_learning_text},
            {"doc_id": "0102", "filename": "0102.txt", "text": predictive_ai_text},
            {"doc_id": "0103", "filename": "0103.txt", "text": nlp_text},
        ],
    )
    stage_01_rows, stage_02_rows = _run_stage_01_and_02(tmp_path)

    try:
        result = run_semantic_deduplication(
            tmp_path,
            stage_01_rows,
            stage_02_rows,
            min_token_count=20,
            chunk_token_count=120,
            eps_list=[0.80, 0.90],
            ncentroids=1,
            kmeans_niter=10,
            seed=42,
            max_docs_for_stage3=50,
        )
    except RuntimeError as exc:
        if "Ollama" in str(exc):
            pytest.skip(f"Ollama embedding backend unavailable: {exc}")
        raise

    summary = result["summary"]
    rows = result["rows"]
    rows_by_id = {row["doc_id"]: row for row in rows}

    # At strict epsilon (0.90 default output), same-domain but different tasks should stay distinct.
    assert rows_by_id["0101"]["is_duplicate"] is False
    assert rows_by_id["0102"]["is_duplicate"] is False
    assert rows_by_id["0103"]["is_duplicate"] is False

    # Confidence guard: ensure the run did not collapse the set at any tested epsilon.
    assert summary["per_epsilon"]["0.8"]["duplicate_documents"] == 0
    assert summary["per_epsilon"]["0.9"]["duplicate_documents"] == 0
