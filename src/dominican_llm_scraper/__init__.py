"""Dominican LLM Scraper - Web scraper for collecting Dominican Spanish dialect data for LLM training."""

__version__ = "0.2.0"

from dominican_llm_scraper.core.config_loader import load_config, SiteConfig
from dominican_llm_scraper.core.crawler import Crawler

__all__ = ["load_config", "SiteConfig", "Crawler", "__version__"]
