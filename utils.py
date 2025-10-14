import json
import logging
import re
import time
from pathlib import Path
from typing import Dict, Any


def setup_canonical_logger(name: str, level: str = "INFO") -> logging.Logger:
    """Setup logger optimized for canonical log lines."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    if not logger.handlers:
        console_handler = logging.StreamHandler()
        formatter = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        console_handler.setFormatter(
            logging.Formatter(formatter)
        )

        file_handler = logging.FileHandler('scraping.log')
        file_handler.setFormatter(
            logging.Formatter(formatter)
        )

        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

    return logger


def log_canonical(logger: logging.Logger, event: str, **kwargs) -> None:
    """Log a canonical log line following Stripe pattern."""
    extras = {k: v for k, v in kwargs.items() if v is not None}

    message_parts = [event]
    for key, value in extras.items():
        if isinstance(value, str):
            message_parts.append(f'{key}="{value}"')
        else:
            message_parts.append(f'{key}={value}')

    canonical_message = ' '.join(message_parts)
    logger.info(canonical_message, extra=extras)


class PerformanceTimer:
    """Context manager for timing operations."""

    def __init__(self):
        self.start_time = None
        self.duration_ms = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            self.duration_ms = int((time.time() - self.start_time) * 1000)


def create_safe_filename(text: str, max_length: int = 100) -> str:
    """Create a safe filename from text."""
    safe_name = re.sub(r'[^\w\-_.]', '_', text)
    return safe_name[:max_length]


def save_json_file(data: Dict[str, Any], filepath: Path) -> None:
    """Save JSON data to a file."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
