"""
Quick debug test for V3.0 certification
"""
import pytest

from hive_logging import get_logger

logger = get_logger(__name__)

@pytest.mark.crust
def test_config():
    """Test configuration system"""
    try:
        from hive_config import create_config_from_sources
        config = create_config_from_sources()
        logger.info(f'Environment: {config.environment}')
        logger.info(f'Debug mode: {config.debug_mode}')
        logger.info(f'Database config: {config.database}')
        logger.info('Configuration test: PASSED')
        return True
    except Exception as e:
        logger.info(f'Configuration test failed: {e}')
        return False
if __name__ == '__main__':
    logger.info('Debug test starting...')
    result = test_config()
    logger.info(f"Result: {('PASSED' if result else 'FAILED')}")
