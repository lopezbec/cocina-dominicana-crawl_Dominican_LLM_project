import json
from pathlib import Path
from typing import Dict, List, Sequence

from dominican_llm_scraper.core.processor.deduplication.stage_01_exact import run_exact_deduplication
from dominican_llm_scraper.core.processor.deduplication.stage_02_near_duplicate import run_near_duplicate_deduplication
from dominican_llm_scraper.core.processor.deduplication.stage_03_semantic import run_semantic_deduplication


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


def _run_stage_01_and_02(base_dir: Path, near_threshold: float = 0.85) -> None:
    run_exact_deduplication(base_dir)
    run_near_duplicate_deduplication(base_dir, threshold=near_threshold)


def test_stage_03_detects_semantic_duplicates(tmp_path: Path) -> None:
    text_a = "casa hogar vivienda barrio familia techo ventana puerta cocina descanso noche"
    text_b = "residencia morada domicilio vecindario parientes tejado ventanal entrada fogon reposo tarde"
    _write_processed_corpus(
        tmp_path,
        [
            {"doc_id": "0001", "filename": "0001.txt", "text": text_a},
            {"doc_id": "0002", "filename": "0002.txt", "text": text_b},
        ],
    )
    _run_stage_01_and_02(tmp_path)

    provider = FakeEmbeddingProvider({text_a: [1.0, 0.0], text_b: [0.99, 0.01]})
    summary = run_semantic_deduplication(
        tmp_path,
        embedding_provider=provider,
        min_token_count=5,
        chunk_token_count=100,
        threshold=0.95,
    )

    assert summary["duplicate_documents"] == 1
    rows = [
        json.loads(line)
        for line in (tmp_path / "dedup_stage_03_semantic.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert rows[1]["canonical_doc_id"] == "0001"
    assert rows[1]["is_duplicate"] is True


def test_stage_03_preserves_same_topic_non_duplicates(tmp_path: Path) -> None:
    text_a = "mercado ahorro prestamo moneda interes reservas importacion indicadores balance crecimiento"
    text_b = "empresa salario consumo comercio empleo hogares impuestos produccion servicios demanda"
    _write_processed_corpus(
        tmp_path,
        [
            {"doc_id": "0001", "filename": "0001.txt", "text": text_a},
            {"doc_id": "0002", "filename": "0002.txt", "text": text_b},
        ],
    )
    _run_stage_01_and_02(tmp_path)

    provider = FakeEmbeddingProvider({text_a: [1.0, 0.0], text_b: [0.6, 0.8]})
    summary = run_semantic_deduplication(
        tmp_path,
        embedding_provider=provider,
        min_token_count=5,
        chunk_token_count=100,
        threshold=0.95,
    )

    assert summary["duplicate_documents"] == 0


def test_stage_03_ignores_previous_stage_duplicates(tmp_path: Path) -> None:
    repeated = "texto repetido " * 40
    unique = "contenido distinto " * 40
    _write_processed_corpus(
        tmp_path,
        [
            {"doc_id": "0001", "filename": "0001.txt", "text": repeated},
            {"doc_id": "0002", "filename": "0002.txt", "text": repeated},
            {"doc_id": "0003", "filename": "0003.txt", "text": unique},
        ],
    )
    _run_stage_01_and_02(tmp_path)

    provider = FakeEmbeddingProvider({unique.strip(): [1.0, 0.0], repeated.strip(): [1.0, 0.0]})
    summary = run_semantic_deduplication(
        tmp_path,
        embedding_provider=provider,
        min_token_count=5,
        chunk_token_count=1000,
        threshold=0.95,
    )

    assert summary["documents_scanned"] == 2
    rows = [
        json.loads(line)
        for line in (tmp_path / "dedup_stage_03_semantic.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert {row["doc_id"] for row in rows} == {"0001", "0003"}


def test_stage_03_skips_short_documents(tmp_path: Path) -> None:
    text_a = "texto corto uno dos"
    text_b = "texto corto tres cuatro"
    _write_processed_corpus(
        tmp_path,
        [
            {"doc_id": "0001", "filename": "0001.txt", "text": text_a},
            {"doc_id": "0002", "filename": "0002.txt", "text": text_b},
        ],
    )
    _run_stage_01_and_02(tmp_path)

    provider = FakeEmbeddingProvider({text_a: [1.0, 0.0], text_b: [1.0, 0.0]})
    summary = run_semantic_deduplication(
        tmp_path,
        embedding_provider=provider,
        min_token_count=20,
        chunk_token_count=100,
        threshold=0.95,
    )

    assert summary["documents_skipped_short"] == 2


def test_stage_03_builds_connected_components(tmp_path: Path) -> None:
    text_a = "selva rio montaña lluvia sendero arbol hoja viento barro piedra canto"
    text_b = "bosque arroyo colina neblina camino tronco rama brisa tierra roca eco"
    text_c = "jungla corriente pico tormenta vereda madera follaje aire suelo grava voz"
    _write_processed_corpus(
        tmp_path,
        [
            {"doc_id": "0001", "filename": "0001.txt", "text": text_a},
            {"doc_id": "0002", "filename": "0002.txt", "text": text_b},
            {"doc_id": "0003", "filename": "0003.txt", "text": text_c},
        ],
    )
    _run_stage_01_and_02(tmp_path)

    provider = FakeEmbeddingProvider({text_a: [1.0, 0.0], text_b: [0.96, 0.04], text_c: [0.92, 0.08]})
    summary = run_semantic_deduplication(
        tmp_path,
        embedding_provider=provider,
        min_token_count=5,
        chunk_token_count=100,
        threshold=0.9,
    )

    assert summary["duplicate_groups"] == 1
    rows = {
        row["doc_id"]: row
        for row in [
            json.loads(line)
            for line in (tmp_path / "dedup_stage_03_semantic.jsonl").read_text(encoding="utf-8").splitlines()
        ]
    }
    assert rows["0002"]["canonical_doc_id"] == "0001"
    assert rows["0003"]["canonical_doc_id"] == "0001"


def test_stage_03_writes_expected_report_files(tmp_path: Path) -> None:
    text_a = "pan horno masa levadura harina miga corteza calor bandeja cocina mesa"
    text_b = "hogaza fogon mezcla fermento trigo centro cubierta temperatura molde comedor"
    _write_processed_corpus(
        tmp_path,
        [
            {"doc_id": "0001", "filename": "0001.txt", "text": text_a},
            {"doc_id": "0002", "filename": "0002.txt", "text": text_b},
        ],
    )
    _run_stage_01_and_02(tmp_path)

    provider = FakeEmbeddingProvider({text_a: [1.0, 0.0], text_b: [0.99, 0.01]})
    run_semantic_deduplication(
        tmp_path,
        embedding_provider=provider,
        min_token_count=5,
        chunk_token_count=100,
        threshold=0.95,
    )

    summary = json.loads((tmp_path / "dedup_stage_03_semantic_summary.json").read_text(encoding="utf-8"))
    assert set(summary) == {
        "documents_scanned",
        "documents_skipped_short",
        "candidate_pairs_evaluated",
        "duplicate_documents",
        "duplicate_groups",
        "model_name",
        "top_k",
        "threshold",
    }
