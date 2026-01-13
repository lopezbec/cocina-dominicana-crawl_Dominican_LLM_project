import os
import re
import yaml
import requests
from pathlib import Path
from typing import Dict, Any, Optional
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()


class SiteConfig:
    def __init__(self, config_dict: Dict[str, Any]):
        self._config = config_dict

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            return object.__getattribute__(self, name)

        value = self._config.get(name)
        if isinstance(value, dict):
            return SiteConfig(value)
        return value

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self._config[key]

    def to_dict(self) -> Dict[str, Any]:
        return self._config


def get_domain_directory(domain: str) -> str:
    return domain.replace(".", "_")


def get_available_sites() -> list[str]:
    sites_dir = Path("config/sites")
    if not sites_dir.exists():
        return []

    sites = []
    for item in sites_dir.iterdir():
        if item.is_dir() and not item.name.startswith("_"):
            sites.append(item.name.replace("_", "."))

    return sorted(sites)


def validate_crawl_domain() -> str:
    domain = os.getenv("CRAWL_DOMAIN")

    if not domain:
        available_sites = get_available_sites()
        error_msg = "\n" + "=" * 70 + "\n"
        error_msg += "ERROR: CRAWL_DOMAIN environment variable not set\n"
        error_msg += "=" * 70 + "\n\n"
        error_msg += "The CRAWL_DOMAIN environment variable is required.\n\n"
        error_msg += "Usage:\n"
        error_msg += "  CRAWL_DOMAIN=example.com make crawl\n"
        error_msg += "  CRAWL_DOMAIN=example.com uv run scraper scrape-all\n\n"

        if available_sites:
            error_msg += "Available sites:\n"
            for site in available_sites:
                error_msg += f"  - {site}\n"
        else:
            error_msg += "No sites configured yet. Create one with:\n"
            error_msg += "  make setup-site DOMAIN=example.com\n"

        error_msg += "\n" + "=" * 70 + "\n"
        raise ValueError(error_msg)

    return domain


def validate_domain_reachable(domain: str, timeout: int = 5) -> None:
    """
    Validate that the domain is reachable via HTTPS.
    Fails fast with clear error if domain is unreachable.

    Args:
        domain: The domain to validate (e.g., 'www.example.com')
        timeout: Request timeout in seconds

    Raises:
        RuntimeError: If domain is unreachable (404, timeout, connection error, etc.)
    """
    base_url = f"https://{domain}"

    # Use a proper user-agent to avoid being blocked
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        # Try HEAD request first (faster)
        response = requests.head(base_url, timeout=timeout, allow_redirects=True, headers=headers)

        # If HEAD returns 403 or 405 (Method Not Allowed), try GET
        if response.status_code in [403, 405]:
            response = requests.get(base_url, timeout=timeout, allow_redirects=True, headers=headers, stream=True)
            # Close the connection immediately, we don't need the body
            response.close()

        if response.status_code >= 400:
            raise RuntimeError(
                f"\n{'=' * 70}\n"
                f"ERROR: Domain validation failed\n"
                f"{'=' * 70}\n\n"
                f"URL: {base_url}\n"
                f"HTTP Status: {response.status_code}\n\n"
                f"The domain returned an error. Please check:\n"
                f"  1. Domain is correct: CRAWL_DOMAIN={domain}\n"
                f"  2. Domain is accessible and online\n\n"
                f"{'=' * 70}\n"
            )

    except requests.exceptions.Timeout:
        raise RuntimeError(
            f"\n{'=' * 70}\n"
            f"ERROR: Domain validation failed\n"
            f"{'=' * 70}\n\n"
            f"URL: {base_url}\n"
            f"Error: Request timeout after {timeout} seconds\n\n"
            f"The domain is not responding. Please check:\n"
            f"  1. Domain is correct: CRAWL_DOMAIN={domain}\n"
            f"  2. Your internet connection\n"
            f"  3. Domain is online and accessible\n\n"
            f"{'=' * 70}\n"
        )

    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            f"\n{'=' * 70}\n"
            f"ERROR: Domain validation failed\n"
            f"{'=' * 70}\n\n"
            f"URL: {base_url}\n"
            f"Error: Connection failed\n\n"
            f"Cannot reach the domain. Please check:\n"
            f"  1. Domain is correct: CRAWL_DOMAIN={domain}\n"
            f"  2. Domain exists (check for typos)\n"
            f"  3. Your internet connection\n\n"
            f"{'=' * 70}\n"
        )

    except requests.exceptions.RequestException as e:
        raise RuntimeError(
            f"\n{'=' * 70}\n"
            f"ERROR: Domain validation failed\n"
            f"{'=' * 70}\n\n"
            f"URL: {base_url}\n"
            f"Error: {str(e)}\n\n"
            f"{'=' * 70}\n"
        )


