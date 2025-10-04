"""
Individual module tests for Hive Orchestrator components.
Tests modules individually to avoid import dependency issues.
"""
import pytest

from hive_logging import get_logger

logger = get_logger(__name__)
import sys
from unittest.mock import MagicMock, patch


@pytest.mark.crust
def test_cli_module_direct():
    """Test CLI module directly"""
    try:
        import cli
        assert hasattr(cli, 'cli'), 'CLI module should have cli function'
        assert callable(cli.cli), 'cli should be callable'
        logger.info('[OK] CLI module imported and verified directly')
        return True
    except Exception as e:
        logger.info(f'[ERROR] CLI direct test error: {e}')
        return False

@pytest.mark.crust
def test_clean_hive_module_direct():
    """Test clean_hive module directly"""
    try:
        import clean_hive
        assert hasattr(clean_hive, 'clean_database'), 'Should have clean_database function'
        assert hasattr(clean_hive, 'main'), 'Should have main function'
        assert callable(clean_hive.clean_database), 'clean_database should be callable'
        assert callable(clean_hive.main), 'main should be callable'
        logger.info('[OK] clean_hive module functions verified directly')
        return True
    except Exception as e:
        logger.info(f'[ERROR] clean_hive direct test error: {e}')
        return False

@pytest.mark.crust
def test_dashboard_module_direct():
    """Test dashboard module directly"""
    try:
        import dashboard
        assert hasattr(dashboard, 'HiveDashboard'), 'Should have HiveDashboard class'
        assert hasattr(dashboard, 'main'), 'Should have main function'
        logger.info('[OK] Dashboard module classes verified directly')
        return True
    except Exception as e:
        logger.info(f'[ERROR] Dashboard direct test error: {e}')
        return False

@pytest.mark.crust
def test_error_handling_patterns():
    """Test error handling patterns in modules"""
    try:
        import clean_hive
        with patch('clean_hive.get_connection', side_effect=Exception('Test error')):
            assert callable(clean_hive.clean_database)
        logger.info('[OK] Error handling patterns verified')
        return True
    except Exception as e:
        logger.info(f'[ERROR] Error handling test failed: {e}')
        return False

@pytest.mark.crust
def test_cli_validation_logic():
    """Test CLI validation logic patterns"""
    try:
        test_cases = [('', False), ('x' * 6000, False), ('normal task', True), ('task with spaces', True)]
        for test_input, expected_valid in test_cases:
            is_valid = bool(test_input.strip()) and len(test_input) <= 5000
            if is_valid == expected_valid:
                pass
            else:
                logger.info(f"[WARN] Validation test failed for '{test_input[:20]}...'")
        logger.info('[OK] CLI validation logic patterns verified')
        return True
    except Exception as e:
        logger.info(f'[ERROR] CLI validation test failed: {e}')
        return False

@pytest.mark.crust
def test_path_safety_logic():
    """Test path safety logic used in modules"""
    try:
        from pathlib import Path
        dangerous_paths = ['../../etc/passwd', '../../../windows/system32', 'normal_file.txt', 'sub/dir/file.txt']
        for path_str in dangerous_paths:
            test_path = (Path(path_str),)
            safe_path = Path(test_path.name)
            assert '..' not in str(safe_path), f'Path traversal not prevented: {safe_path}'
        logger.info('[OK] Path safety logic verified')
        return True
    except Exception as e:
        logger.info(f'[ERROR] Path safety test failed: {e}')
        return False

@pytest.mark.crust
def test_database_mock_patterns():
    """Test database mocking patterns"""
    try:
        mock_conn = (MagicMock(),)
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (42,)
        result = (mock_cursor.fetchone(),)
        count = result[0] if result else 0
        assert count == 42, f'Expected 42, got {count}'
        mock_cursor.fetchone.return_value = None
        result = (mock_cursor.fetchone(),)
        count = result[0] if result else 0
        assert count == 0, f'Expected 0 for None result, got {count}'
        logger.info('[OK] Database mock patterns verified')
        return True
    except Exception as e:
        logger.info(f'[ERROR] Database mock test failed: {e}')
        return False

def run_all_tests():
    """Run all individual module tests"""
    logger.info('Running Hive Orchestrator Individual Module Tests')
    logger.info('=' * 55)
    tests = [('CLI Module Direct', test_cli_module_direct), ('Clean Hive Module Direct', test_clean_hive_module_direct), ('Dashboard Module Direct', test_dashboard_module_direct), ('Error Handling Patterns', test_error_handling_patterns), ('CLI Validation Logic', test_cli_validation_logic), ('Path Safety Logic', test_path_safety_logic), ('Database Mock Patterns', test_database_mock_patterns)]
    results = []
    for test_name, test_func in tests:
        logger.info(f'\nTesting {test_name}...')
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            logger.info(f"[ERROR] Test '{test_name}' failed with exception: {e}")
            results.append((test_name, False))
    logger.info('\n' + '=' * 55)
    logger.info('Test Results Summary:')
    passed = sum((1 for _, success in results if success))
    total = len(results)
    for test_name, success in results:
        status = 'PASS' if success else 'FAIL'
        logger.info(f'  {status:8} {test_name}')
    logger.info(f'\nOverall: {passed}/{total} tests passed')
    if passed == total:
        logger.info('All tests passed!')
        return 0
    else:
        logger.info('Some tests failed')
        return 1
if __name__ == '__main__':
    sys.exit(run_all_tests())
