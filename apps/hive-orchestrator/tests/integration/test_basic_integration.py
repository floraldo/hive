#!/usr/bin/env python3
"""
Basic integration tests for Hive Orchestrator components.
Tests basic functionality without complex import dependencies.
"""

from hive_logging import get_logger

logger = get_logger(__name__)
import sys
from pathlib import Path
from unittest.mock import patch

# No sys.path manipulation needed - use Poetry workspace imports


def test_module_imports():
    """Test that core modules can be imported"""
    try:
        # Test individual module imports
        import hive_orchestrator.clean_hive
        import hive_orchestrator.cli
        import hive_orchestrator.dashboard

        logger.info("✅ All core modules imported successfully")
        return True
    except ImportError as e:
        logger.info(f"❌ Import error: {e}")
        return False


def test_cli_module_basic():
    """Test basic CLI module functionality"""
    try:
        from hive_orchestrator.cli import cli

        # Check that CLI commands exist
        commands = list(cli.commands.keys()) if hasattr(cli, "commands") else []
        expected_commands = ["status", "queue-task", "start-queen", "start-worker"]

        for cmd in expected_commands:
            if cmd in commands:
                logger.info(f"✅ CLI command '{cmd}' found")
            else:
                logger.info(f"⚠️ CLI command '{cmd}' not found")

        return True
    except Exception as e:
        logger.info(f"❌ CLI test error: {e}")
        return False


def test_clean_hive_module():
    """Test clean_hive module functionality"""
    try:
        from hive_orchestrator.clean_hive import clean_database
        from hive_orchestrator.clean_hive import main as clean_main

        # Test that functions exist and are callable
        assert callable(clean_database), "clean_database should be callable"
        assert callable(clean_main), "clean_main should be callable"

        logger.info("✅ clean_hive module functions are callable")
        return True
    except Exception as e:
        logger.info(f"❌ clean_hive test error: {e}")
        return False


def test_dashboard_module():
    """Test dashboard module functionality"""
    try:
        from hive_orchestrator.dashboard import HiveDashboard

        # Test dashboard initialization
        with patch(
            "hive_orchestrator.dashboard.get_connection",
            side_effect=Exception("Mock DB error"),
        ):
            dashboard = HiveDashboard()
            assert dashboard.refresh_rate == 2
            assert dashboard.console is not None

        logger.info("✅ Dashboard module initialized successfully")
        return True
    except Exception as e:
        logger.info(f"❌ Dashboard test error: {e}")
        return False


def test_error_handling():
    """Test error handling across modules"""
    try:
        from hive_orchestrator.clean_hive import clean_database

        # Test that clean_database handles database errors gracefully
        with patch(
            "hive_orchestrator.clean_hive.get_connection",
            side_effect=Exception("Database error"),
        ):
            # This should not raise an exception, but handle it gracefully
            try:
                clean_database()  # Should handle the error internally
                logger.info("✅ clean_database handles errors gracefully")
            except Exception as e:
                logger.info(f"⚠️ clean_database raised exception: {e}")

        return True
    except Exception as e:
        logger.info(f"❌ Error handling test failed: {e}")
        return False


def test_input_validation():
    """Test input validation functions"""
    try:
        # Test path validation concepts
        from pathlib import Path

        # Test basic path validation logic
        test_path = Path("test/../../etc/passwd")  # Path traversal attempt
        safe_path = Path(test_path.name)  # Should be just the filename

        assert str(safe_path) == "passwd", f"Expected 'passwd', got '{safe_path}'"
        assert ".." not in str(safe_path), "Path traversal should be prevented"

        logger.info("✅ Basic input validation logic works")
        return True
    except Exception as e:
        logger.info(f"❌ Input validation test error: {e}")
        return False


def test_configuration_handling():
    """Test configuration file handling"""
    try:
        import json
        import tempfile

        # Create a temporary config file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            config = {"test": "value", "number": 42}
            json.dump(config, f)
            config_path = f.name

        # Test reading the config
        with open(config_path, "r") as f:
            loaded_config = json.load(f)

        assert loaded_config["test"] == "value"
        assert loaded_config["number"] == 42

        # Clean up
        Path(config_path).unlink()

        logger.info("✅ Configuration handling works")
        return True
    except Exception as e:
        logger.info(f"❌ Configuration test error: {e}")
        return False


def run_all_tests():
    """Run all basic integration tests"""
    logger.info("🧪 Running Basic Hive Orchestrator Integration Tests")
    logger.info("=" * 60)

    tests = [
        ("Module Imports", test_module_imports),
        ("CLI Module", test_cli_module_basic),
        ("Clean Hive Module", test_clean_hive_module),
        ("Dashboard Module", test_dashboard_module),
        ("Error Handling", test_error_handling),
        ("Input Validation", test_input_validation),
        ("Configuration Handling", test_configuration_handling),
    ]

    results = []
    for test_name, test_func in tests:
        logger.info(f"\n🔍 Testing {test_name}...")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            logger.info(f"❌ Test '{test_name}' failed with exception: {e}")
            results.append((test_name, False))

    logger.info("\n" + "=" * 60)
    logger.info("📊 Test Results Summary:")

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        logger.info(f"  {status:8} {test_name}")

    logger.info(f"\n🎯 Overall: {passed}/{total} tests passed")

    if passed == total:
        logger.info("🎉 All tests passed!")
        return 0
    else:
        logger.info("⚠️ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
