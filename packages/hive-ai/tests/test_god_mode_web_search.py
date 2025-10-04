"""
Unit tests for Exa web search client.

Tests cover:
- Search functionality
- Similar content discovery
- Error handling
- API response parsing
- Client lifecycle management
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from hive_ai.tools.web_search import ExaSearchClient, ExaSearchResult


class TestExaSearchClient:
    """Test Exa search client initialization and configuration."""

    def test_client_initialization_with_api_key(self):
        """Test client initialization with explicit API key."""
        client = ExaSearchClient(api_key="test-key-123")

        assert client.api_key == "test-key-123"
        assert client.base_url == "https://api.exa.ai"
        assert client.client is not None

    def test_client_initialization_from_environment(self):
        """Test client initialization from environment variable."""
        with patch.dict(os.environ, {"EXA_API_KEY": "env-key-456"}):
            client = ExaSearchClient()

            assert client.api_key == "env-key-456"

    def test_client_initialization_without_api_key_raises_error(self):
        """Test that missing API key raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove EXA_API_KEY if it exists
            os.environ.pop("EXA_API_KEY", None)

            with pytest.raises(ValueError) as exc_info:
                ExaSearchClient()

            assert "api key required" in str(exc_info.value).lower()

    def test_client_custom_base_url(self):
        """Test client with custom base URL."""
        client = ExaSearchClient(
            api_key="test-key",
            base_url="https://custom.exa.api"
        )

        assert client.base_url == "https://custom.exa.api"


class TestExaSearch:
    """Test search functionality."""

    @pytest.mark.asyncio
    async def test_search_basic_query(self):
        """Test basic search with mock response."""
        client = ExaSearchClient(api_key="test-key")

        mock_response = {
            "results": [
                {
                    "title": "Python Async Guide",
                    "url": "https://example.com/async",
                    "text": "Learn about async/await...",
                    "score": 0.95,
                    "publishedDate": "2024-01-15"
                },
                {
                    "title": "Advanced Async Patterns",
                    "url": "https://example.com/patterns",
                    "text": "Deep dive into async patterns...",
                    "score": 0.88,
                }
            ]
        }

        with patch.object(client.client, 'post', new_callable=AsyncMock) as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_response
            mock_resp.raise_for_status = MagicMock()
            mock_post.return_value = mock_resp

            results = await client.search_async(
                query="Python async best practices",
                num_results=2,
            )

            assert len(results) == 2
            assert results[0].title == "Python Async Guide"
            assert results[0].url == "https://example.com/async"
            assert results[0].text == "Learn about async/await..."
            assert results[0].score == 0.95
            assert results[1].published_date is None  # Not in response

    @pytest.mark.asyncio
    async def test_search_with_text_disabled(self):
        """Test search without text content."""
        client = ExaSearchClient(api_key="test-key")

        mock_response = {
            "results": [
                {
                    "title": "Test Article",
                    "url": "https://example.com/test",
                    "score": 0.9,
                }
            ]
        }

        with patch.object(client.client, 'post', new_callable=AsyncMock) as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_response
            mock_resp.raise_for_status = MagicMock()
            mock_post.return_value = mock_resp

            results = await client.search_async(
                query="test query",
                include_text=False,
            )

            assert len(results) == 1
            assert results[0].text is None

            # Verify request payload didn't include contents
            call_args = mock_post.call_args
            payload = call_args.kwargs['json']
            assert 'contents' not in payload

    @pytest.mark.asyncio
    async def test_search_with_filters(self):
        """Test search with category and date filters."""
        client = ExaSearchClient(api_key="test-key")

        mock_response = {"results": []}

        with patch.object(client.client, 'post', new_callable=AsyncMock) as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_response
            mock_resp.raise_for_status = MagicMock()
            mock_post.return_value = mock_resp

            await client.search_async(
                query="research papers",
                category="research paper",
                start_published_date="2024-01-01",
                use_autoprompt=True,
            )

            # Verify filters in request
            call_args = mock_post.call_args
            payload = call_args.kwargs['json']

            assert payload['category'] == "research paper"
            assert payload['startPublishedDate'] == "2024-01-01"
            assert payload['useAutoprompt'] is True

    @pytest.mark.asyncio
    async def test_search_num_results_validation(self):
        """Test validation of num_results parameter."""
        client = ExaSearchClient(api_key="test-key")

        # Too few
        with pytest.raises(ValueError) as exc_info:
            await client.search_async("test", num_results=0)
        assert "between 1 and 20" in str(exc_info.value)

        # Too many
        with pytest.raises(ValueError) as exc_info:
            await client.search_async("test", num_results=25)
        assert "between 1 and 20" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_search_api_error_handling(self):
        """Test handling of API errors."""
        client = ExaSearchClient(api_key="test-key")

        with patch.object(client.client, 'post', new_callable=AsyncMock) as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 429
            mock_resp.text = "Rate limit exceeded"
            mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Rate limit",
                request=MagicMock(),
                response=mock_resp
            )
            mock_post.return_value = mock_resp

            with pytest.raises(httpx.HTTPStatusError):
                await client.search_async("test query")

    @pytest.mark.asyncio
    async def test_search_empty_results(self):
        """Test handling of empty search results."""
        client = ExaSearchClient(api_key="test-key")

        mock_response = {"results": []}

        with patch.object(client.client, 'post', new_callable=AsyncMock) as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_response
            mock_resp.raise_for_status = MagicMock()
            mock_post.return_value = mock_resp

            results = await client.search_async("obscure query")

            assert len(results) == 0
            assert isinstance(results, list)


