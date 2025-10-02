# RAG Baseline Metrics Template

**Purpose**: Document RAG performance baseline for continuous improvement tracking
**Status**: TEMPLATE (Run `poetry run pytest tests/rag/test_golden_set.py -v` to generate actual metrics)
**Date Created**: 2025-10-03

---

## How to Generate Actual Metrics

**Prerequisites**:
1. Python 3.11 environment active (`poetry shell`)
2. RAG index exists (`data/rag_index/`)
3. All hive packages installed

**Run Golden Set Evaluation**:
```bash
# Activate correct environment
cd /c/git/hive
poetry shell

# Run golden set tests
poetry run pytest tests/rag/test_golden_set.py -v -s

# Run core functionality tests
poetry run pytest tests/rag/test_core_functionality.py -v -s
```

**Expected Output**:
- Retrieval accuracy metrics
- Performance measurements
- Quality scores by category

---

## Baseline Metrics Template

### Retrieval Accuracy

**Overall Metrics**:
- Total Queries: `[TO BE MEASURED]`
- Found in Top-5: `[TO BE MEASURED]` (`[%]`)
- Meets Threshold: `[TO BE MEASURED]` (`[%]`)
- Average Relevance Score: `[TO BE MEASURED]`

**By Category**:
| Category | Queries | Accuracy | Avg Relevance |
|----------|---------|----------|---------------|
| CI/CD | 2 | `[TBM]` | `[TBM]` |
| Database | 1 | `[TBM]` | `[TBM]` |
| Async Patterns | 1 | `[TBM]` | `[TBM]` |
| Configuration | 1 | `[TBM]` | `[TBM]` |
| Logging | 1 | `[TBM]` | `[TBM]` |

**Target Thresholds** (from golden_set.yaml):
- Context Precision: ≥92%
- Context Recall: ≥88%
- Faithfulness: ≥95%
- Answer Relevancy: ≥90%

### Performance Metrics

**Query Latency**:
- Average: `[TO BE MEASURED]` ms
- P50 (median): `[TO BE MEASURED]` ms
- P95: `[TO BE MEASURED]` ms (target: <200ms)
- P99: `[TO BE MEASURED]` ms

**Throughput**:
- Single worker: `[TO BE MEASURED]` queries/min
- 4 workers: `[TO BE MEASURED]` queries/min (estimated)

**Storage**:
- Total index size: 26.6 MB (known)
- Per-chunk avg: 2.5 KB (known)
- Load time: `[TO BE MEASURED]` seconds

### Quality Metrics by Difficulty

**Easy Queries** (database, logging):
- Count: `[TO BE MEASURED]`
- Accuracy: `[TO BE MEASURED]` (target: >95%)
- Avg Relevance: `[TO BE MEASURED]`

**Medium Queries** (patterns, config):
- Count: `[TO BE MEASURED]`
- Accuracy: `[TO BE MEASURED]` (target: >85%)
- Avg Relevance: `[TO BE MEASURED]`

**Hard Queries** (deprecation, migration):
- Count: `[TO BE MEASURED]`
- Accuracy: `[TO BE MEASURED]` (target: >75%)
- Avg Relevance: `[TO BE MEASURED]`

### Failed Queries Analysis

**Queries Below Threshold**:
```
[TO BE POPULATED FROM TEST OUTPUT]

Example format:
- ❌ [Category] Query text
  - Expected: file_path.py
  - Found: No / different file
  - Top score: 0.XX
```

**Root Cause Analysis**:
- [ ] Chunking issues (chunks too large/small)
- [ ] Embedding quality (semantic mismatch)
- [ ] Query phrasing (unclear intent)
- [ ] Missing context in index

**Improvement Actions**:
1. `[Action based on failures]`
2. `[Action based on failures]`

---

## RAGAS Evaluation (Future)

**Metrics to Implement**:
- **Context Precision**: Retrieved chunks are relevant
- **Context Recall**: All relevant chunks retrieved
- **Faithfulness**: Generated answers match context
- **Answer Relevancy**: Answers address the question

