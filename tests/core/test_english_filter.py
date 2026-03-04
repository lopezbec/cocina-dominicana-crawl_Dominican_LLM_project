import json
from pathlib import Path

from dominican_llm_scraper.core.processor import process_markdown_to_plain_text


def test_markdown_to_plain_text_basic() -> None:
    markdown = "# Titulo\n\nTexto con **negrita** y [enlace](https://ejemplo.com).\n\n-\n\n---"
    _meta, plain = process_markdown_to_plain_text(markdown)
    assert "Titulo" in plain
    assert "Texto con" in plain
    assert "negrita" in plain
    assert "enlace" in plain
    assert "---" not in plain
    assert "\n\n\n" not in plain


def test_generic_noise_removal_lines() -> None:
    markdown = "Saltar a la navegación principal\n\nIn English\n\nSALTAR A:\n\nmostrar ↓\n\nContenido"
    _meta, plain = process_markdown_to_plain_text(markdown)
    assert "Saltar a" not in plain
    assert "In English" not in plain
    assert "SALTAR A" not in plain
    assert "mostrar" not in plain
    assert "Contenido" not in plain


def test_english_filter_mixed_text() -> None:
    markdown = "Esta receta tiene rice and beans. OK, eso esta bien."
    _meta, plain = process_markdown_to_plain_text(markdown)
    assert "rice" not in plain
    assert "and" not in plain
    assert "beans" not in plain
    assert "OK" in plain
    assert "receta" in plain


def test_inline_punctuation_cleanup() -> None:
    markdown = "Por **Nombre**\n\n** - Revisado: hoy"
    _meta, plain = process_markdown_to_plain_text(markdown)
    assert "*" not in plain


def test_first_raw_to_processed_output() -> None:
    raw_dir = Path("data/raw")
    processed_dir = Path("data/processed")
    metadata_file = raw_dir / "metadata.jsonl"
    if not metadata_file.exists():
        return

    with open(metadata_file, "r", encoding="utf-8") as f:
        first_line = f.readline().strip()
    if not first_line:
        return

    meta = json.loads(first_line)
    doc_id = meta["doc_id"]
    domain = meta.get("domain", "unknown")
    url_slug = meta["url_slug"]

    md_filename = f"{doc_id}_{domain.replace('.', '_')}_{url_slug}.md"
    md_file = raw_dir / md_filename
    if not md_file.exists():
        return

    with open(md_file, "r", encoding="utf-8") as f:
        content = f.read()

    _meta, plain = process_markdown_to_plain_text(content)
    processed_dir.mkdir(parents=True, exist_ok=True)
    output_file = processed_dir / f"{doc_id}_{domain.replace('.', '_')}_{url_slug}.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(plain)
