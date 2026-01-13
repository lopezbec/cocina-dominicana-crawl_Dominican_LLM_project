# core/logging_config.py
import logging
import logging.config
import os
import socket
from datetime import datetime
from pathlib import Path

from pythonjsonlogger import jsonlogger
import colorlog


class SpringBootFormatter(logging.Formatter):
    """
    Custom formatter that mimics Spring Boot logging style with colors.

    Format: <timestamp>  <level> [<correlationId>] <pid> --- <logger_name_padded> : <message>

    Example:
        2026-01-13T15:45:31.263-04:00  INFO [a7b8c9d0] 79468 --- core.crawler                  : scrape_success url="https://example.com"

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

    def format(self, record):
        # Extract correlation ID from extras
        correlation_id = None
        if hasattr(record, "canonical_fields"):
            correlation_id = record.canonical_fields.get("session_id")

        # Format timestamp with milliseconds: 2026-01-13T15:45:31.263-04:00
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
            # Plain text (for production)
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


class JsonFormatter(jsonlogger.JsonFormatter):
    """
    Enhanced JSON formatter for production logs.

    Adds useful fields like logger name, level, timestamp, hostname, PID, etc.
    Automatically extracts structured fields from log extras.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hostname = socket.gethostname()
        self.pid = os.getpid()

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)

        # Add standard fields
        if not log_record.get("level"):
            log_record["level"] = record.levelname

        if not log_record.get("logger"):
            log_record["logger"] = record.name

        if not log_record.get("timestamp"):
            # ISO-8601 timestamp with timezone and milliseconds
            dt = datetime.fromtimestamp(record.created)
            timestamp = dt.strftime("%Y-%m-%dT%H:%M:%S")
            milliseconds = int(record.msecs)
            timestamp += f".{milliseconds:03d}"
            timezone = dt.astimezone().strftime("%z")
            if timezone:
                timezone = f"{timezone[:3]}:{timezone[3:]}"
            timestamp += timezone
            log_record["timestamp"] = timestamp

        # Add context fields
        log_record["hostname"] = self.hostname
        log_record["pid"] = self.pid

        # Extract event name from message if it follows canonical pattern
        # Example: "scrape_success url="..." attempt=1"
        message = log_record.get("message", "")
        if message and " " in message:
            parts = message.split(" ", 1)
            if "=" not in parts[0]:  # First part is the event name
                log_record["event"] = parts[0]

        # Add any extra fields from the log record
        # These come from the 'extra' parameter in logger calls
        if hasattr(record, "canonical_fields"):
            for key, value in record.canonical_fields.items():
                if key not in log_record:
                    log_record[key] = value


def get_logging_config(env: str = None) -> dict:
    """
    Build a dictConfig-style logging configuration.

    env:
        "dev"  -> Spring Boot-style colored console + JSON file logs
        "prod" -> Spring Boot-style plain console + JSON file logs
    """
    if env is None:
        env = os.getenv("APP_ENV", "dev").lower()

    # Get configuration from environment
    log_dir = os.getenv("LOG_DIR", "data/logs")
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    retention_days = int(os.getenv("LOG_RETENTION_DAYS", "14" if env == "dev" else "30"))

    # Ensure log directory exists
    Path(log_dir).mkdir(exist_ok=True)

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
            "json": {
                # Use our enhanced JSON formatter class
                "()": "dominican_llm_scraper.core.logging_config.JsonFormatter",
                "format": "%(timestamp)s %(level)s %(name)s %(message)s",
            },
        },
        "handlers": {
            "console_springboot_colored": {
                "class": "logging.StreamHandler",
                "formatter": "springboot_colored",
                "level": log_level,
                "stream": "ext://sys.stdout",
            },
            "console_springboot_plain": {
                "class": "logging.StreamHandler",
                "formatter": "springboot_plain",
                "level": log_level,
                "stream": "ext://sys.stdout",
            },
            "file_json": {
                "class": "logging.handlers.TimedRotatingFileHandler",
                "formatter": "json",
                "level": "INFO",
                "filename": f"{log_dir}/app.log",
                "when": "midnight",
                "backupCount": retention_days,
                "encoding": "utf-8",
            },
            "file_errors": {
                "class": "logging.handlers.TimedRotatingFileHandler",
                "formatter": "json",
                "level": "WARNING",
                "filename": f"{log_dir}/errors.log",
                "when": "midnight",
                "backupCount": retention_days,
                "encoding": "utf-8",
            },
            # Backward compatibility: keep writing to scraping.log
            "file_legacy": {
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
        # Production: Spring Boot plain console + JSON files + legacy file
        handlers = ["console_springboot_plain", "file_json", "file_errors", "file_legacy"]
        config["root"]["handlers"] = handlers
        config["loggers"]["dominican_llm_scraper.core"]["handlers"] = handlers
        config["loggers"]["dominican_llm_scraper.utils"]["handlers"] = handlers
    else:
        # Dev: Spring Boot colored console + JSON files + legacy file
        handlers = ["console_springboot_colored", "file_json", "file_errors", "file_legacy"]
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
