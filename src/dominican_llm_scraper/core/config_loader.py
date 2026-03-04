import re
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()


# ============================================================================
# URL Configuration Management
# ============================================================================


def load_urls_config() -> List[Dict[str, Any]]:
    """Load URLs configuration from config/urls.yml."""
    urls_file = Path("config/urls.yml")

    if not urls_file.exists():
        raise FileNotFoundError(
            f"URLs configuration file not found: {urls_file}\nRun the migration script first: python migrate_config.py"
        )

    with open(urls_file, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    return config.get("urls", [])


def update_url_processed_status(url: str, processed: bool = True):
    """Update the processed status of a URL in config/urls.yml."""
    urls_file = Path("config/urls.yml")

    if not urls_file.exists():
        return

    with open(urls_file, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    urls = config.get("urls", [])

    for url_entry in urls:
        if url_entry.get("url") == url:
            url_entry["processed"] = processed
            break

    with open(urls_file, "w", encoding="utf-8") as f:
        # Preserve comments by reading original content
        with open(urls_file, "r", encoding="utf-8") as rf:
            lines = rf.readlines()
            comments = []
            for line in lines:
                if line.strip().startswith("#"):
                    comments.append(line)
                else:
                    break

        # Write comments back
        f.writelines(comments)
        if comments and not comments[-1].endswith("\n\n"):
            f.write("\n")

        # Write updated config
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def get_domain_from_url(url: str) -> str:
    """Extract domain from URL."""
    parsed = urlparse(url)
    domain = parsed.netloc

    # Remove www. prefix if present
    if domain.startswith("www."):
        domain = domain[4:]

    return domain


# ============================================================================
# Site Configuration
# ============================================================================


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
    """Get list of configured sites from config/sites directory."""
    sites_dir = Path("config/sites")
    if not sites_dir.exists():
        return []

    sites = []
    for item in sites_dir.iterdir():
        if item.is_dir() and not item.name.startswith("_"):
            sites.append(item.name.replace("_", "."))

    return sorted(sites)


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
    """Merge site-specific config into global config.

    - Scalar values: site overrides global
    - Lists: site is appended to global (merged)
    - Dicts: recursively merged
    """
    merged = global_config.copy()

    for key, value in site_config.items():
        if key not in merged:
            merged[key] = value
        elif isinstance(value, dict) and isinstance(merged[key], dict):
            merged[key] = merge_configs(merged[key], value)
        elif isinstance(value, list) and isinstance(merged[key], list):
            # For lists, merge (append site-specific to global)
            merged[key] = merged[key] + value
        else:
            # Scalar values: site overrides global
            merged[key] = value

    return merged


def load_config(domain: Optional[str] = None) -> SiteConfig:
    """Load configuration for a specific domain or URL.

    Args:
        domain: Optional domain name or full URL. If URL provided (with http:// or https://),
                the protocol is preserved in base_url. If plain domain provided, defaults to https://.
                If not provided, returns global config only.

    Returns:
        SiteConfig object with merged configuration.
    """
    # Load global config
    global_config_path = Path("config/config.yml")
    if global_config_path.exists():
        with open(global_config_path, "r", encoding="utf-8") as f:
            global_config = yaml.safe_load(f) or {}
    else:
        global_config = {}

    if not domain:
        return SiteConfig(global_config)

    if domain.startswith("http://") or domain.startswith("https://"):
        parsed = urlparse(domain)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        domain = parsed.netloc
        if domain.startswith("www."):
            domain = domain[4:]
    else:
        # Plain domain provided - default to HTTPS
        base_url = f"https://{domain}"

    # Load site-specific config if exists
    domain_dir = get_domain_directory(domain)
    site_config_path = Path("config/sites") / domain_dir / "config.yml"

    if site_config_path.exists():
        with open(site_config_path, "r", encoding="utf-8") as f:
            site_config = yaml.safe_load(f) or {}
    else:
        site_config = {}

    # Merge configs
    merged_config = merge_configs(global_config, site_config)

    merged_config["domain"] = domain
    merged_config["domain_slug"] = domain_dir
    merged_config["base_url"] = base_url

    # Generate URL patterns from auto-generated base_url
    auto_patterns = generate_url_patterns(base_url)
    merged_config["_auto_url_patterns"] = auto_patterns

    return SiteConfig(merged_config)
