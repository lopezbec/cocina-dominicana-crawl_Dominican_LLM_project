from pathlib import Path

from dominican_llm_processor.cli import main
from dominican_llm_processor.config_loader import PROJECT_DIR, load_config, resolve_project_path


def test_default_config_connects_crawler_raw_data_to_processor_output() -> None:
    config = load_config()

    assert resolve_project_path(config["input_dir"]) == (PROJECT_DIR.parent / "crawler" / "data" / "raw").resolve()
    assert resolve_project_path(config["output_dir"]) == (PROJECT_DIR / "data" / "processed").resolve()
    assert config["min_content_length"] == 50


def test_processor_cli_rejects_missing_input_directory(tmp_path: Path) -> None:
    missing = tmp_path / "missing"

    assert main(["process", "--input", str(missing)]) == 1
