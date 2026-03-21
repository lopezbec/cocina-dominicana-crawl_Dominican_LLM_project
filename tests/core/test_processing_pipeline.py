from dominican_llm_scraper.core.processor.pipeline import process_markdown_to_plain_text


def test_pipe_table_is_converted_to_plain_text() -> None:
    markdown = """# Ficha

Antes de la tabla.

| Campo | Valor |
| --- | --- |
| Serie: | NA |
| Editora: | Editora Buho |

Despues de la tabla.
"""

    _meta, plain = process_markdown_to_plain_text(markdown)

    assert "Antes de la tabla." in plain
    assert "Serie:" in plain
    assert "NA" in plain
    assert "Editora:" in plain
    assert "Editora Buho" in plain
    assert "Despues de la tabla." in plain
    assert "| --- | --- |" not in plain
    assert "| Serie: | NA |" not in plain
