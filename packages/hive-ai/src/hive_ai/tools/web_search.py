"""Exa web search integration for real-time knowledge retrieval.

Provides access to the Exa API for high-quality web search results
that can be archived to RAG for future retrieval.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from hive_logging import get_logger

logger = get_logger(__name__)


class ExaSearchResult:
    """Single search result from Exa API."""

    def __init__(
        self,
        title: str,
        url: str,
        text: str | None = None,
        score: float | None = None,
        published_date: str | None = None,
    ):
        self.title = title
        self.url = url
        self.text = text
        self.score = score
        self.published_date = published_date

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "title": self.title,
            "url": self.url,
            "text": self.text,
            "score": self.score,
            "published_date": self.published_date,
        }


class ExaSearchClient:
    """Client for Exa web search API.

    Provides high-quality web search results with full text extraction
    for knowledge augmentation and RAG archival.

    Example:
        ```python
        client = ExaSearchClient()
        results = await client.search_async(
            query="Python async best practices",
            num_results=5,
            include_text=True
        )
        for result in results:
            print(f"{result.title}: {result.url}")
        ```

    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        """Initialize Exa search client.

        Args:
            api_key: Exa API key. If None, reads from EXA_API_KEY environment variable.
            base_url: Exa API base URL. If None, uses default production URL.

        Raises:
            ValueError: If API key is not provided and not in environment.

        """
        self.api_key = api_key or os.getenv("EXA_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Exa API key required. Provide via api_key parameter or EXA_API_KEY "
                "environment variable.",
            )

        self.base_url = base_url or "https://api.exa.ai"
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

        logger.info("Initialized Exa search client")

    async def search_async(
        self,
        query: str,
        num_results: int = 5,
        include_text: bool = True,
        use_autoprompt: bool = False,
        category: str | None = None,
        start_published_date: str | None = None,
    ) -> list[ExaSearchResult]:
        """Execute web search via Exa API.

        Args:
            query: Search query string.
            num_results: Number of results to return (1-20).
            include_text: Whether to include full text content in results.
            use_autoprompt: Let Exa optimize the query automatically.
            category: Filter by category (e.g., 'company', 'research paper', 'news').
            start_published_date: Filter by publication date (ISO format: YYYY-MM-DD).

        Returns:
            List of ExaSearchResult objects.

        Raises:
            httpx.HTTPStatusError: If API request fails.
            ValueError: If num_results is out of range.

        """
        if not 1 <= num_results <= 20:
            raise ValueError("num_results must be between 1 and 20")

        logger.info(f"Executing Exa search: '{query}' (num_results={num_results})")

        # Build request payload
        payload: dict[str, Any] = {
            "query": query,
            "numResults": num_results,
            "useAutoprompt": use_autoprompt,
        }

        if include_text:
            payload["contents"] = {"text": True}

        if category:
            payload["category"] = category

        if start_published_date:
            payload["startPublishedDate"] = start_published_date

        try:
            # Execute search
            response = await self.client.post(f"{self.base_url}/search", json=payload)
            response.raise_for_status()

            data = response.json()
            results_data = data.get("results", [])

            # Parse results
            results = []
            for item in results_data:
                result = ExaSearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    text=item.get("text") if include_text else None,
                    score=item.get("score"),
                    published_date=item.get("publishedDate"),
                )
                results.append(result)

            logger.info(f"Exa search returned {len(results)} results")
            return results

        except httpx.HTTPStatusError as e:
            logger.error(f"Exa API error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Exa search failed: {e}")
            raise

    async def search_similar_async(
        self,
        url: str,
        num_results: int = 5,
        include_text: bool = True,
    ) -> list[ExaSearchResult]:
        """Find content similar to a given URL.

        Args:
            url: URL to find similar content for.
            num_results: Number of results to return (1-20).
            include_text: Whether to include full text content in results.

        Returns:
            List of ExaSearchResult objects similar to the source URL.

        Raises:
            httpx.HTTPStatusError: If API request fails.
            ValueError: If num_results is out of range.

        """
        if not 1 <= num_results <= 20:
            raise ValueError("num_results must be between 1 and 20")

        logger.info(f"Finding content similar to: {url}")

        payload: dict[str, Any] = {
            "url": url,
            "numResults": num_results,
        }

        if include_text:
            payload["contents"] = {"text": True}

        try:
            response = await self.client.post(f"{self.base_url}/findSimilar", json=payload)
            response.raise_for_status()

            data = response.json()
            results_data = data.get("results", [])

            results = []
            for item in results_data:
                result = ExaSearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    text=item.get("text") if include_text else None,
                    score=item.get("score"),
                    published_date=item.get("publishedDate"),
                )
                results.append(result)

            logger.info(f"Found {len(results)} similar results")
            return results

        except httpx.HTTPStatusError as e:
            logger.error(f"Exa API error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Similar search failed: {e}")
            raise

    async def close(self) -> None:
        """Close the HTTP client connection."""
        await self.client.aclose()
        logger.debug("Closed Exa search client")

    async def __aenter__(self) -> ExaSearchClient:
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()
