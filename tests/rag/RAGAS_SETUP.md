# RAGAS Evaluation Framework Setup

**Purpose**: Comprehensive RAG quality evaluation with RAGAS metrics

## Installation

### Option 1: pip (Recommended)

```bash
# Install RAGAS and dependencies
pip install ragas datasets

# Verify installation
python -c "import ragas; print(f'RAGAS {ragas.__version__} installed')"
```

### Option 2: poetry (Hive Workspace)

```bash
# Add to package dependencies
cd packages/hive-ai
poetry add --group dev ragas datasets

# Install
poetry install
```

## Dependencies

RAGAS requires:
- `ragas` - Main evaluation framework
- `datasets` - HuggingFace datasets library for data handling
- OpenAI API key (for LLM-based metrics) - Optional, can use local models

## Environment Setup (Optional)

For LLM-based metrics (faithfulness, answer_relevancy), set API key:

```bash
# OpenAI (recommended)
export OPENAI_API_KEY="your-api-key-here"

# Or use local models (no API key needed)
# RAGAS supports HuggingFace models via transformers
```

## Metrics Overview

### 1. Context Precision (≥85%)
**What it measures**: Are the retrieved contexts relevant to the query?

**Example**:
- Query: "How to implement async retry?"
- Good: Retrieved `hive_async.retry()` documentation
- Bad: Retrieved unrelated logging code

**Formula**: Precision = Relevant Contexts / Total Retrieved Contexts

### 2. Context Recall (≥80%)
**What it measures**: Did we retrieve all relevant contexts?

**Example**:
- Query: "Database connection pooling"
- Good: Retrieved ConnectionPool class AND usage examples
- Bad: Retrieved only ConnectionPool class (missed examples)

**Formula**: Recall = Retrieved Relevant Contexts / All Relevant Contexts

### 3. Faithfulness (≥90%)
**What it measures**: Is the generated answer consistent with retrieved context?

**Example**:
- Context: "Use create_config_from_sources() with DI pattern"
- Good answer: "Pass config to constructor with create_config_from_sources()"
- Bad answer: "Use get_config() singleton" (contradicts context)

**Requirement**: LLM evaluation (OpenAI API or local model)

### 4. Answer Relevancy (≥85%)
**What it measures**: Does the answer directly address the query?

**Example**:
- Query: "How to add CI/CD check?"
- Good answer: "Add job to .github/workflows/ci.yml"
- Bad answer: "CI/CD is important for quality" (doesn't answer how)

**Requirement**: LLM evaluation (OpenAI API or local model)

## Running RAGAS Tests

### Full RAGAS Evaluation

```bash
# With OpenAI API key
export OPENAI_API_KEY="your-key"
pytest tests/rag/test_ragas_evaluation.py -v -s

# Expected output:
# Context Precision:  0.876 (target: ≥0.850) ✓
# Context Recall:     0.823 (target: ≥0.800) ✓
# Faithfulness:       0.912 (target: ≥0.900) ✓
# Answer Relevancy:   0.867 (target: ≥0.850) ✓
```

### Simplified Retrieval Metrics (No API key needed)

```bash
# Run without external dependencies
pytest tests/rag/test_retrieval_metrics.py -v -s

# Provides:
# - Precision@k, Recall@k
# - MRR (Mean Reciprocal Rank)
# - NDCG@k (Normalized Discounted Cumulative Gain)
```

## Test Files

### `test_ragas_evaluation.py`
Full RAGAS framework evaluation with all 4 metrics.

**Requires**:
- RAGAS installed
- datasets installed
- OpenAI API key (for faithfulness, answer_relevancy)

**Features**:
- Comprehensive evaluation across 22 queries
- Category-level breakdown
- Quality threshold assertions

### `test_retrieval_metrics.py`
Simplified retrieval metrics without external dependencies.

**Requires**:
- Only pytest and yaml (standard)
- No API keys needed

**Features**:
- Precision@k, Recall@k, MRR, NDCG@k
- Difficulty-level breakdown
- Category-level breakdown

### `test_golden_set.py`
Original golden set tests with accuracy and performance validation.

**Requires**:
- Only pytest and yaml (standard)

**Features**:
- Top-k accuracy with expected file matching
- Score threshold validation
- Performance testing (latency P95)
- Context quality validation

## Troubleshooting

### "RAGAS not installed"

```bash
pip install ragas datasets
```

### "OpenAI API key not found"

```bash
# Set environment variable
export OPENAI_API_KEY="your-key"

# Or use local models (advanced)
# Edit test_ragas_evaluation.py to use HuggingFace models
```

### "RAGAS metrics import error"

```bash
# Check RAGAS version (requires ≥0.1.0)
pip show ragas

# Upgrade if needed
pip install --upgrade ragas
```

### "Dataset format error"

```bash
# Ensure datasets library is installed
pip install datasets

# Check version compatibility
pip show datasets
```

## Integration with CI/CD

### Quick Validation (Fast)

```yaml
# .github/workflows/rag-validation.yml
- name: Run retrieval metrics
  run: pytest tests/rag/test_retrieval_metrics.py -v
```

### Full RAGAS Evaluation (Comprehensive)

```yaml
# Requires secrets.OPENAI_API_KEY in GitHub repo settings
- name: Run RAGAS evaluation
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
  run: pytest tests/rag/test_ragas_evaluation.py -v
```

## Quality Thresholds

| Metric | Target | Meaning |
|--------|--------|---------|
| Context Precision | ≥85% | High relevance of retrieved contexts |
| Context Recall | ≥80% | Good coverage of relevant information |
| Faithfulness | ≥90% | Answers consistent with context |
| Answer Relevancy | ≥85% | Answers address queries directly |
| Recall@5 | ≥90% | Expected file in top-5 results |
| MRR@10 | ≥0.70 | Relevant results ranked highly |

## Next Steps

1. **Install RAGAS**: `pip install ragas datasets`
2. **Run installation test**: `pytest tests/rag/test_ragas_evaluation.py::test_ragas_installation -v`
3. **Index codebase**: `python packages/hive-ai/scripts/index_full_codebase.py`
4. **Run baseline evaluation**: `pytest tests/rag/ -v -s`
5. **Document results**: Create `claudedocs/rag_phase2_baseline_results.md`

## References

- RAGAS Documentation: https://docs.ragas.io/
- RAGAS GitHub: https://github.com/explodinggradients/ragas
- HuggingFace Datasets: https://huggingface.co/docs/datasets/
- RAG Evaluation Guide: https://docs.ragas.io/en/latest/concepts/metrics/

---

**Status**: Setup instructions ready
**Next**: Install RAGAS → Index codebase → Run baseline evaluation
