"""Structured logging module for CrawlLama."""
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logs."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)

        return json.dumps(log_data)


class Logger:
    """Unified logger manager for CrawlLama."""
    
    _initialized_loggers = set()
    _default_config = {
        "log_file": "logs/app.log",
        "level": "INFO",
        "format_type": "json"
    }
    
    @classmethod
    def configure(cls, log_file: str = "logs/app.log", level: str = "INFO", format_type: str = "json"):
        """
        Configure default logger settings.
        
        Args:
            log_file: Path to log file
            level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            format_type: Format type ("json" or "text")
        """
        cls._default_config = {
            "log_file": log_file,
            "level": level,
            "format_type": format_type
        }
    
    @classmethod
    def get(cls, name: str | None = None) -> logging.Logger:
        """
        Get or create logger instance with consistent configuration.
        
        Args:
            name: Logger name (default: "crawllama", or use __name__ for module-specific)
            
        Returns:
            Configured logger instance
            
        Examples:
            >>> logger = Logger.get()  # Default "crawllama" logger
            >>> logger = Logger.get(__name__)  # Module-specific logger
        """
        # Use default name if not specified
        if name is None:
            name = "crawllama"
        
        # Get logger instance
        logger = logging.getLogger(name)
        
        # Initialize if not already done
        if name not in cls._initialized_loggers:
            cls._initialize_logger(logger)
            cls._initialized_loggers.add(name)
        
        return logger
    
    @classmethod
    def _initialize_logger(cls, logger: logging.Logger):
        """Initialize logger with handlers and formatters."""
        config = cls._default_config
        
        # Set level
        logger.setLevel(getattr(logging, config["level"].upper()))
        
        # Prevent duplicate handlers
        if logger.handlers:
            return
        
        # Create logs directory
        log_path = Path(config["log_file"])
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # File handler with log rotation
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            config["log_file"], 
            maxBytes=10 * 1024 * 1024, 
            backupCount=5, 
            encoding="utf-8"
        )
        
        if config["format_type"] == "json":
            file_handler.setFormatter(JSONFormatter())
        else:
            file_handler.setFormatter(
                logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            )
        logger.addHandler(file_handler)
        
        # Console handler with simple format
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter('%(levelname)s: %(message)s')
        )
        logger.addHandler(console_handler)


# ============================================================================
# DEPRECATED: Legacy functions (for backwards compatibility)
# ============================================================================


def setup_logger(
    name: str = "crawllama",
    log_file: str = "logs/app.log",
    level: str = "INFO",
    format_type: str = "json"
) -> logging.Logger:
    """
    DEPRECATED: Use Logger.get() instead.
    Setup structured logger with file and console handlers.

    Args:
        name: Logger name
        log_file: Path to log file
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: Format type ("json" or "text")

    Returns:
        Configured logger instance
    """
    import warnings
    warnings.warn(
        "setup_logger() is deprecated. Use Logger.get() instead:\n"
        "  Old: logger = setup_logger(__name__)\n"
        "  New: logger = Logger.get(__name__)",
        DeprecationWarning,
        stacklevel=2
    )
    
    # Configure with provided settings
    Logger.configure(log_file, level, format_type)
    return Logger.get(name)


def get_logger(name: str = "crawllama") -> logging.Logger:
    """
    DEPRECATED: Use Logger.get() instead.
    Get or create logger instance.
    """
    import warnings
    warnings.warn(
        "get_logger() is deprecated. Use Logger.get() instead:\n"
        "  Old: logger = get_logger('my_module')\n"
        "  New: logger = Logger.get('my_module')",
        DeprecationWarning,
        stacklevel=2
    )
    return Logger.get(name)
