"""Test client for RAG API.

Simple script to validate the RAG API functionality with sample queries.

Usage:
    # Start server first: python scripts/rag/start_api.py

    # Run tests
    python scripts/rag/test_api.py

    # Single query test
    python scripts/rag/test_api.py --query "How do I use logging?"

    # Custom server
    python scripts/rag/test_api.py --url http://localhost:9000
"""

import argparse
import sys
import time
from typing import Any

try:
    import httpx
except ImportError:
    print("Error: httpx not installed. Run: pip install httpx")
    sys.exit(1)


class RAGAPITest:
    """Test client for RAG API."""

    def __init__(self, base_url: str = "http://localhost:8765"):
        self.base_url = base_url
        self.client = httpx.Client(base_url=base_url, timeout=30.0)

    def test_health(self) -> dict[str, Any]:
        """Test health check endpoint."""
        print("Testing /health endpoint...")
        try:
            response = self.client.get("/health")
            response.raise_for_status()
            data = response.json()

            print(f"  Status: {data['status']}")
            print(f"  Index available: {data['index_available']}")
            print(f"  Total chunks: {data['total_chunks']}")
            print(f"  Last indexed: {data.get('last_indexed', 'N/A')}")
            print(f"  Uptime: {data['uptime_seconds']:.2f}s")

            return data
        except httpx.HTTPError as e:
            print(f"  Error: {e}")
            return {}

    def test_query(
        self,
        query: str,
        session_id: str = "test-session",
        max_results: int = 5,
        formatting_style: str = "minimal",
    ) -> dict[str, Any]:
        """Test query endpoint."""
        print("\nTesting /query endpoint...")
        print(f"  Query: {query}")

        try:
            start = time.time()
            response = self.client.post(
                "/query",
                json={
                    "query": query,
                    "session_id": session_id,
                    "max_results": max_results,
                    "formatting_style": formatting_style,
                    "include_metadata": True,
                },
            )
            elapsed = (time.time() - start) * 1000

            response.raise_for_status()
            data = response.json()

            print(f"  Results: {data['metadata']['total_results']}")
            print(f"  Cache hit: {data['metadata']['cache_hit']}")
            print(f"  Server time: {data['performance_ms']:.2f}ms")
            print(f"  Total time: {elapsed:.2f}ms")

            print("\n  Formatted Context:")
            print("  " + "-" * 60)
            # Print first 500 chars of context
            context = data["formatted_context"]
            if len(context) > 500:
                print(f"  {context[:500]}...")
            else:
                print(f"  {context}")
            print("  " + "-" * 60)

            if data["chunks"]:
                print("\n  Sample chunks:")
                for i, chunk in enumerate(data["chunks"][:3], 1):
                    meta = chunk.get("metadata", {})
                    print(f"    {i}. {meta.get('file_path', 'unknown')}")
                    print(f"       Score: {meta.get('score', 0):.3f}")
                    print(f"       Lines: {meta.get('start_line', '?')}-{meta.get('end_line', '?')}")

            return data
        except httpx.HTTPError as e:
            print(f"  Error: {e}")
            if hasattr(e, "response") and e.response:
                try:
                    error_detail = e.response.json()
                    print(f"  Detail: {error_detail}")
                except Exception:
                    print(f"  Response: {e.response.text}")
            return {}

    def test_stats(self) -> dict[str, Any]:
        """Test stats endpoint."""
        print("\nTesting /stats endpoint...")
        try:
            response = self.client.get("/stats")
            response.raise_for_status()
            data = response.json()

            print(f"  Uptime: {data['uptime_seconds']:.2f}s")
            print(f"  Total queries: {data['total_queries']}")
            print(f"  Queries/min: {data['queries_per_minute']:.2f}")
            print(f"  Index available: {data['index_available']}")

            return data
        except httpx.HTTPError as e:
            print(f"  Error: {e}")
            return {}

    def run_all_tests(self) -> bool:
        """Run all API tests."""
        print("=" * 70)
        print("RAG API Test Suite")
        print("=" * 70)

        # Test health
        health = self.test_health()
        if not health or health.get("status") != "healthy":
            print("\n⚠ Warning: API not healthy, some tests may fail")

        # Test queries
        test_queries = [
            "How do I use the logging system?",
            "What is the purpose of hive-orchestration package?",
            "How do I create a new validator in golden rules?",
        ]

        for i, query in enumerate(test_queries, 1):
            print(f"\n{'=' * 70}")
            print(f"Query Test {i}/{len(test_queries)}")
            print(f"{'=' * 70}")
            result = self.test_query(query)
            if not result:
                print("  ❌ Query failed")
                return False
            time.sleep(0.5)  # Brief pause between tests

        # Test cache hit (repeat last query)
        print(f"\n{'=' * 70}")
        print("Cache Test (Repeat Query)")
        print(f"{'=' * 70}")
        result = self.test_query(test_queries[-1])
        if result and result["metadata"].get("cache_hit"):
            print("  ✅ Cache working")
        else:
            print("  ⚠ Cache not hit (may be expected)")

        # Test stats
        self.test_stats()

        print("\n" + "=" * 70)
        print("✅ All tests completed successfully!")
        print("=" * 70)

        return True


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Test RAG API")
    parser.add_argument(
        "--url",
        default="http://localhost:8765",
        help="Base URL of RAG API",
    )
    parser.add_argument(
        "--query",
        help="Single query to test (instead of full test suite)",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=5,
        help="Maximum results to return",
    )
    parser.add_argument(
        "--formatting-style",
        choices=["instructional", "structured", "minimal", "markdown"],
        default="minimal",
        help="Formatting style for response",
    )

    args = parser.parse_args()

    tester = RAGAPITest(base_url=args.url)

    try:
        if args.query:
            # Single query test
            print("=" * 70)
            print("Single Query Test")
            print("=" * 70)
            tester.test_health()
            result = tester.test_query(
                args.query,
                max_results=args.max_results,
                formatting_style=args.formatting_style,
            )
            return 0 if result else 1
        # Full test suite
        success = tester.run_all_tests()
        return 0 if success else 1

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        return 1
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
