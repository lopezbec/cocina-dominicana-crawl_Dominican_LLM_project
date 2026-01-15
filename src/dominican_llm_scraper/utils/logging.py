import logging

from dominican_llm_scraper.core.log_context import get_all_context_fields


def setup_canonical_logger(name: str, level: str = "INFO") -> logging.Logger:
    """
    Setup logger optimized for canonical log lines.

    DEPRECATED: This function is kept for backward compatibility.
    New code should use core.logging_config.get_logger() instead.

    Note: If logging has been initialized via core.logging_config.setup_logging(),
    this will simply return the configured logger. Otherwise, it falls back to
    the old behavior for backward compatibility.
    """
    logger = logging.getLogger(name)

    # If logger already has handlers (from setup_logging()), just return it
    if logger.handlers or logging.getLogger().handlers:
        return logger

    # Fallback: old behavior for backward compatibility
    logger.setLevel(getattr(logging, level.upper()))

    console_handler = logging.StreamHandler()
    formatter = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    console_handler.setFormatter(logging.Formatter(formatter))

    file_handler = logging.FileHandler("scraping.log")
    file_handler.setFormatter(logging.Formatter(formatter))

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


def log_canonical(logger: logging.Logger, event: str, level: str = "INFO", **kwargs) -> None:
    """
    Log a canonical log line following Stripe pattern.

    This function creates structured logs that work beautifully in both
    development (human-readable colored output) and production (JSON).

    Args:
        logger: The logger instance to use
        event: The event name (e.g., "scrape_success", "article_saved")
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        **kwargs: Additional key-value pairs to include in the log

    Example:
        log_canonical(
            logger,
            "scrape_success",
            url="https://example.com",
            attempt=1,
            duration_ms=1234
        )

    Output in dev (colored console):
        2026-01-13 13:30:45 | INFO     | core.crawler | scrape_success url="https://example.com" attempt=1 duration_ms=1234 session_id="abc-123"

    Output in prod (JSON):
        {"timestamp":"2026-01-13T13:30:45-0500","level":"INFO","logger":"core.crawler","event":"scrape_success","url":"https://example.com","attempt":1,"duration_ms":1234,"session_id":"abc-123","hostname":"mycomputer","pid":12345}
    """
    # Get context fields (includes session_id if set)
    context_fields = get_all_context_fields()

    # Merge kwargs with context fields (kwargs take precedence)
    all_fields = {**context_fields, **kwargs}

    # Filter out None values
    extras = {k: v for k, v in all_fields.items() if v is not None}

    # Build human-readable message (for console/plain text logs)
    message_parts = [event]
    for key, value in extras.items():
        if isinstance(value, str):
            message_parts.append(f'{key}="{value}"')
        else:
            message_parts.append(f"{key}={value}")

    canonical_message = " ".join(message_parts)

    # Add event to extras for JSON formatter
    extras["event"] = event

    # Log at the appropriate level
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.log(log_level, canonical_message, extra={"canonical_fields": extras})