class TestExaSimilarSearch:
    """Test similar content search functionality."""

    @pytest.mark.asyncio
    async def test_search_similar_basic(self):
        """Test finding similar content by URL."""
        client = ExaSearchClient(api_key="test-key")

        mock_response = {
            "results": [
                {
                    "title": "Similar Article 1",
                    "url": "https://example.com/similar1",
                    "text": "Similar content here...",
                    "score": 0.92,
                }
            ]
        }

        with patch.object(client.client, 'post', new_callable=AsyncMock) as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_response
            mock_resp.raise_for_status = MagicMock()
            mock_post.return_value = mock_resp

            results = await client.search_similar_async(
                url="https://example.com/source",
                num_results=5,
            )

            assert len(results) == 1
            assert results[0].title == "Similar Article 1"

            # Verify correct endpoint and payload
            call_args = mock_post.call_args
            assert call_args.args[0] == "https://api.exa.ai/findSimilar"
            payload = call_args.kwargs['json']
            assert payload['url'] == "https://example.com/source"
            assert payload['numResults'] == 5

    @pytest.mark.asyncio
    async def test_search_similar_validation(self):
        """Test validation for similar search."""
        client = ExaSearchClient(api_key="test-key")

        with pytest.raises(ValueError):
            await client.search_similar_async(
                url="https://example.com",
                num_results=25  # Too many
            )


class TestExaSearchResult:
    """Test ExaSearchResult data model."""

    def test_search_result_creation(self):
        """Test creating search result instances."""
        result = ExaSearchResult(
            title="Test Article",
            url="https://example.com/test",
            text="Article content...",
            score=0.95,
            published_date="2024-01-15",
        )

        assert result.title == "Test Article"
        assert result.url == "https://example.com/test"
        assert result.text == "Article content..."
        assert result.score == 0.95
        assert result.published_date == "2024-01-15"

    def test_search_result_minimal_fields(self):
        """Test search result with only required fields."""
        result = ExaSearchResult(
            title="Minimal Result",
            url="https://example.com/min",
        )

        assert result.title == "Minimal Result"
        assert result.url == "https://example.com/min"
        assert result.text is None
        assert result.score is None
        assert result.published_date is None

    def test_search_result_to_dict(self):
        """Test conversion to dictionary."""
        result = ExaSearchResult(
            title="Dict Test",
            url="https://example.com/dict",
            text="Content",
            score=0.88,
        )

        result_dict = result.to_dict()

        assert result_dict == {
            "title": "Dict Test",
            "url": "https://example.com/dict",
            "text": "Content",
            "score": 0.88,
            "published_date": None,
        }


class TestClientLifecycle:
    """Test client lifecycle and resource management."""

    @pytest.mark.asyncio
    async def test_client_close(self):
        """Test closing the client."""
        client = ExaSearchClient(api_key="test-key")

        with patch.object(client.client, 'aclose', new_callable=AsyncMock) as mock_close:
            await client.close()

            mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_client_context_manager(self):
        """Test using client as async context manager."""
        close_called = False

        async def mock_aclose():
            nonlocal close_called
            close_called = True

        with patch.object(httpx.AsyncClient, 'aclose', new=mock_aclose):
            async with ExaSearchClient(api_key="test-key") as client:
                assert client.api_key == "test-key"

            assert close_called is True


class TestIntegrationWithAgent:
    """Test integration between ExaSearchClient and BaseAgent."""

    @pytest.mark.asyncio
    async def test_agent_web_search_tool(self):
        """Test agent's web search tool wrapper."""
        from hive_ai.agents.agent import BaseAgent
        from hive_ai.core.config import AgentConfig

        # Create agent with web search enabled (will fail gracefully without API key)
        config = AgentConfig(enable_exa_search=True)
        agent = BaseAgent(config=config)

        # Since we don't have API key in tests, client should be None
        assert agent._web_search_client is None

        # But if we mock it...
        mock_client = MagicMock(spec=ExaSearchClient)
        mock_results = [
            ExaSearchResult(
                title="Result 1",
                url="https://example.com/1",
                text="Content 1",
            )
        ]

        async def mock_search(**kwargs):
            return mock_results

        mock_client.search_async = mock_search
        agent._web_search_client = mock_client

        # Now register the tool
        agent._tools["web_search"] = agent._web_search_tool

        # Call the tool
        results = await agent.call_tool_async(
            "web_search",
            query="test query",
        )

        assert len(results) == 1
        assert results[0]["title"] == "Result 1"
        assert results[0]["url"] == "https://example.com/1"

    @pytest.mark.asyncio
    async def test_agent_web_search_error_handling(self):
        """Test agent's handling of web search errors."""
        from hive_ai.agents.agent import BaseAgent
        from hive_ai.core.config import AgentConfig

        config = AgentConfig(enable_exa_search=True)
        agent = BaseAgent(config=config)

        # Tool should raise error if client not initialized
        agent._tools["web_search"] = agent._web_search_tool

        with pytest.raises(RuntimeError) as exc_info:
            await agent.call_tool_async("web_search", query="test")

        assert "not initialized" in str(exc_info.value).lower()
