"""
Pytest configuration for hive-test-intelligence.

Ensures the plugin is loaded during test execution.
"""
pytest_plugins = ["hive_test_intelligence.collector"]
