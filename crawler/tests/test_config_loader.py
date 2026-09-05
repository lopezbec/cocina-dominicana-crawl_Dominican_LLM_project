from dominican_llm_scraper.core.config_loader import (
    generate_url_patterns,
    get_domain_from_url,
    merge_configs,
)


def test_get_domain_from_url_removes_www_prefix() -> None:
    assert get_domain_from_url("https://www.cocinadominicana.com/recetas") == "cocinadominicana.com"


def test_merge_configs_recurses_appends_lists_and_overrides_scalars() -> None:
    global_config = {
        "crawler": {"max_depth": 2, "delay_seconds": 5},
        "filters": {"exclude_patterns": ["feed"]},
    }
    site_config = {
        "crawler": {"delay_seconds": 1},
        "filters": {"exclude_patterns": ["comments"]},
    }

    merged = merge_configs(global_config, site_config)

    assert merged["crawler"] == {"max_depth": 2, "delay_seconds": 1}
    assert merged["filters"]["exclude_patterns"] == ["feed", "comments"]


def test_generated_patterns_are_scoped_to_the_base_url() -> None:
    patterns = generate_url_patterns("https://example.com")

    assert len(patterns) == 2
    assert all("https://example\\.com" in pattern for pattern in patterns)
