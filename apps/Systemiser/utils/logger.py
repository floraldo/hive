import logging
from pathlib import Path
from datetime import datetime
import sys
import traceback
from collections import deque
import os
import pandas as pd # Added import for DataFrame type hint if needed
from hive_logging import get_logger

logger = get_logger(__name__)

class SystemLogger:
    MAX_LOG_SESSIONS = 5
    
    def __init__(self, name="system_logger", log_dir="logs"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear() # Ensure no duplicate handlers if re-initialized
        
        # Create logs directory relative to the caller's CWD or specified path
        # Make log_dir relative to Systemiser root for now
        systemiser_root = Path(__file__).parent.parent 
        self.log_dir = systemiser_root / log_dir
        self.log_dir.mkdir(exist_ok=True)
        
        # Use a single log file
        self.log_file = self.log_dir / f"{name}.log"
        
        # If file exists with encoding issues, remove it (use with caution)
        # Consider rotating logs instead of removing
        # if self.log_file.exists():
        #     try:
        #         with open(self.log_file, 'r', encoding='utf-8') as f:
        #             f.read()
        #     except UnicodeDecodeError:
        #         os.remove(self.log_file)
        
        # File handler with detailed formatting
        # Rotate logs instead of appending indefinitely
        # from logging.handlers import RotatingFileHandler
        # file_handler = RotatingFileHandler(self.log_file, maxBytes=5*1024*1024, backupCount=2, encoding='utf-8')
        file_handler = logging.FileHandler(self.log_file, mode='a', encoding='utf-8') # Keep simple append for now
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s - %(levelname)s - [%(name)s] - %(message)s\n' # Added logger name
        )
        file_handler.setFormatter(file_format)
        
        # Console handler with simpler formatting
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO) # Default console level
        console_format = logging.Formatter('%(levelname)s: [%(name)s] %(message)s') # Added logger name
        console_handler.setFormatter(console_format)
        
        # Add handlers only if they haven't been added before
        if not self.logger.handlers:
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)
            
        # Initialize console output tracking
        self.console_history = deque(maxlen=5)
        
        # Start new session - moved to a separate setup function
        # self._start_new_session()
    
    def _start_new_session(self):
        """Log session start with system information"""
        session_info = [
            f"\n{'='*50}",
            f"New session started at {datetime.now()}",
            f"Python version: {sys.version}",
            f"Working directory: {os.getcwd()}",
            f"Command line: {' '.join(sys.argv)}",
            f"{'='*50}\n"
        ]
        self.info('\n'.join(session_info))
    
    def _log_and_capture(self, level, msg, capture_console=True):
        """Internal logging method"""
        log_func = getattr(self.logger, level, self.logger.info) # Get correct log function
        log_func(msg)
        
        if capture_console and level in ['info', 'warning', 'error', 'critical']: # Only capture relevant levels
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.console_history.append(f"[{timestamp}] {level.upper()}: {msg}")
    
    # --- Public Logging Methods --- 
    def debug(self, msg, capture_console=False): # Usually don't capture debug to console history
        self._log_and_capture('debug', msg, capture_console)
        
    def info(self, msg, capture_console=True): 
        self._log_and_capture('info', msg, capture_console)
        
    def warning(self, msg, capture_console=True): 
        self._log_and_capture('warning', msg, capture_console)
        
    def error(self, msg, capture_console=True): 
        self._log_and_capture('error', msg, capture_console)
        
    def critical(self, msg, capture_console=True): 
        self._log_and_capture('critical', msg, capture_console)
    
    def exception(self, msg, capture_console=True):
        """Log exception with full traceback"""
        # Log the exception traceback to the file handler
        self.logger.exception(msg) 
        # Log a simpler message to console history if needed
        if capture_console:
             self._log_and_capture('error', f"{msg} (See log file for details)", True)

    def log_dataframe(self, df: pd.DataFrame, title: str ="DataFrame Output"):
        """Log DataFrame content with proper formatting"""
        # Limit rows/cols logged to file to prevent huge logs
        pd.set_option('display.max_rows', 50)
        pd.set_option('display.max_columns', 20)
        df_string = df.to_string()
        pd.reset_option('display.max_rows')
        pd.reset_option('display.max_columns')
        
        output = [
            f"\n{title}:",
            "-" * (len(title) + 1),
            df_string,
            "-" * (len(title) + 1),
            ""
        ]
        # Log full dataframe to file (DEBUG level) but not console history
        self.debug('\n'.join(output), capture_console=False)
        # Log summary to INFO
        self.info(f"{title} logged to file (rows={df.shape[0]}, cols={df.shape[1]})", capture_console=True)

    def get_console_history(self):
        """Get the last few console outputs"""
        return list(self.console_history)

# --- Setup Function --- 
# Keep global instance creation separate from class definition
def setup_logging(name="system", level=logging.INFO, log_dir="logs") -> logging.Logger:
    """Creates and configures the logger instance."""
    logger_instance = SystemLogger(name=name, log_dir=log_dir)
    logger_instance.logger.setLevel(level) # Set overall level
    # Set console handler level specifically if different
    for handler in logger_instance.logger.handlers:
        if isinstance(handler, logging.StreamHandler):
            handler.setLevel(level) 
            
    logger_instance._start_new_session() # Log session start after setup
    return logger_instance.logger

# --- Example Usage (for testing if run directly) --- 
if __name__ == "__main__":
    # Example: Set up logger with INFO level for console
    main_logger = setup_logging("main_test", level=logging.INFO)
    main_logger.debug("This debug message goes to file only.")
    main_logger.info("This info message goes to file and console.")
    main_logger.warning("This is a warning.")
    
    try:
        1 / 0
    except ZeroDivisionError:
        main_logger.exception("A deliberate error occurred!")
        
    df_test = pd.DataFrame({'A': [1, 2, 3], 'B': ['x', 'y', 'z']})
    main_logger.log_dataframe(df_test, "Test DataFrame")

    # Example: Set up another logger with DEBUG level
    debug_logger = setup_logging("debug_test", level=logging.DEBUG)
    debug_logger.debug("This debug message goes to file and console.")
    
    logger.info("\nLast few console messages from main_test:")
    logger.info(main_logger.handlers[0].__self__.get_console_history()) # Access via handler might be complex 