import json
import re
from pathlib import Path
from typing import Dict, Any


def create_safe_filename(text: str, max_length: int = 100) -> str:
    """Create a safe filename from text."""
    safe_name = re.sub(r"[^\w\-_.]", "_", text)
    return safe_name[:max_length]


def save_json_file(data: Dict[str, Any], filepath: Path) -> None:
    """Save JSON data to a file."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
