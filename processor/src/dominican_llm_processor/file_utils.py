import re


def create_safe_filename(text: str, max_length: int = 100) -> str:
    """Create a filesystem-safe name from a URL slug."""
    safe_name = re.sub(r"[^\w\-_.]", "_", text)
    return safe_name[:max_length]
