"""Structured JSON logging setup for Murmuration simulation.

This module configures structured logging using the structlog library,
ensuring consistent JSON output for all log messages as required by CLAUDE.md.
"""

import sys
import logging
from pathlib import Path
from typing import Optional, Any, Dict

import structlog
from structlog.types import FilteringBoundLogger


# Global logger instance
_logger: Optional[FilteringBoundLogger] = None


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    service_name: str = "murmuration",
) -> None:
    """Setup structured JSON logging configuration.
    
    Configures structlog to output structured JSON logs with consistent
    formatting and metadata fields.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path to write logs to (stdout if None)
        service_name: Service name to include in log metadata
    """
    global _logger
    
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        level=numeric_level,
        stream=sys.stdout if log_file is None else open(log_file, "a"),
    )
    
    # Shared processors for all loggers
    shared_processors = [
        # Add service metadata
        structlog.processors.add_log_level,
        # structlog.stdlib.add_logger_name,  # Commented out for compatibility
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.contextvars.merge_contextvars,
        # Add custom context
        lambda logger, name, event_dict: _add_service_context(
            logger, name, event_dict, service_name
        ),
    ]
    
    # Configure structlog
    structlog.configure(
        processors=shared_processors + [
            # Final processor depends on output format
            structlog.processors.JSONRenderer(sort_keys=True)
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Create the global logger instance
    _logger = structlog.get_logger("murmuration")
    
    # Log initialization
    _logger.info(
        "Logging initialized",
        extra={
            "level": level,
            "log_file": log_file,
            "service": service_name,
        }
    )


def _add_service_context(
    logger: Any, 
    name: str, 
    event_dict: Dict[str, Any], 
    service_name: str
) -> Dict[str, Any]:
    """Add service-specific context to log events.
    
    Args:
        logger: Logger instance
        name: Logger name
        event_dict: Event dictionary to modify
        service_name: Service name to add
        
    Returns:
        Modified event dictionary
    """
    event_dict["service"] = service_name
    
    # Add process info
    import os
    event_dict["pid"] = os.getpid()
    
    return event_dict


def get_logger(name: Optional[str] = None) -> FilteringBoundLogger:
    """Get a structured logger instance.
    
    Args:
        name: Optional logger name (uses default if None)
        
    Returns:
        Configured structlog logger
        
    Raises:
        RuntimeError: If logging hasn't been setup yet
    """
    if _logger is None:
        # Auto-initialize with defaults for convenience
        setup_logging()
    
    if name is None:
        return _logger
    
    return structlog.get_logger(name)


def log_simulation_event(
    event_type: str,
    **kwargs: Any
) -> None:
    """Log a structured simulation event.
    
    Convenience function for logging simulation-specific events
    with consistent structure.
    
    Args:
        event_type: Type of event (tick, arrival, loss, etc.)
        **kwargs: Additional event data
    """
    logger = get_logger()
    
    event_data = {
        "event_type": event_type,
        **kwargs
    }
    
    logger.info("simulation_event", extra=event_data)


def log_performance_metric(
    metric_name: str,
    value: float,
    unit: str = "",
    **kwargs: Any
) -> None:
    """Log a performance metric.
    
    Args:
        metric_name: Name of the metric (fps, cohesion, etc.)
        value: Metric value
        unit: Optional unit string
        **kwargs: Additional context
    """
    logger = get_logger()
    
    logger.info(
        "performance_metric",
        extra={
            "metric_name": metric_name,
            "value": value,
            "unit": unit,
            **kwargs
        }
    )


def log_error_with_context(
    message: str,
    error: Exception,
    **kwargs: Any
) -> None:
    """Log an error with full context information.
    
    Args:
        message: Human-readable error description
        error: Exception that occurred
        **kwargs: Additional context
    """
    logger = get_logger()
    
    logger.error(
        message,
        extra={
            "error_type": type(error).__name__,
            "error_message": str(error),
            "error_module": getattr(error, "__module__", None),
            **kwargs
        }
    )


def create_child_logger(name: str, **context: Any) -> FilteringBoundLogger:
    """Create a child logger with additional context.
    
    Args:
        name: Child logger name
        **context: Context to bind to the child logger
        
    Returns:
        Child logger with bound context
    """
    logger = get_logger()
    return logger.bind(child_name=name, **context)


class LoggingContext:
    """Context manager for adding temporary logging context."""
    
    def __init__(self, **context: Any):
        self.context = context
        self.logger = get_logger()
    
    def __enter__(self) -> FilteringBoundLogger:
        return self.logger.bind(**self.context)
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass


def with_logging_context(**context: Any) -> LoggingContext:
    """Create a logging context manager.
    
    Usage:
        with with_logging_context(agent_id=123, tick=456) as logger:
            logger.info("Agent update", extra={"velocity": 5.2})
    
    Args:
        **context: Context variables to add
        
    Returns:
        Context manager that provides a bound logger
    """
    return LoggingContext(**context)


# Default setup for when the module is imported directly
if __name__ == "__main__":
    setup_logging(level="DEBUG")
    logger = get_logger()
    
    # Test the logging setup
    logger.info("Testing structured logging")
    logger.debug("Debug message with data", extra={"test_value": 42})
    logger.warning("Warning message")
    logger.error("Error message", extra={"error_code": "E001"})
    
    # Test event logging
    log_simulation_event(
        "test_event",
        tick=100,
        agent_count=150,
        cohesion=0.75
    )
    
    # Test performance logging
    log_performance_metric("fps", 58.3, "frames/second", target=60.0)
    
    # Test child logger
    child = create_child_logger("test_child", module="physics")
    child.info("Child logger message")
    
    # Test context manager
    with with_logging_context(simulation_id="sim_001") as ctx_logger:
        ctx_logger.info("Context logger message", extra={"step": "initialization"})
    
    print("Logging test completed successfully")