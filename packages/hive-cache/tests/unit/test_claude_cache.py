"""Unit tests for hive_cache.claude_cache module."""
from unittest.mock import Mock, patch

import pytest

from hive_cache.claude_cache import ClaudeAPICache


@pytest.mark.core
class TestClaudeCache:
    """Test cases for ClaudeAPICache class."""

    @pytest.mark.core
    def test_claude_cache_initialization(self):
        """Test ClaudeAPICache can be initialized."""
        cache = ClaudeAPICache()
        assert cache is not None

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_claude_cache_basic_operations(self):
        """Test basic cache operations work."""
        cache = ClaudeAPICache()
        assert hasattr(cache, 'get')
        assert hasattr(cache, 'set')
        assert hasattr(cache, 'clear')

    @pytest.mark.core
    def test_claude_cache_config_handling(self):
        """Test cache handles configuration properly."""
        mock_config = Mock()
        with patch('hive_cache.claude_cache.load_config', return_value=mock_config):
            cache = ClaudeAPICache()
            assert cache is not None
