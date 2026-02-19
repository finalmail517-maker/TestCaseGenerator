"""
Comprehensive logging utility module for the Test Case Generator
"""
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
import json

class Logger:
    """Centralized logging utility with enhanced formatting"""
    
    _loggers = {}
    
    @classmethod
    def get_logger(
        cls,
        name: str,
        log_level: str = "INFO",
        log_file: Optional[Path] = None
    ) -> logging.Logger:
        """
        Get or create a logger instance
        
        Args:
            name: Logger name
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_file: Optional log file path
            
        Returns:
            Logger instance
        """
        if name in cls._loggers:
            return cls._loggers[name]
        
        # Create logger
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, log_level.upper()))
        
        # Remove existing handlers
        logger.handlers = []
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        simple_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        
        # Console handler with color support
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(simple_formatter)
        logger.addHandler(console_handler)
        
        # File handler with detailed logging
        if log_file:
            log_file.parent.mkdir(exist_ok=True, parents=True)
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(detailed_formatter)
            logger.addHandler(file_handler)
        
        # Store logger
        cls._loggers[name] = logger
        
        return logger
    
    @classmethod
    def log_function_call(cls, logger: logging.Logger):
        """Decorator to log function calls"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                logger.debug(f" Calling {func.__name__} with args={args}, kwargs={kwargs}")
                try:
                    result = func(*args, **kwargs)
                    logger.debug(f" {func.__name__} completed successfully")
                    return result
                except Exception as e:
                    logger.error(f" {func.__name__} raised {type(e).__name__}: {str(e)}")
                    raise
            return wrapper
        return decorator
    
    @classmethod
    def log_performance(cls, logger: logging.Logger):
        """Decorator to log function performance"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                import time
                start_time = time.time()
                
                result = func(*args, **kwargs)
                
                elapsed_time = time.time() - start_time
                logger.info(f" {func.__name__} took {elapsed_time:.2f} seconds")
                
                return result
            return wrapper
        return decorator

class StructuredLogger:
    """Logger with structured JSON output"""
    
    def __init__(self, name: str, log_file: Optional[Path] = None):
        self.name = name
        self.log_file = log_file
        
        if log_file:
            log_file.parent.mkdir(exist_ok=True, parents=True)
    
    def log(self, level: str, message: str, **kwargs):
        """Log a structured message"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'logger': self.name,
            'level': level,
            'message': message,
            **kwargs
        }
        
        if self.log_file:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry) + '\n')
        
        # Also print to console with emoji
        emoji_map = {
            'INFO': 'ℹ️',
            'WARNING': '⚠️',
            'ERROR': '❌',
            'DEBUG': '🔍',
            'CRITICAL': '🚨'
        }
        emoji = emoji_map.get(level, '📝')
        print(f"{emoji} [{level}] {message}")
    
    def info(self, message: str, **kwargs):
        self.log('INFO', message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        self.log('WARNING', message, **kwargs)
    
    def error(self, message: str, **kwargs):
        self.log('ERROR', message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        self.log('DEBUG', message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        self.log('CRITICAL', message, **kwargs)

class TestGenerationLogger:
    """Specialized logger for test generation events"""
    
    def __init__(self):
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        
        self.generation_log = self.log_dir / "test_generation.log"
        self.error_log = self.log_dir / "errors.log"
        self.performance_log = self.log_dir / "performance.log"
        
        self.logger = get_app_logger("test_generation_logger")
    
    def log_generation_start(self, test_type: str, file_count: int):
        """Log start of test generation"""
        entry = {
            'event': 'generation_start',
            'test_type': test_type,
            'file_count': file_count,
            'timestamp': datetime.now().isoformat()
        }
        
        self._write_log(self.generation_log, entry)
        self.logger.info(f"🚀 Test generation started: {test_type} for {file_count} files")
    
    def log_generation_complete(
        self,
        test_type: str,
        test_count: int,
        duration: float
    ):
        """Log completion of test generation"""
        entry = {
            'event': 'generation_complete',
            'test_type': test_type,
            'test_count': test_count,
            'duration_seconds': duration,
            'timestamp': datetime.now().isoformat()
        }
        
        self._write_log(self.generation_log, entry)
        self.logger.info(f"✅ Test generation complete: {test_count} tests in {duration:.2f}s")
    
    def log_error(self, error_type: str, error_message: str, context: dict = None):
        """Log an error"""
        entry = {
            'event': 'error',
            'error_type': error_type,
            'error_message': error_message,
            'context': context or {},
            'timestamp': datetime.now().isoformat()
        }
        
        self._write_log(self.error_log, entry)
        self.logger.error(f"❌ Error: {error_type} - {error_message}")
    
    def log_performance(self, operation: str, duration: float, metadata: dict = None):
        """Log performance metrics"""
        entry = {
            'event': 'performance',
            'operation': operation,
            'duration_seconds': duration,
            'metadata': metadata or {},
            'timestamp': datetime.now().isoformat()
        }
        
        self._write_log(self.performance_log, entry)
        self.logger.debug(f"⏱️ Performance: {operation} took {duration:.2f}s")
    
    def _write_log(self, log_file: Path, data: dict):
        """Write log entry to file"""
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(data) + '\n')
        except Exception as e:
            self.logger.error(f"Failed to write log: {e}")
    
    def get_statistics(self) -> dict:
        """Get statistics from logs"""
        stats = {
            'total_generations': 0,
            'total_tests': 0,
            'average_duration': 0,
            'error_count': 0,
            'by_test_type': {}
        }
        
        if not self.generation_log.exists():
            return stats
        
        durations = []
        
        try:
            with open(self.generation_log, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        
                        if entry['event'] == 'generation_complete':
                            stats['total_generations'] += 1
                            stats['total_tests'] += entry['test_count']
                            durations.append(entry['duration_seconds'])
                            
                            test_type = entry['test_type']
                            if test_type not in stats['by_test_type']:
                                stats['by_test_type'][test_type] = {
                                    'count': 0,
                                    'total_tests': 0
                                }
                            
                            stats['by_test_type'][test_type]['count'] += 1
                            stats['by_test_type'][test_type]['total_tests'] += entry['test_count']
                    
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            self.logger.error(f"Error reading statistics: {e}")
        
        if durations:
            stats['average_duration'] = sum(durations) / len(durations)
        
        # Count errors
        if self.error_log.exists():
            try:
                with open(self.error_log, 'r', encoding='utf-8') as f:
                    stats['error_count'] = sum(1 for _ in f)
            except:
                pass
        
        return stats


# Initialize default logger
def get_app_logger(name: str = "test_generator") -> logging.Logger:
    """Get the main application logger"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    return Logger.get_logger(
        name,
        log_level="INFO",
        log_file=log_dir / "app.log"
    )


# Create a global logger instance
app_logger = get_app_logger()