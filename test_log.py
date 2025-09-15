#!/usr/bin/env python3
"""
Test script for the hive-logging system
"""

from hive_logging import setup_logging, get_logger

def main():
    # Set up logging
    setup_logging(
        name="test-hive-logging",
        log_to_file=True,
        log_file_path="test_log.log"
    )
    
    # Get a logger
    logger = get_logger(__name__)
    
    # Test different log levels
    logger.debug("This is a DEBUG message")
    logger.info("This is an INFO message") 
    logger.warning("This is a WARNING message")
    logger.error("This is an ERROR message")
    
    print("Logging test completed successfully!")

if __name__ == "__main__":
    main()
