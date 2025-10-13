from dataclasses import dataclass
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass
class ScrapingConfig:
    firecrawl_api_key: str
    base_url: str = "https://www.cocinadominicana.com"
    output_dir: str = "topics"
    delay_between_requests: float = 2.0
    max_retries: int = 3
    retry_backoff_factor: float = 2.0
    max_pages_per_section: int = 50
    timeout: int = 30
    user_agent: str = "Mozilla/5.0 (compatible; DominicanCuisineBot/1.0)"
    preserve_progress: bool = True
    
    @classmethod
    def from_env(cls) -> "ScrapingConfig":
        api_key = os.getenv("FIRECRAWL_API_KEY")
        if not api_key:
            raise ValueError("FIRECRAWL_API_KEY environment variable is required")
        return cls(firecrawl_api_key=api_key)

SECTIONS = {
    "cultura-y-origenes": {
        "url": "/cultura/herencia",
        "display_name": "Cultura y Orígenes"
    },
    "costumbres-y-tradiciones": {
        "url": "/cultura/tradiciones-costumbres", 
        "display_name": "Costumbres y Tradiciones"
    },
    "festividades-y-celebraciones": {
        "url": "/cultura/celebraciones",
        "display_name": "Festividades y Celebraciones"
    },
    "en-comparacion": {
        "url": "/cultura/versus",
        "display_name": "En Comparación"
    }
}