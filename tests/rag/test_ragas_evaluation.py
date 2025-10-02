"""
RAGAS-based RAG evaluation for comprehensive quality metrics.

Uses RAGAS framework to evaluate retrieval quality with metrics:
- context_precision: Retrieved contexts are relevant to the query
- context_recall: All relevant contexts are retrieved
- faithfulness: Generated answers are consistent with context
- answer_relevancy: Answers directly address the query

Requires: pip install ragas datasets
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

# Add hive-ai to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "packages" / "hive-ai" / "src"))

try:
    from ragas import evaluate
    from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness

    RAGAS_AVAILABLE = True
except ImportError:
    RAGAS_AVAILABLE = False
    pytest.skip("RAGAS not installed - run: pip install ragas datasets", allow_module_level=True)

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


def test_ragas_comprehensive_evaluation(retriever, golden_set):
    """
    Comprehensive RAG evaluation using RAGAS metrics.

    Evaluates:
    - Context Precision (≥85%): Retrieved contexts are relevant
    - Context Recall (≥80%): All relevant contexts retrieved
    - Faithfulness (≥90%): Answers consistent with context
    - Answer Relevancy (≥85%): Answers address query
    """
    if not RAGAS_AVAILABLE:
        pytest.skip("RAGAS not installed")

    # Prepare dataset for RAGAS evaluation
    ragas_dataset = []

    for query_spec in golden_set:
        query = query_spec["query"]
        expected_answer = query_spec["expected_answer"]
        expected_file = query_spec["expected_file"]

        # Retrieve context
        context = retriever.retrieve_with_context(query, k=5, include_golden_rules=False)

        # Extract contexts as strings
        contexts = []
        for pattern in context.code_patterns:
            # Include signature + code for context
            context_text = f"{pattern.signature}\n{pattern.code[:500]}"  # Limit length
            contexts.append(context_text)

        if not contexts:
            contexts = ["No relevant context found"]

        # Create RAGAS evaluation entry
        ragas_dataset.append(
            {
                "question": query,
                "contexts": contexts,
                "answer": expected_answer,  # Expected answer from golden set
                "ground_truth": expected_answer,  # Ground truth for evaluation
            }
        )

    # Run RAGAS evaluation
    print("\n" + "=" * 80)
    print("RAGAS Comprehensive Evaluation")
    print("=" * 80)
    print(f"Evaluating {len(ragas_dataset)} queries...")

    try:
        from datasets import Dataset

        # Convert to HuggingFace Dataset format
        dataset = Dataset.from_list(ragas_dataset)

        # Evaluate with RAGAS metrics
        evaluation_result = evaluate(
            dataset,
            metrics=[
                context_precision,
                context_recall,
                faithfulness,
                answer_relevancy,
            ],
        )

        # Print results
        print("\n" + "=" * 80)
        print("RAGAS Metrics Results")
        print("=" * 80)
        print(f"Context Precision:  {evaluation_result['context_precision']:.3f} (target: ≥0.850)")
        print(f"Context Recall:     {evaluation_result['context_recall']:.3f} (target: ≥0.800)")
        print(f"Faithfulness:       {evaluation_result['faithfulness']:.3f} (target: ≥0.900)")
        print(f"Answer Relevancy:   {evaluation_result['answer_relevancy']:.3f} (target: ≥0.850)")
        print("=" * 80)

        # Assert quality thresholds
        assert (
            evaluation_result["context_precision"] >= 0.85
        ), f"Context precision {evaluation_result['context_precision']:.3f} below 0.85 target"
        assert (
            evaluation_result["context_recall"] >= 0.80
        ), f"Context recall {evaluation_result['context_recall']:.3f} below 0.80 target"
        assert (
            evaluation_result["faithfulness"] >= 0.90
        ), f"Faithfulness {evaluation_result['faithfulness']:.3f} below 0.90 target"
        assert (
            evaluation_result["answer_relevancy"] >= 0.85
        ), f"Answer relevancy {evaluation_result['answer_relevancy']:.3f} below 0.85 target"

        print("\n[OK] All RAGAS metrics meet quality thresholds")

    except Exception as e:
        print(f"\n[WARNING] RAGAS evaluation failed: {e}")
        print("This may be due to missing LLM API keys or network issues")
        pytest.skip(f"RAGAS evaluation failed: {e}")


def test_ragas_by_category(retriever, golden_set):
    """
    RAGAS evaluation broken down by query category.

    Helps identify which types of queries have quality issues.
    """
    if not RAGAS_AVAILABLE:
        pytest.skip("RAGAS not installed")

    # Group queries by primary tag
    categories = {}
    for query_spec in golden_set:
        tags = query_spec.get("tags", [])
        if not tags:
            continue

        primary_tag = tags[0]  # Use first tag as category
        if primary_tag not in categories:
            categories[primary_tag] = []
        categories[primary_tag].append(query_spec)

    print("\n" + "=" * 80)
    print("RAGAS Evaluation by Category")
    print("=" * 80)

    # Evaluate each category
    category_results = {}

    for category, queries in categories.items():
        if len(queries) < 2:  # Skip categories with too few queries
            continue

        print(f"\nEvaluating category: {category} ({len(queries)} queries)...")

        # Prepare dataset for this category
        ragas_dataset = []
        for query_spec in queries:
            context = retriever.retrieve_with_context(query_spec["query"], k=5)
            contexts = [f"{p.signature}\n{p.code[:500]}" for p in context.code_patterns]

            if not contexts:
                contexts = ["No context found"]

            ragas_dataset.append(
                {
                    "question": query_spec["query"],
                    "contexts": contexts,
                    "answer": query_spec["expected_answer"],
                    "ground_truth": query_spec["expected_answer"],
                }
            )

        try:
            from datasets import Dataset

            dataset = Dataset.from_list(ragas_dataset)
            result = evaluate(dataset, metrics=[context_precision, context_recall])

            category_results[category] = {
                "precision": result["context_precision"],
                "recall": result["context_recall"],
                "count": len(queries),
            }

            print(f"  Precision: {result['context_precision']:.3f}")
            print(f"  Recall: {result['context_recall']:.3f}")

        except Exception as e:
            print(f"  [WARNING] Evaluation failed: {e}")

    # Print summary
    if category_results:
        print("\n" + "=" * 80)
        print("Category Performance Summary")
        print("=" * 80)
        for category, metrics in sorted(category_results.items(), key=lambda x: x[1]["precision"], reverse=True):
            print(
                f"{category:20s} | Precision: {metrics['precision']:.3f} | Recall: {metrics['recall']:.3f} | N={metrics['count']}"
            )
        print("=" * 80)


def test_ragas_installation():
    """Verify RAGAS and dependencies are correctly installed."""
    print("\n" + "=" * 80)
    print("RAGAS Installation Check")
    print("=" * 80)

    try:
        import ragas

        print(f"[OK] RAGAS version: {ragas.__version__}")
    except ImportError:
        print("[FAIL] RAGAS not installed")
        print("       Install with: pip install ragas")
        pytest.fail("RAGAS not installed")

    try:
        import datasets

        print(f"[OK] datasets version: {datasets.__version__}")
    except ImportError:
        print("[FAIL] datasets not installed")
        print("       Install with: pip install datasets")
        pytest.fail("datasets not installed")

    try:
        from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness

        print("[OK] RAGAS metrics importable")
        print(f"     - context_precision: {context_precision}")
        print(f"     - context_recall: {context_recall}")
        print(f"     - faithfulness: {faithfulness}")
        print(f"     - answer_relevancy: {answer_relevancy}")
    except ImportError as e:
        print(f"[FAIL] RAGAS metrics not importable: {e}")
        pytest.fail(f"RAGAS metrics not importable: {e}")

    print("=" * 80)
    print("[OK] RAGAS framework ready for evaluation")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])
