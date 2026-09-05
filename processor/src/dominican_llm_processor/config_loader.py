from pathlib import Path
from typing import Any, Dict

import yaml


PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_DIR / "config" / "config.yml"


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    """Load processor settings from YAML."""
    if not path.is_file():
        raise FileNotFoundError(f"Processor configuration file not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    if not isinstance(config, dict):
        raise ValueError(f"Processor configuration must be a YAML object: {path}")
    return config


def resolve_project_path(value: str) -> Path:
    """Resolve a configured path relative to the processor project."""
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (PROJECT_DIR / path).resolve()
