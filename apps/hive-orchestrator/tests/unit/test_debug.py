#!/usr/bin/env python3
"""
Quick debug test for V3.0 certification
"""

from hive_logging import get_logger

logger = get_logger(__name__)

# No sys.path manipulation needed - use Poetry workspace imports


def test_config():
    """Test configuration system"""
    try:
        from hive_config import get_config

        config = get_config()
        logger.info(f"Environment: {config.env}")
        logger.info(f"Debug mode: {config.get_bool('debug_mode')}")
        logger.info(f"Max connections: {config.get_int('db_max_connections')}")
        logger.info("Configuration test: PASSED")
        return True
    except Exception as e:
        logger.info(f"Configuration test failed: {e}")
        return False


if __name__ == "__main__":
    logger.info("Debug test starting...")
    result = test_config()
    logger.info(f"Result: {'PASSED' if result else 'FAILED'}")
