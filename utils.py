import re
import os
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from slugify import slugify
from datetime import datetime
import logging

def setup_logging(level: str = "INFO") -> logging.Logger:
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('scraping.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def create_safe_filename(title: str) -> str:
    """Create a safe filename from article title."""
    return slugify(title, max_length=100)

def extract_word_count(text: str) -> int:
    """Extract word count from article text."""
    clean_text = re.sub(r'<[^>]+>', '', text)
    words = re.findall(r'\b\w+\b', clean_text)
    return len(words)

def extract_dates_from_text(text: str) -> Dict[str, Optional[str]]:
    """Extract publish and review dates from article text."""
    dates: Dict[str, Optional[str]] = {"publish_date": None, "review_date": None}
    
    publish_patterns = [
        r'Publicado:\s*([^.]+)',
        r'Published:\s*([^.]+)',
        r'Por.*?Publicado:\s*([^.]+)'
    ]
    
    review_patterns = [
        r'Revisado:\s*([^.]+)',
        r'Reviewed:\s*([^.]+)',
        r'Por.*?Revisado:\s*([^.]+)'
    ]
    
    for pattern in publish_patterns:
        match = re.search(pattern, text)
        if match:
            dates["publish_date"] = match.group(1).strip()
            break
    
    for pattern in review_patterns:
        match = re.search(pattern, text)
        if match:
            dates["review_date"] = match.group(1).strip()
            break
        
    return dates

def extract_recommendations(text: str) -> List[str]:
    """Extract any recommendations mentioned in the article."""
    recommendations = []
    
    rec_patterns = [
        r'recomendamos?\s+([^.]+)',
        r'sugerimos?\s+([^.]+)',
        r'aconsejamos?\s+([^.]+)',
        r'te recomiendo\s+([^.]+)',
        r'mi recomendación\s+([^.]+)'
    ]
    
    for pattern in rec_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        recommendations.extend([match.strip() for match in matches])
    
    return recommendations

def save_progress(progress_file: str, state: Dict[str, Any]) -> None:
    """Save progress state to file."""
    with open(progress_file, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def load_progress(progress_file: str) -> Dict[str, Any]:
    """Load progress state from file."""
    if os.path.exists(progress_file):
        try:
            with open(progress_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    return {}

def create_markdown_frontmatter(metadata: Dict[str, Any]) -> str:
    """Create YAML frontmatter for markdown files."""
    frontmatter = "---\n"
    for key, value in metadata.items():
        if isinstance(value, list):
            if value:
                frontmatter += f"{key}:\n"
                for item in value:
                    frontmatter += f"  - \"{item}\"\n"
            else:
                frontmatter += f"{key}: []\n"
        elif value is not None:
            if isinstance(value, str) and any(char in value for char in [':', '"', '\n']):
                frontmatter += f"{key}: \"{value}\"\n"
            else:
                frontmatter += f"{key}: {value}\n"
    frontmatter += "---\n\n"
    return frontmatter

def wait_with_backoff(attempt: int, base_delay: float = 1.0, backoff_factor: float = 2.0) -> None:
    """Wait with exponential backoff."""
    delay = base_delay * (backoff_factor ** attempt)
    time.sleep(delay)