**Setup Required**:
```bash
pip install ragas
pip install datasets
```

**Implementation**:
```python
from ragas import evaluate
from ragas.metrics import (
    context_precision,
    context_recall,
    faithfulness,
    answer_relevancy
)

# Run evaluation
result = evaluate(
    dataset=golden_set,
    metrics=[
        context_precision,
        context_recall,
        faithfulness,
        answer_relevancy
    ]
)
```

---

## Improvement Tracking

### Iteration 1: Baseline (Current)
**Date**: 2025-10-03
**Changes**: Initial RAG deployment
**Results**: `[TO BE MEASURED]`

### Iteration 2: After First Optimization
**Date**: `[TBD]`
**Changes**: `[List optimizations applied]`
**Results**: `[Improvement vs baseline]`

### Target Progression
```
Iteration 1 (Baseline): [TBM]% accuracy
Iteration 2 (1 week):   85% accuracy (+[X]%)
Iteration 3 (2 weeks):  90% accuracy (+[X]%)
Iteration 4 (1 month):  95% accuracy (+[X]%)
```

---

## Comparison with Production Goals

### Phase 2 Success Criteria
- [X] Index operational (10,661 chunks) ✅
- [X] Query system functional ✅
- [X] API ready for deployment ✅
- [ ] Retrieval accuracy >90% (pending measurement)
- [ ] Query latency <200ms p95 (pending measurement)

### Guardian Integration Goals
- [ ] Comment generation functional (blocked by Python 3.11 env)
- [ ] RAG context retrieval <150ms p95
- [ ] Pattern detection accuracy >80%

---

## Environment Notes

**Blocker**: Cannot run tests in current session due to Python 3.10 vs 3.11 mismatch

**Resolution Required**:
```bash
# User must run:
cd /c/git/hive
poetry shell  # Activates Python 3.11
poetry run pytest tests/rag/test_golden_set.py -v -s
```

**Expected Metrics After Running**:
- Replace all `[TO BE MEASURED]` with actual values
- Document any failed queries
- Create improvement action plan

---

## Quick Start for Metrics Collection

```bash
# 1. Activate poetry environment
cd /c/git/hive
poetry shell

# 2. Verify Python version
python --version  # Should be 3.11.9

# 3. Run golden set evaluation
poetry run pytest tests/rag/test_golden_set.py -v -s > rag_metrics_output.txt

# 4. Run core tests
poetry run pytest tests/rag/test_core_functionality.py -v -s >> rag_metrics_output.txt

# 5. Extract metrics and update this template
cat rag_metrics_output.txt | grep -E "(Accuracy|P95|Average)" > metrics_summary.txt

# 6. Create final baseline document
cp claudedocs/rag_baseline_metrics_template.md claudedocs/rag_baseline_metrics_2025_10_03.md
# Then manually update with actual values
```

---

## Metrics Dashboard (Future)

**Visualization Needs**:
- Accuracy trend over time
- Query latency distribution
- Category-wise performance heatmap
- Failed query analysis

**Tools**:
- Grafana dashboard (if metrics exported to Prometheus)
- Jupyter notebook for ad-hoc analysis
- Simple Python script for CLI visualization

---

## Conclusion

This template provides the structure for RAG performance baselines. Once the Python 3.11 environment is active and tests are run, this template should be:

1. **Copied** to `rag_baseline_metrics_2025_10_03.md`
2. **Populated** with actual test results
3. **Analyzed** for improvement opportunities
4. **Tracked** over time for quality progression

**Next Actions**:
1. User runs `poetry shell`
2. User executes golden set tests
3. Agent (or user) updates template with results
4. Team reviews and plans improvements

---

**Created by**: RAG Agent
**Status**: TEMPLATE - Awaiting Test Execution
**Blocked By**: Python 3.11 environment activation
**Resolution**: `poetry shell` + run tests