def generate_url_patterns(base_url: str) -> list[str]:
    """Generate regex patterns to extract URLs from markdown.

    Patterns are simplified to capture only the full URL (no tuple).
    All URLs must have the full protocol (https://) to be valid.
    """
    patterns = [
        rf"\]({re.escape(base_url)}/[^)]+)\)",  # Markdown link: [text](URL)
        rf"\(({re.escape(base_url)}/[^)]+)\)",  # Parenthetical: (URL)
    ]

    return patterns


def merge_configs(global_config: Dict[str, Any], site_config: Dict[str, Any]) -> Dict[str, Any]:
    merged = global_config.copy()

    for key, value in site_config.items():
        if key not in merged:
            merged[key] = value
        elif isinstance(value, dict) and isinstance(merged[key], dict):
            merged[key] = merge_configs(merged[key], value)
        elif isinstance(value, list) and isinstance(merged[key], list):
            if key == "exclude_patterns" or key == "include_patterns":
                merged[key] = merged[key] + value
            else:
                merged[key] = value
        else:
            merged[key] = value

    return merged


def load_config() -> SiteConfig:
    domain = validate_crawl_domain()

    # Auto-generate base_url from domain (always HTTPS)
    base_url = f"https://{domain}"

    global_config_path = Path("config/config.yml")
    if global_config_path.exists():
        with open(global_config_path, "r", encoding="utf-8") as f:
            global_config = yaml.safe_load(f) or {}
    else:
        global_config = {}

    # Get timeout from global config (default: 5 seconds)
    domain_validation_timeout = global_config.get("crawler", {}).get("domain_validation_timeout", 5)

    # Validate domain is reachable (fail fast)
    validate_domain_reachable(domain, timeout=domain_validation_timeout)

    domain_dir = get_domain_directory(domain)
    site_config_path = Path("config/sites") / domain_dir / "config.yml"

    if not site_config_path.exists():
        available_sites = get_available_sites()
        error_msg = "\n" + "=" * 70 + "\n"
        error_msg += f"ERROR: Site configuration not found for domain: {domain}\n"
        error_msg += "=" * 70 + "\n\n"
        error_msg += f"Expected configuration file: {site_config_path}\n\n"

        if available_sites:
            error_msg += "Available sites:\n"
            for site in available_sites:
                error_msg += f"  - {site}\n"
            error_msg += "\n"

        error_msg += "To create a new site configuration:\n"
        error_msg += f"  make setup-site DOMAIN={domain}\n"
        error_msg += "\n" + "=" * 70 + "\n"
        raise FileNotFoundError(error_msg)

    with open(site_config_path, "r", encoding="utf-8") as f:
        site_config = yaml.safe_load(f) or {}

    merged_config = merge_configs(global_config, site_config)

    merged_config["domain"] = domain
    merged_config["domain_slug"] = domain_dir
    merged_config["base_url"] = base_url  # Set auto-generated base_url

    # Generate URL patterns from auto-generated base_url
    auto_patterns = generate_url_patterns(base_url)
    if "filters" not in merged_config:
        merged_config["filters"] = {}
    if "include_patterns" not in merged_config["filters"]:
        merged_config["filters"]["include_patterns"] = []

    merged_config["_auto_url_patterns"] = auto_patterns

    return SiteConfig(merged_config)


def load_processing_patterns(domain: str) -> Optional[Dict[str, Any]]:
    domain_dir = get_domain_directory(domain)
    patterns_path = Path("config/sites") / domain_dir / "processing_patterns.yml"

    if not patterns_path.exists():
        return None

    with open(patterns_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
