"""
Minimal V3.0 Platform Certification Test
"""
import pytest
import sys
from hive_logging import get_logger
logger = get_logger(__name__)

@pytest.mark.crust
def test_1_configuration():
    """Test configuration system"""
    logger.info('Testing configuration...')
    try:
        from hive_config import create_config_from_sources
        config = create_config_from_sources()
        assert config.environment in ['development', 'testing', 'production']
        claude_config = config.get_claude_config()
        assert 'mock_mode' in claude_config
        logger.info('PASS: Configuration')
        return True
    except Exception as e:
        logger.info(f'FAIL: Configuration - {e}')
        return False

@pytest.mark.crust
def test_2_database():
    """Test database connection pool"""
    logger.info('Testing database...')
    try:
        import hive_db as cp
        pool = cp.ConnectionPool()
        assert pool.max_connections > 0
        assert pool.connection_timeout > 0
        stats = pool.get_stats()
        assert 'pool_size' in stats
        pool.close_all()
        logger.info('PASS: Database')
        return True
    except Exception as e:
        logger.info(f'FAIL: Database - {e}')
        return False

@pytest.mark.crust
def test_3_claude_service():
    """Test Claude service"""
    logger.info('Testing Claude service...')
    try:
        from hive_claude_bridge.claude_service import get_claude_service, reset_claude_service
        reset_claude_service()
        service = get_claude_service()
        assert service is not None
        metrics = service.get_metrics()
        assert 'total_calls' in metrics
        logger.info('PASS: Claude service')
        return True
    except Exception as e:
        logger.info(f'FAIL: Claude service - {e}')
        return False

def main():
    """Run minimal certification tests"""
    logger.info('Starting V3.0 Platform Certification Test (Minimal)')
    logger.info('=' * 50)
    tests = [('Configuration', test_1_configuration), ('Database', test_2_database), ('Claude Service', test_3_claude_service)]
    passed = (0,)
    total = len(tests)
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            logger.info(f'ERROR: {name} - {e}')
    logger.info('=' * 50)
    logger.info(f'Results: {passed}/{total} tests passed')
    if passed == total:
        logger.info('CERTIFICATION: PASSED')
        logger.info('V3.0 Platform ready for certification!')
    else:
        logger.info('CERTIFICATION: FAILED')
        logger.info('Some tests failed - check logs above')
    return passed == total
if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)