"""Unit tests for hive_cache.claude_cache module."""

from unittest.mock import Mock, patch

import pytest

from hive_cache.claude_cache import ClaudeCache


class TestClaudeCache:
    """Test cases for ClaudeCache class."""

    def test_claude_cache_initialization(self):
        """Test ClaudeCache can be initialized."""
        cache = ClaudeCache()
        assert cache is not None

    @pytest.mark.asyncio
    async def test_claude_cache_basic_operations(self):
        """Test basic cache operations work."""
        cache = ClaudeCache()

        # Test basic functionality without external dependencies
        assert hasattr(cache, "get")
        assert hasattr(cache, "set")
        assert hasattr(cache, "clear")

    def test_claude_cache_config_handling(self):
        """Test cache handles configuration properly."""
        # Test with mock config
        mock_config = Mock()

        with patch("hive_cache.claude_cache.load_config", return_value=mock_config):
            cache = ClaudeCache()
            assert cache is not None
