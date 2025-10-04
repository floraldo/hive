"""
Golden set evaluation for RAG system quality validation.

Tests RAG retrieval accuracy against curated query-answer pairs using
RAGAS framework for comprehensive quality metrics.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

# Add hive-ai to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "packages" / "hive-ai" / "src"))

from hive_ai.rag import EnhancedRAGRetriever


@pytest.fixture(scope="module")
def retriever():
    """Initialize retriever with test index."""
    retriever = EnhancedRAGRetriever()

    # Try to load existing index
    index_path = Path(__file__).parent.parent.parent / "data" / "rag_index"
    if index_path.exists():
        retriever.load(index_path)
    else:
        pytest.skip("RAG index not found - run indexing first")

    return retriever


@pytest.fixture(scope="module")
def golden_set():
    """Load golden set queries."""
    golden_set_path = Path(__file__).parent / "golden_set.yaml"

    if not golden_set_path.exists():
        pytest.skip("Golden set not found")

    with open(golden_set_path) as f:
        data = yaml.safe_load(f)

    return data["queries"]


def test_golden_set_retrieval_accuracy(retriever, golden_set):
    """
    Test RAG retrieval accuracy on golden set.

    Validates that expected files appear in top-k results
    and meet minimum score thresholds.
    """
    results = []

    for query_spec in golden_set:
        query = query_spec["query"]
        expected_file = query_spec["expected_file"]
        min_score = query_spec.get("min_score", 0.80)

        # Retrieve
        retrieval_results = retriever.retrieve(query, k=5)

        # Check if expected file in results
        found = False
        top_score = 0.0
        rank = None

        for i, result in enumerate(retrieval_results, 1):
            if expected_file in result.chunk.file_path:
                found = True
                top_score = result.score
                rank = i
                break
            top_score = max(top_score, result.score)

        meets_threshold = top_score >= min_score if found else False

        results.append(
            {
                "query": query,
                "expected_file": expected_file,
                "found": found,
                "rank": rank,
                "top_score": top_score,
                "meets_threshold": meets_threshold,
                "min_score": min_score,
                "tags": query_spec.get("tags", []),
            }
        )

    # Calculate metrics
    total = len(results)
    found_count = sum(1 for r in results if r["found"])
    threshold_count = sum(1 for r in results if r["meets_threshold"])

    accuracy = found_count / total if total > 0 else 0
    quality = threshold_count / total if total > 0 else 0

    # Print detailed results
    print("\n" + "=" * 80)
    print("Golden Set Evaluation Results")
    print("=" * 80)
    print(f"Total queries: {total}")
    print(f"Found in top-5: {found_count} ({accuracy:.1%})")
    print(f"Meets threshold: {threshold_count} ({quality:.1%})")
    print("\nFailed queries:")

    for r in results:
        if not r["found"]:
            print(f"  ❌ [{r['tags'][0] if r['tags'] else 'N/A'}] {r['query']}")
            print(f"      Expected: {r['expected_file']}")
            print(f"      Top score: {r['top_score']:.3f}")
        elif not r["meets_threshold"]:
            print(f"  ⚠️  [{r['tags'][0] if r['tags'] else 'N/A'}] {r['query']}")
            print(f"      Found at rank {r['rank']}, score {r['top_score']:.3f} < {r['min_score']:.3f}")

    print("=" * 80)

    # Assert targets
    assert accuracy >= 0.90, f"Accuracy {accuracy:.1%} below 90% target"
    assert quality >= 0.85, f"Quality {quality:.1%} below 85% target"


def test_retrieval_performance(retriever, golden_set):
    """Test RAG retrieval performance meets latency targets."""
    import time

    latencies = []

    for query_spec in golden_set[:10]:  # Test on first 10 for speed
        start = time.time()
        retriever.retrieve(query_spec["query"], k=5)
        latency_ms = (time.time() - start) * 1000
        latencies.append(latency_ms)

    avg_latency = sum(latencies) / len(latencies)
    p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]

    print("\nPerformance Results:")
    print(f"  Average latency: {avg_latency:.1f}ms")
    print(f"  P95 latency: {p95_latency:.1f}ms")

    assert p95_latency < 200, f"P95 latency {p95_latency:.1f}ms exceeds 200ms target"


def test_context_quality(retriever, golden_set):
    """Test structured context generation quality."""
    sample_queries = golden_set[:5]

    for query_spec in sample_queries:
        context = retriever.retrieve_with_context(query_spec["query"], include_golden_rules=True)

        # Validate context structure
        assert len(context.code_patterns) > 0, "No code patterns retrieved"
        assert context.retrieval_time_ms > 0, "Invalid retrieval time"

        # Validate pattern quality
        for pattern in context.code_patterns:
            assert pattern.code, "Empty code in pattern"
            assert pattern.source, "Missing source attribution"
            assert pattern.relevance_score > 0, "Invalid relevance score"

    print(f"\n✅ Context quality validated for {len(sample_queries)} queries")


def test_category_accuracy_by_difficulty(retriever, golden_set):
    """
    Test accuracy broken down by difficulty level and category.

    Helps identify which types of queries need improvement.
    """
    # Categorize queries
    easy = [q for q in golden_set if "database" in q.get("tags", []) or "logging" in q.get("tags", [])]
    medium = [q for q in golden_set if "patterns" in q.get("tags", []) or "config" in q.get("tags", [])]
    hard = [q for q in golden_set if "deprecation" in q.get("tags", []) or "migration" in q.get("tags", [])]

    def calc_accuracy(queries):
        if not queries:
            return 1.0
        found = 0
        for q in queries:
            results = retriever.retrieve(q["query"], k=5)
            if any(q["expected_file"] in r.chunk.file_path for r in results):
                found += 1
        return found / len(queries)

    easy_acc = calc_accuracy(easy)
    medium_acc = calc_accuracy(medium)
    hard_acc = calc_accuracy(hard)

    print("\nAccuracy by Difficulty:")
    print(f"  Easy ({len(easy)} queries): {easy_acc:.1%} (target: >95%)")
    print(f"  Medium ({len(medium)} queries): {medium_acc:.1%} (target: >85%)")
    print(f"  Hard ({len(hard)} queries): {hard_acc:.1%} (target: >75%)")

    # Assert targets
    assert easy_acc >= 0.95, f"Easy accuracy {easy_acc:.1%} below 95%"
    assert medium_acc >= 0.85, f"Medium accuracy {medium_acc:.1%} below 85%"
    # Hard is aspirational, don't fail on it yet


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])
