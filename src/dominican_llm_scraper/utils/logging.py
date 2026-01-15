# type: ignore
import contextvars
import logging
import logging.config
import os
import uuid
from datetime import datetime
from typing import Any, Dict, Optional


# Thread-safe context variables for correlation IDs and log fields
_correlation_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("correlation_id", default=None)
_log_context: contextvars.ContextVar[Dict[str, Any]] = contextvars.ContextVar("log_context", default={})


def _get_correlation_id() -> Optional[str]:
    """Get current correlation ID from context."""
    return _correlation_id.get()


def _set_correlation_id(correlation_id: str) -> None:
    """Set correlation ID in current context."""
    _correlation_id.set(correlation_id)


def _get_log_context() -> Dict[str, Any]:
    """Get current log context dictionary."""
    return _log_context.get() or {}


def _set_log_context(context: Dict[str, Any]) -> None:
    """Set log context dictionary."""
    _log_context.set(context)


def _update_log_context(**kwargs) -> None:
    """Update log context with additional fields."""
    current = _get_log_context()
    current.update(kwargs)
    _set_log_context(current)


def _get_all_context_fields() -> Dict[str, Any]:
    """Get all context fields including correlation ID."""
    fields = _get_log_context().copy()
    correlation_id = _get_correlation_id()
    if correlation_id:
        fields["session_id"] = correlation_id
    return fields


class SpringBootFormatter(logging.Formatter):
    """Custom formatter for Spring Boot-style logs with optional colors."""

    COLORS = {
        "GREY": "\033[90m",
        "CYAN": "\033[36m",
        "BRIGHT_BLUE": "\033[94m",
        "YELLOW": "\033[93m",
        "RED": "\033[91m",
        "BOLD_RED": "\033[1;91m",
        "MAGENTA": "\033[95m",
        "RESET": "\033[0m",
    }

    LEVEL_COLORS = {
        "DEBUG": COLORS["CYAN"],
        "INFO": COLORS["BRIGHT_BLUE"],
        "WARNING": COLORS["YELLOW"],
        "ERROR": COLORS["RED"],
        "CRITICAL": COLORS["BOLD_RED"],
    }

    def __init__(self, use_colors=True, logger_name_width=40):
        super().__init__()
        self.use_colors = use_colors
        self.logger_name_width = logger_name_width
        self.pid = os.getpid()

    def format(self, record):  # type: ignore
        # Extract correlation ID
        correlation_id = None
        if hasattr(record, "canonical_fields"):
            correlation_id = getattr(record.canonical_fields, "get", lambda x: None)("session_id")

        # Format timestamp: 2026-01-15T11:01:10.750-04:00
        dt = datetime.fromtimestamp(record.created)
        timestamp = dt.strftime("%Y-%m-%dT%H:%M:%S")
        milliseconds = int(record.msecs)
        timestamp += f".{milliseconds:03d}"
        timezone = dt.astimezone().strftime("%z")
        if timezone:
            timezone = f"{timezone[:3]}:{timezone[3:]}"
        timestamp += timezone

        # Format components
        level = record.levelname.rjust(5)
        corr_display = f"[{correlation_id}]" if correlation_id else "[-]"
        pid_display = str(self.pid)
        logger_name = record.name[: self.logger_name_width].ljust(self.logger_name_width)
        message = record.getMessage()

        # Build log line
        if self.use_colors:
            timestamp_colored = f"{self.COLORS['GREY']}{timestamp}{self.COLORS['RESET']}"
            level_colored = f"{self.LEVEL_COLORS.get(record.levelname, '')}{level}{self.COLORS['RESET']}"
            corr_colored = f"{self.COLORS['MAGENTA']}{corr_display}{self.COLORS['RESET']}"
            pid_colored = f"{self.COLORS['MAGENTA']}{pid_display}{self.COLORS['RESET']}"
            logger_colored = f"{self.COLORS['CYAN']}{logger_name}{self.COLORS['RESET']}"
            log_line = (
                f"{timestamp_colored} {level_colored} {corr_colored} {pid_colored} --- {logger_colored} : {message}"
            )
        else:
            log_line = f"{timestamp} {level} {corr_display} {pid_display} --- {logger_name} : {message}"

        # Add exception info
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
            if record.exc_text:
                if log_line[-1:] != "\n":
                    log_line += "\n"
                log_line += record.exc_text

        return log_line


def setup_logging(env: Optional[str] = None) -> None:
    """Initialize logging system. Call once at application startup."""
    if env is None:
        env = os.getenv("APP_ENV", "dev").lower()

    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "springboot_colored": {
                "()": "dominican_llm_scraper.utils.logging.SpringBootFormatter",
                "use_colors": True,
                "logger_name_width": 40,
            },
            "springboot_plain": {
                "()": "dominican_llm_scraper.utils.logging.SpringBootFormatter",
                "use_colors": False,
                "logger_name_width": 40,
            },
        },
        "handlers": {
            "console_colored": {
                "class": "logging.StreamHandler",
                "formatter": "springboot_colored",
                "level": log_level,
                "stream": "ext://sys.stdout",
            },
            "console_plain": {
                "class": "logging.StreamHandler",
                "formatter": "springboot_plain",
                "level": log_level,
                "stream": "ext://sys.stdout",
            },
            "file_handler": {
                "class": "logging.FileHandler",
                "formatter": "springboot_plain",
                "level": "INFO",
                "filename": "scraping.log",
                "encoding": "utf-8",
            },
        },
        "root": {
            "level": log_level,
            "handlers": ["console_colored", "file_handler"] if env == "dev" else ["console_plain", "file_handler"],
        },
    }

    logging.config.dictConfig(config)


def log_canonical(logger: logging.Logger, event: str, level: str = "INFO", **kwargs) -> None:
    """Log structured event in key=value format with automatic context fields."""
    context_fields = _get_all_context_fields()
    all_fields = {**context_fields, **kwargs}
    extras = {k: v for k, v in all_fields.items() if v is not None}

    message_parts = [event]
    for key, value in extras.items():
        if isinstance(value, str):
            message_parts.append(f'{key}="{value}"')
        else:
            message_parts.append(f"{key}={value}")

    canonical_message = " ".join(message_parts)
    extras["event"] = event

    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.log(log_level, canonical_message, extra={"canonical_fields": extras})


class LogContext:
    """Context manager for correlation IDs and additional log fields."""

    def __init__(self, correlation_id: Optional[str] = None, **context_fields):
        self.correlation_id = correlation_id
        self.context_fields = context_fields
        self.previous_correlation_id = None
        self.previous_context = None

    def __enter__(self):
        self.previous_correlation_id = _get_correlation_id()
        self.previous_context = _get_log_context().copy()

        if self.correlation_id:
            _set_correlation_id(self.correlation_id)
        elif not _get_correlation_id():
            correlation_id = str(uuid.uuid4())[:8]
            _set_correlation_id(correlation_id)

        if self.context_fields:
            _update_log_context(**self.context_fields)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.previous_correlation_id:
            _set_correlation_id(self.previous_correlation_id)
        else:
            _correlation_id.set(None)
        _set_log_context(self.previous_context)

    @classmethod
    def new_session(cls, session_type: Optional[str] = None, **context_fields):
        """Create new session with fresh correlation ID."""
        correlation_id = str(uuid.uuid4())[:8]
        if session_type:
            context_fields["session_type"] = session_type
        return cls(correlation_id=correlation_id, **context_fields)
