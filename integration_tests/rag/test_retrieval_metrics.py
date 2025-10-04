"""
Simplified RAG retrieval metrics without external dependencies.

Provides core retrieval quality metrics that can run without RAGAS:
- Precision@k: Proportion of retrieved results that are relevant
- Recall@k: Proportion of relevant results that are retrieved
- MRR (Mean Reciprocal Rank): Average of reciprocal ranks of first relevant result
- NDCG@k: Normalized Discounted Cumulative Gain for ranking quality
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


def calculate_precision_at_k(retrieved_files: list[str], relevant_file: str, k: int) -> float:
    """Calculate precision@k: proportion of top-k results that are relevant."""
    if not retrieved_files:
        return 0.0

    top_k = retrieved_files[:k]
    relevant_count = sum(1 for f in top_k if relevant_file in f)
    return relevant_count / len(top_k)


def calculate_recall_at_k(retrieved_files: list[str], relevant_file: str, k: int) -> float:
    """Calculate recall@k: whether the relevant file was retrieved in top-k."""
    if not retrieved_files:
        return 0.0

    top_k = retrieved_files[:k]
    return 1.0 if any(relevant_file in f for f in top_k) else 0.0


def calculate_mrr(retrieved_files: list[str], relevant_file: str) -> float:
    """Calculate Mean Reciprocal Rank: 1/rank of first relevant result."""
    for i, file_path in enumerate(retrieved_files, 1):
        if relevant_file in file_path:
            return 1.0 / i
    return 0.0


def calculate_ndcg_at_k(retrieved_files: list[str], relevant_file: str, k: int) -> float:
    """
    Calculate NDCG@k (Normalized Discounted Cumulative Gain).

    Simplified version: relevant=1, not relevant=0.
    """
    import math

    if not retrieved_files:
        return 0.0

    # DCG: sum of (relevance / log2(rank+1))
    dcg = 0.0
    for i, file_path in enumerate(retrieved_files[:k], 1):
        relevance = 1.0 if relevant_file in file_path else 0.0
        dcg += relevance / math.log2(i + 1)

    # IDCG: best possible DCG (relevant item at rank 1)
    idcg = 1.0 / math.log2(2)  # Single relevant item at position 1

    return dcg / idcg if idcg > 0 else 0.0


def test_retrieval_metrics_comprehensive(retriever, golden_set):
    """
    Comprehensive retrieval metrics evaluation.

    Metrics:
    - Precision@k: How many retrieved results are relevant?
    - Recall@k: Did we retrieve the relevant result?
    - MRR: How high is the relevant result ranked?
    - NDCG@k: Quality of ranking
    """
    k_values = [1, 3, 5, 10]
    metrics = {k: {"precision": [], "recall": [], "mrr": [], "ndcg": []} for k in k_values}

    for query_spec in golden_set:
        query = query_spec["query"]
        expected_file = query_spec["expected_file"]

        # Retrieve results
        results = retriever.retrieve(query, k=max(k_values))
        retrieved_files = [r.chunk.file_path for r in results]

        # Calculate metrics for each k
        for k in k_values:
            metrics[k]["precision"].append(calculate_precision_at_k(retrieved_files, expected_file, k))
            metrics[k]["recall"].append(calculate_recall_at_k(retrieved_files, expected_file, k))
            metrics[k]["mrr"].append(calculate_mrr(retrieved_files[:k], expected_file))
            metrics[k]["ndcg"].append(calculate_ndcg_at_k(retrieved_files, expected_file, k))

    # Calculate averages and print results
    print("\n" + "=" * 80)
    print("Retrieval Metrics - Comprehensive Evaluation")
    print("=" * 80)
    print(f"Queries evaluated: {len(golden_set)}")
    print()

    for k in k_values:
        avg_precision = sum(metrics[k]["precision"]) / len(metrics[k]["precision"])
        avg_recall = sum(metrics[k]["recall"]) / len(metrics[k]["recall"])
        avg_mrr = sum(metrics[k]["mrr"]) / len(metrics[k]["mrr"])
        avg_ndcg = sum(metrics[k]["ndcg"]) / len(metrics[k]["ndcg"])

        print(f"Metrics @ k={k}:")
        print(f"  Precision: {avg_precision:.3f} (relevance of retrieved results)")
        print(f"  Recall:    {avg_recall:.3f} (coverage of relevant results)")
        print(f"  MRR:       {avg_mrr:.3f} (ranking quality)")
        print(f"  NDCG:      {avg_ndcg:.3f} (normalized ranking quality)")
        print()

    # Assert key targets
    recall_at_5 = sum(metrics[5]["recall"]) / len(metrics[5]["recall"])
    mrr_overall = sum(metrics[10]["mrr"]) / len(metrics[10]["mrr"])

    print("=" * 80)
    print("Quality Targets:")
    print(f"  Recall@5:  {recall_at_5:.1%} (target: ≥90%)")
    print(f"  MRR@10:    {mrr_overall:.3f} (target: ≥0.70)")
    print("=" * 80)

    assert recall_at_5 >= 0.90, f"Recall@5 {recall_at_5:.1%} below 90% target"
    assert mrr_overall >= 0.70, f"MRR@10 {mrr_overall:.3f} below 0.70 target"


def test_metrics_by_difficulty(retriever, golden_set):
    """Breakdown retrieval metrics by query difficulty."""
    # Categorize by difficulty
    easy = [q for q in golden_set if "database" in q.get("tags", []) or "logging" in q.get("tags", [])]
    medium = [q for q in golden_set if "patterns" in q.get("tags", []) or "config" in q.get("tags", [])]
    hard = [q for q in golden_set if "deprecation" in q.get("tags", []) or "migration" in q.get("tags", [])]

    def evaluate_queries(queries, label):
        if not queries:
            return

        recalls = []
        mrrs = []

        for q in queries:
            results = retriever.retrieve(q["query"], k=5)
            retrieved_files = [r.chunk.file_path for r in results]

            recalls.append(calculate_recall_at_k(retrieved_files, q["expected_file"], 5))
            mrrs.append(calculate_mrr(retrieved_files, q["expected_file"]))

        avg_recall = sum(recalls) / len(recalls)
        avg_mrr = sum(mrrs) / len(mrrs)

        print(f"{label} ({len(queries)} queries):")
        print(f"  Recall@5: {avg_recall:.1%}")
        print(f"  MRR:      {avg_mrr:.3f}")
        print()

    print("\n" + "=" * 80)
    print("Retrieval Metrics by Difficulty")
    print("=" * 80)
    print()

    evaluate_queries(easy, "Easy")
    evaluate_queries(medium, "Medium")
    evaluate_queries(hard, "Hard")

    print("=" * 80)


def test_metrics_by_category(retriever, golden_set):
    """Breakdown retrieval metrics by query category."""
    # Group by primary tag
    categories = {}
    for query_spec in golden_set:
        tags = query_spec.get("tags", [])
        if not tags:
            continue

        primary_tag = tags[0]
        if primary_tag not in categories:
            categories[primary_tag] = []
        categories[primary_tag].append(query_spec)

    print("\n" + "=" * 80)
    print("Retrieval Metrics by Category")
    print("=" * 80)
    print()

    category_results = []

    for category, queries in categories.items():
        if len(queries) < 2:
            continue

        recalls = []
        mrrs = []

        for q in queries:
            results = retriever.retrieve(q["query"], k=5)
            retrieved_files = [r.chunk.file_path for r in results]

            recalls.append(calculate_recall_at_k(retrieved_files, q["expected_file"], 5))
            mrrs.append(calculate_mrr(retrieved_files, q["expected_file"]))

        avg_recall = sum(recalls) / len(recalls)
        avg_mrr = sum(mrrs) / len(mrrs)

        category_results.append((category, len(queries), avg_recall, avg_mrr))

    # Sort by recall descending
    category_results.sort(key=lambda x: x[2], reverse=True)

    print(f"{'Category':<20} {'N':>3} {'Recall@5':>10} {'MRR':>8}")
    print("-" * 50)
    for category, count, recall, mrr in category_results:
        print(f"{category:<20} {count:>3} {recall:>9.1%} {mrr:>8.3f}")

    print("=" * 80)


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])
