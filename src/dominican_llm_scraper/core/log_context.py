# core/log_context.py
import contextvars
import uuid
from typing import Optional, Dict, Any


# Thread-safe context variable for correlation ID
_correlation_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("correlation_id", default=None)

# Thread-safe context variable for additional context fields
_log_context: contextvars.ContextVar[Dict[str, Any]] = contextvars.ContextVar("log_context", default={})


def get_correlation_id() -> Optional[str]:
    """Get the current correlation ID from context."""
    return _correlation_id.get()


def set_correlation_id(correlation_id: str) -> None:
    """Set the correlation ID for the current context."""
    _correlation_id.set(correlation_id)


def generate_correlation_id() -> str:
    """Generate a new correlation ID and set it in context."""
    correlation_id = str(uuid.uuid4())[:8]  # Short 8-character UUID
    set_correlation_id(correlation_id)
    return correlation_id


def clear_correlation_id() -> None:
    """Clear the correlation ID from context."""
    _correlation_id.set(None)


def get_log_context() -> Dict[str, Any]:
    """Get the current log context dictionary."""
    return _log_context.get() or {}


def set_log_context(context: Dict[str, Any]) -> None:
    """Set the log context dictionary."""
    _log_context.set(context)


def update_log_context(**kwargs) -> None:
    """Update the log context with additional fields."""
    current = get_log_context()
    current.update(kwargs)
    set_log_context(current)


def clear_log_context() -> None:
    """Clear the log context."""
    _log_context.set({})


class LogContext:
    """
    Context manager for adding correlation IDs and context to logs.

    Usage:
        with LogContext(session_type="scrape", url="https://example.com"):
            # All logs in this block will include session_id and context fields
            logger.info("Processing...")

    Or generate a correlation ID:
        with LogContext.new_session(session_type="crawl"):
            # Automatically generates a new correlation ID
            logger.info("Starting crawl...")
    """

    def __init__(self, correlation_id: Optional[str] = None, **context_fields):
        """
        Initialize log context.

        Args:
            correlation_id: Optional correlation ID. If None, uses existing or generates new.
            **context_fields: Additional fields to add to all logs in this context.
        """
        self.correlation_id = correlation_id
        self.context_fields = context_fields
        self.previous_correlation_id = None
        self.previous_context = None

    def __enter__(self):
        # Save previous state
        self.previous_correlation_id = get_correlation_id()
        self.previous_context = get_log_context().copy()

        # Set new correlation ID if provided, otherwise generate or keep existing
        if self.correlation_id:
            set_correlation_id(self.correlation_id)
        elif not get_correlation_id():
            generate_correlation_id()

        # Update context with new fields
        if self.context_fields:
            update_log_context(**self.context_fields)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore previous state
        if self.previous_correlation_id:
            set_correlation_id(self.previous_correlation_id)
        else:
            clear_correlation_id()

        set_log_context(self.previous_context)

    @classmethod
    def new_session(cls, session_type: Optional[str] = None, **context_fields):
        """
        Create a new log context with a fresh correlation ID.

        Args:
            session_type: Optional type of session (e.g., "scrape", "crawl", "discover")
            **context_fields: Additional context fields
        """
        correlation_id = str(uuid.uuid4())[:8]

        if session_type:
            context_fields["session_type"] = session_type

        return cls(correlation_id=correlation_id, **context_fields)


def get_all_context_fields() -> Dict[str, Any]:
    """
    Get all context fields including correlation ID.

    Returns a dictionary with all current context fields.
    """
    fields = get_log_context().copy()

    correlation_id = get_correlation_id()
    if correlation_id:
        fields["session_id"] = correlation_id

    return fields
