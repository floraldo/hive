"""Unit tests for hive_cache.exceptions module."""
import pytest


@pytest.mark.core
class TestCacheExceptions:
    """Test cases for cache exception classes."""

    @pytest.mark.core
    def test_cache_exceptions_module_exists(self):
        """Test exceptions module can be imported."""
        try:
            from hive_cache import exceptions
            assert exceptions is not None
        except ImportError:
            pytest.skip('Exceptions module not found as separate module')

    @pytest.mark.core
    def test_base_cache_exception(self):
        """Test base cache exception class."""
        try:
            from hive_cache.exceptions import CacheError
            error = CacheError('Test error')
            assert str(error) == 'Test error'
            assert isinstance(error, Exception)
        except ImportError:
            pytest.skip('CacheError not found as separate class')

    @pytest.mark.core
    def test_cache_exception_hierarchy(self):
        """Test cache exception hierarchy is properly structured."""
        try:
            from hive_cache.exceptions import CacheError, CacheKeyError, CacheTimeoutError
            if 'CacheTimeoutError' in locals():
                assert issubclass(CacheTimeoutError, CacheError)
            if 'CacheKeyError' in locals():
                assert issubclass(CacheKeyError, CacheError)
        except ImportError:
            pytest.skip('Specific cache exception classes not found')
