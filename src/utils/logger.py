"""
Centralized logging configuration for the RAG application.
Uses loguru for structured logging.
"""

import sys
from pathlib import Path
from loguru import logger as _logger
import os

# Get log level from environment
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# Remove default handler
_logger.remove()

# Add console handler with color
_logger.add(
    sys.stdout,
    format="<level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=LOG_LEVEL,
    colorize=True
)

# Add file handler for all logs
_logger.add(
    LOG_DIR / "app.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="DEBUG",
    rotation="500 MB",
    retention="7 days"
)

# Add file handler for errors only
_logger.add(
    LOG_DIR / "errors.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="ERROR",
    rotation="500 MB",
    retention="30 days"
)


def get_logger(name: str = None):
    """
    Get a logger instance.
    
    Args:
        name: Module name (typically __name__)
    
    Returns:
        Logger instance
    """
    return _logger.bind(module=name) if name else _logger


# Convenience functions
def log_info(message: str, **kwargs):
    """Log info level message."""
    _logger.info(message, **kwargs)


def log_debug(message: str, **kwargs):
    """Log debug level message."""
    _logger.debug(message, **kwargs)


def log_warning(message: str, **kwargs):
    """Log warning level message."""
    _logger.warning(message, **kwargs)


def log_error(message: str, **kwargs):
    """Log error level message."""
    _logger.error(message, **kwargs)


def log_critical(message: str, **kwargs):
    """Log critical level message."""
    _logger.critical(message, **kwargs)
