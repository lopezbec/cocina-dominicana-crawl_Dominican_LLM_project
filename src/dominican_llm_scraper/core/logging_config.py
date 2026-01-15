# core/logging_config.py
# type: ignore
import logging
import logging.config
import os
from datetime import datetime


class SpringBootFormatter(logging.Formatter):
    """
    Custom formatter that mimics Spring Boot logging style with colors.

    Format: <timestamp>  <level> [<correlationId>] <pid> --- <logger_name_padded> : <message>

    Example:
        2026-01-15T11:01:10.750-04:00  INFO [a7b8c9d0] 79468 --- core.crawler                  : scrape_success url="https://example.com"

    Colors (for dev mode):
        - Timestamp: Dark grey
        - INFO: Bright cyan/blue
        - WARNING: Yellow
        - ERROR: Red
        - CRITICAL: Bold red
        - DEBUG: Cyan
        - Correlation ID & PID: Magenta
        - Logger name: Cyan
        - Message: Default/white
    """

    # ANSI color codes
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
        # Extract correlation ID from extras
        correlation_id = None
        if hasattr(record, "canonical_fields"):
            correlation_id = getattr(record.canonical_fields, "get", lambda x: None)("session_id")

        # Format timestamp with milliseconds: 2026-01-15T11:01:10.750-04:00
        dt = datetime.fromtimestamp(record.created)
        timestamp = dt.strftime("%Y-%m-%dT%H:%M:%S")
        # Add milliseconds (3 digits)
        milliseconds = int(record.msecs)
        timestamp += f".{milliseconds:03d}"
        # Add timezone
        timezone = dt.astimezone().strftime("%z")
        if timezone:
            # Format timezone as -04:00 instead of -0400
            timezone = f"{timezone[:3]}:{timezone[3:]}"
        timestamp += timezone

        # Format level (right-aligned, 5 chars for alignment)
        level = record.levelname.rjust(5)

        # Format correlation ID
        corr_display = f"[{correlation_id}]" if correlation_id else "[-]"

        # Format PID
        pid_display = str(self.pid)

        # Format logger name (right-padded to fixed width)
        logger_name = record.name[: self.logger_name_width].ljust(self.logger_name_width)

        # Format message
        message = record.getMessage()

        # Build the log line
        if self.use_colors:
            # Apply colors
            timestamp_colored = f"{self.COLORS['GREY']}{timestamp}{self.COLORS['RESET']}"
            level_colored = f"{self.LEVEL_COLORS.get(record.levelname, '')}{level}{self.COLORS['RESET']}"
            corr_colored = f"{self.COLORS['MAGENTA']}{corr_display}{self.COLORS['RESET']}"
            pid_colored = f"{self.COLORS['MAGENTA']}{pid_display}{self.COLORS['RESET']}"
            logger_colored = f"{self.COLORS['CYAN']}{logger_name}{self.COLORS['RESET']}"

            log_line = (
                f"{timestamp_colored} {level_colored} {corr_colored} {pid_colored} --- {logger_colored} : {message}"
            )
        else:
            # Plain text (for production and file output)
            log_line = f"{timestamp} {level} {corr_display} {pid_display} --- {logger_name} : {message}"

        # Add exception info if present
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
            if record.exc_text:
                if log_line[-1:] != "\n":
                    log_line += "\n"
                log_line += record.exc_text

        return log_line


def get_logging_config(env: str = None) -> dict:
    """
    Build a dictConfig-style logging configuration.

    env:
        "dev"  -> Spring Boot-style colored console + plain text file
        "prod" -> Spring Boot-style plain console + plain text file
    """
    if env is None:
        env = os.getenv("APP_ENV", "dev").lower()

    # Get log level from environment
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "springboot_colored": {
                "()": "dominican_llm_scraper.core.logging_config.SpringBootFormatter",
                "use_colors": True,
                "logger_name_width": 40,
            },
            "springboot_plain": {
                "()": "dominican_llm_scraper.core.logging_config.SpringBootFormatter",
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
        "loggers": {
            # Project-specific loggers
            "dominican_llm_scraper.core": {
                "level": log_level,
                "handlers": [],
                "propagate": False,
            },
            "dominican_llm_scraper.utils": {
                "level": log_level,
                "handlers": [],
                "propagate": False,
            },
        },
        "root": {
            "level": log_level,
            "handlers": [],
        },
    }

    # Environment-specific handler wiring
    if env == "prod":
        # Production: Plain console + file
        handlers = ["console_plain", "file_handler"]
    else:
        # Dev: Colored console + file
        handlers = ["console_colored", "file_handler"]

    config["root"]["handlers"] = handlers
    config["loggers"]["dominican_llm_scraper.core"]["handlers"] = handlers
    config["loggers"]["dominican_llm_scraper.utils"]["handlers"] = handlers

    return config


def setup_logging(env: str = None) -> None:
    """
    Apply the logging configuration.

    Call this once at application startup.
    """
    config = get_logging_config(env)
    logging.config.dictConfig(config)

    # Log initialization message
    logger = logging.getLogger(__name__)
    actual_env = env or os.getenv("APP_ENV", "dev").lower()
    logger.info(
        f"logging_initialized env={actual_env} log_level={os.getenv('LOG_LEVEL', 'INFO')}",
        extra={
            "canonical_fields": {
                "event": "logging_initialized",
                "env": actual_env,
                "log_level": os.getenv("LOG_LEVEL", "INFO"),
            }
        },
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.

    Convenience function for getting loggers after setup_logging() has been called.
    """
    return logging.getLogger(name)
