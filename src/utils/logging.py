# src/utils/logging.py

import logging
import sys
from datetime import datetime
import uuid


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for different log levels."""
    
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
    }
    RESET = '\033[0m'

    def format(self, record):
        # Add color to level name only
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        
        return super().format(record)


def setup_logger(name: str, level: int = logging.DEBUG) -> logging.Logger:
    """
    Creates and configures a logger with colored output.
    
    Args:
        name: Name of the logger (usually __name__)
        level: Logging level (default: INFO)
    
    Returns:
        Configured logger instance
    
    Example:
        from src.utils.logging import setup_logger
        
        logger = setup_logger(__name__)
        logger.info("This is an info message")
    """
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Remove existing handlers to avoid duplicates
    if logger.handlers:
        logger.handlers.clear()
    
    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    
    # Create formatter
    formatter = ColoredFormatter(
        fmt='%(levelname)s: %(filename)s:%(lineno)d - %(message)s'
    )
    
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    return logger


def setup_global_logging(level: int = logging.INFO):
    """
    Configure global logging for the entire application.
    Call this once at application startup.
    
    Args:
        level: Global logging level (default: INFO)
    """
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers
    if root_logger.handlers:
        root_logger.handlers.clear()
    
    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    
    # Create formatter
    formatter = ColoredFormatter(
        fmt='%(levelname)s:    %(filename)s:%(lineno)d - %(message)s'
    )
    
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)


# Example usage when run directly
if __name__ == "__main__":
    # Test the logger
    logger = setup_logger(__name__)
    
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    logger.critical("This is a critical message")
    
