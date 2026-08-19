import json
from pathlib import Path
from typing import Dict, List, Sequence

from dominican_llm_scraper.core.processor.deduplication.stage_01_exact import run_exact_deduplication
from dominican_llm_scraper.core.processor.deduplication.stage_02_near_duplicate import run_near_duplicate_deduplication
from dominican_llm_scraper.core.processor.deduplication.stage_03_semantic import (
    _normalize_text,
    _tokenize,
    run_semantic_deduplication,
)
from dominican_llm_scraper.core.processor.deduplication.stage_04_sentence_spans import run_sentence_span_deduplication


class FakeEmbeddingProvider:
    def __init__(self, mapping: Dict[str, List[float]]) -> None:
        self.mapping = mapping

    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        return [self.mapping[text.strip()] for text in texts]


def _write_processed_corpus(base_dir: Path, documents: list[dict]) -> None:
    with open(base_dir / "metadata_plaintext.jsonl", "w", encoding="utf-8") as metadata_handle:
        for document in documents:
            (base_dir / document["filename"]).write_text(document["text"], encoding="utf-8")
            metadata_handle.write(
                json.dumps(
                    {
                        "doc_id": document["doc_id"],
                        "filename": document["filename"],
                        "title": document.get("title", ""),
                        "url": document.get("url", ""),
                        "domain": document.get("domain", "example.com"),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )


def _stage_rows(doc_ids: list[str]) -> list[dict]:
    return [{"doc_id": doc_id, "canonical_doc_id": doc_id, "is_duplicate": False} for doc_id in doc_ids]


def _pair_edges(pairs: list[tuple[str, str, float]]) -> list[dict]:
    return [{"doc_id_a": left, "doc_id_b": right, "similarity": similarity} for left, right, similarity in pairs]


def test_stage_04_detects_exact_three_sentence_span(tmp_path: Path) -> None:
    shared = "Primera oración compartida. Segunda oración compartida. Tercera oración compartida."
    _write_processed_corpus(
        tmp_path,
        [
            {"doc_id": "0001", "filename": "0001.txt", "text": f"Intro única. {shared} Cierre A."},
            {"doc_id": "0002", "filename": "0002.txt", "text": f"Apertura distinta. {shared} Cierre B."},
        ],
    )
    stage_01_rows = _stage_rows(["0001", "0002"])
    stage_02_rows = _stage_rows(["0001", "0002"])

    result = run_sentence_span_deduplication(
        tmp_path, stage_01_rows, stage_02_rows, _pair_edges([("0001", "0002", 0.93)]), candidate_epsilon=0.90
    )
    summary = result["summary"]
    rows = result["rows"]

    assert summary["duplicate_documents"] == 1
    assert rows == [
        {
            "doc_id": "0002",
            "canonical_doc_id": "0001",
            "is_duplicate": True,
            "match_type": "exact_3_sentence_span",
            "candidate_doc_id": "0001",
            "stage3_similarity": 0.93,
            "matched_span_hash": rows[0]["matched_span_hash"],
            "matched_span_text": shared,
            "matched_sentence_start": 1,
            "candidate_epsilon": 0.9,
            "span_sentence_count": 3,
        }
    ]


def test_stage_04_does_not_match_same_topic_different_wording(tmp_path: Path) -> None:
    _write_processed_corpus(
        tmp_path,
        [
            {
                "doc_id": "0001",
                "filename": "0001.txt",
                "text": "La IA predice demanda. El modelo aprende patrones. El equipo valida resultados.",
            },
            {
                "doc_id": "0002",
                "filename": "0002.txt",
                "text": "El aprendizaje profundo clasifica imágenes. La red ajusta pesos. La evaluación mide precisión.",
            },
        ],
    )
    stage_01_rows = _stage_rows(["0001", "0002"])
    stage_02_rows = _stage_rows(["0001", "0002"])

    result = run_sentence_span_deduplication(
        tmp_path, stage_01_rows, stage_02_rows, _pair_edges([("0001", "0002", 0.97)]), candidate_epsilon=0.90
    )
    summary = result["summary"]

    assert summary["duplicate_documents"] == 0
    assert result["rows"] == []


def test_stage_04_ignores_repeated_spans_inside_one_document(tmp_path: Path) -> None:
    repeated = "Uno repetido. Dos repetido. Tres repetido."
    _write_processed_corpus(
        tmp_path,
        [
            {"doc_id": "0001", "filename": "0001.txt", "text": f"{repeated} {repeated}"},
            {"doc_id": "0002", "filename": "0002.txt", "text": "Otra cosa. Sin copia. Nada igual."},
        ],
    )
    stage_01_rows = _stage_rows(["0001", "0002"])
    stage_02_rows = _stage_rows(["0001", "0002"])

    result = run_sentence_span_deduplication(
        tmp_path, stage_01_rows, stage_02_rows, _pair_edges([("0001", "0002", 0.96)]), candidate_epsilon=0.90
    )
    summary = result["summary"]

    assert summary["duplicate_documents"] == 0
    assert result["rows"] == []


def test_stage_04_matches_whitespace_only_differences(tmp_path: Path) -> None:
    _write_processed_corpus(
        tmp_path,
        [
            {"doc_id": "0001", "filename": "0001.txt", "text": "A uno. A dos. A tres."},
            {"doc_id": "0002", "filename": "0002.txt", "text": "A uno.\n\nA   dos.\tA tres."},
        ],
    )
    stage_01_rows = _stage_rows(["0001", "0002"])
    stage_02_rows = _stage_rows(["0001", "0002"])

    result = run_sentence_span_deduplication(
        tmp_path, stage_01_rows, stage_02_rows, _pair_edges([("0001", "0002", 0.91)]), candidate_epsilon=0.90
    )
    summary = result["summary"]
    rows = result["rows"]

    assert summary["duplicate_documents"] == 1
    assert rows[0]["matched_span_text"] == "A uno. A dos. A tres."


def test_stage_04_keeps_punctuation_case_and_accents_exact(tmp_path: Path) -> None:
    _write_processed_corpus(
        tmp_path,
        [
            {"doc_id": "0001", "filename": "0001.txt", "text": "Árbol alto. Casa blanca. Niño juega."},
            {"doc_id": "0002", "filename": "0002.txt", "text": "Arbol alto. casa blanca. Niño juega!"},
        ],
    )
    stage_01_rows = _stage_rows(["0001", "0002"])
    stage_02_rows = _stage_rows(["0001", "0002"])

    result = run_sentence_span_deduplication(
        tmp_path, stage_01_rows, stage_02_rows, _pair_edges([("0001", "0002", 0.99)]), candidate_epsilon=0.90
    )
    summary = result["summary"]

    assert summary["duplicate_documents"] == 0
    assert result["rows"] == []


def test_stage_04_outputs_only_duplicate_cases(tmp_path: Path) -> None:
    shared = "S1. S2. S3."
    _write_processed_corpus(
        tmp_path,
        [
            {"doc_id": "0001", "filename": "0001.txt", "text": shared},
            {"doc_id": "0002", "filename": "0002.txt", "text": shared},
            {"doc_id": "0003", "filename": "0003.txt", "text": "D1. D2. D3."},
        ],
    )
    stage_01_rows = _stage_rows(["0001", "0002", "0003"])
    stage_02_rows = _stage_rows(["0001", "0002", "0003"])

    result = run_sentence_span_deduplication(
        tmp_path,
        stage_01_rows,
        stage_02_rows,
        _pair_edges([("0001", "0002", 0.94), ("0001", "0003", 0.95)]),
        candidate_epsilon=0.90,
    )
    summary = result["summary"]
    rows = result["rows"]

    assert summary["candidate_pairs_scanned"] == 2
    assert len(rows) == 1
    assert rows[0]["doc_id"] == "0002"


def test_stage_04_integrates_after_semantic_candidate_filter(tmp_path: Path) -> None:
    shared = "El arroz se lava con cuidado. El pollo se sazona temprano. El sofrito levanta el sabor."
    doc_a = f"Entrada A. {shared} Cierre A con detalles únicos."
    doc_b = f"Entrada B distinta. {shared} Cierre B con detalles propios."
    doc_c = "La inteligencia artificial predice la demanda. El modelo analiza patrones. La empresa evalúa escenarios."
    doc_d = "El aprendizaje profundo procesa imágenes. La red neuronal ajusta pesos. El laboratorio mide exactitud."
    docs = [
        {"doc_id": "0001", "filename": "0001.txt", "text": doc_a},
        {"doc_id": "0002", "filename": "0002.txt", "text": doc_b},
        {"doc_id": "0003", "filename": "0003.txt", "text": doc_c},
        {"doc_id": "0004", "filename": "0004.txt", "text": doc_d},
    ]
    _write_processed_corpus(tmp_path, docs)
    stage_01_rows = run_exact_deduplication(tmp_path)["rows"]
    stage_02_rows = run_near_duplicate_deduplication(tmp_path, stage_01_rows, threshold=0.95)["rows"]

    provider = FakeEmbeddingProvider(
        {
            " ".join(_tokenize(_normalize_text(doc_a))): [1.0, 0.0],
            " ".join(_tokenize(_normalize_text(doc_b))): [0.999, 0.001],
            " ".join(_tokenize(_normalize_text(doc_c))): [0.998, 0.002],
            " ".join(_tokenize(_normalize_text(doc_d))): [0.997, 0.003],
        }
    )
    semantic_result = run_semantic_deduplication(
        tmp_path,
        stage_01_rows,
        stage_02_rows,
        embedding_provider=provider,
        min_token_count=1,
        chunk_token_count=200,
        eps_list=[0.90],
        ncentroids=1,
        kmeans_niter=5,
        seed=42,
    )

    result = run_sentence_span_deduplication(
        tmp_path, stage_01_rows, stage_02_rows, semantic_result["pair_edges"], candidate_epsilon=0.90
    )
    summary = result["summary"]
    rows = result["rows"]

    assert summary["duplicate_documents"] == 1
    assert rows[0]["doc_id"] == "0002"
    assert rows[0]["canonical_doc_id"] == "0001"
    assert rows[0]["matched_span_text"] == shared
