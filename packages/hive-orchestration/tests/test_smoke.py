"""
Smoke tests for hive-orchestration package.

Verifies basic package structure and imports.
"""


def test_package_import():
    """Test that hive_orchestration package can be imported."""
    import hive_orchestration

    assert hive_orchestration is not None


def test_package_version():
    """Test that package has version."""
    import hive_orchestration

    assert hasattr(hive_orchestration, "__version__")
    assert hive_orchestration.__version__ == "1.0.0"


def test_package_all():
    """Test that __all__ is defined."""
    import hive_orchestration

    assert hasattr(hive_orchestration, "__all__")
    assert isinstance(hive_orchestration.__all__, list)


def test_logger_available():
    """Test that logger is available."""
    import hive_orchestration

    assert hasattr(hive_orchestration, "logger")
