# RAG Phase 2 Execution Plan - Refined

**Status**: Approved for Execution
**Duration**: Weeks 3-6 (4 weeks)
**Based on**: Expert review feedback + Phase 1 learnings

---

## 🎯 Phase 2 Objectives

1. **Guardian Integration**: Single high-impact use case (code review enhancement)
2. **Full Indexing**: 2,000 Hive files + architectural memory (`.md` reports)
3. **Golden Set Evaluation**: Automated quality validation with RAGAS framework
4. **Incremental Indexing**: `pre-push` Git hook for efficiency
5. **Package Extraction**: `hive-rag` with developer + agent APIs

---

## Week 3: Guardian Code Review Integration

### Objective
Enhance Guardian's code review with RAG-powered context retrieval.

### High-Impact Use Case: PR Code Review

**Guardian Agent Enhancement**:
```python
# apps/guardian-agent/src/guardian_agent/review/review_engine.py

class ReviewEngineWithRAG:
    def __init__(self):
        self.rag = EnhancedRAGRetriever()
        self.uic = UnifiedIntelligenceCore()
        self._index_hive_codebase()

    async def review_pr_async(self, pr_files: list[str]) -> ReviewResult:
        """Enhanced PR review with RAG context."""

        all_reviews = []

        for file_path, diff in pr_files:
            # 1. RAG: Retrieve similar patterns
            similar_patterns = self.rag.retrieve_with_context(
                query=f"Code patterns similar to {file_path}:\n{diff[:500]}",
                k=3,
                include_golden_rules=True,
            )

            # 2. RAG: Check for deprecated patterns
            deprecation_check = self.rag.retrieve(
                RetrievalQuery(
                    query=diff[:500],
                    exclude_archived=False,  # Include archived for warnings
                    k=5,
                )
            )

            # 3. Generate review with context
            review = await self._generate_review(
                file_path=file_path,
                diff=diff,
                similar_patterns=similar_patterns,
                deprecation_warnings=[
                    r.chunk.deprecation_reason
                    for r in deprecation_check
                    if r.chunk.is_archived
                ],
            )

            # 4. Log traceability
            logger.info(
                "RAG-enhanced review",
                extra={
                    "file": file_path,
                    "patterns_retrieved": len(similar_patterns.code_patterns),
                    "golden_rules_applied": len(similar_patterns.golden_rules),
                    "deprecation_warnings": len(review.deprecation_warnings),
                    "retrieval_time_ms": similar_patterns.retrieval_time_ms,
                }
            )

            all_reviews.append(review)

        return ReviewResult(reviews=all_reviews)
```

### Traceability Requirements

**Enhanced Logging**:
```python
from hive_logging import get_logger

logger = get_logger(__name__)

# Example log output
logger.info(
    "RAG retrieval for Guardian review",
    extra={
        "query_summary": query[:100],
        "results_count": len(results),
        "top_result": {
            "file": results[0].chunk.file_path,
            "signature": results[0].chunk.signature,
            "score": results[0].score,
            "method": results[0].retrieval_method,
        },
        "filters_applied": {
            "exclude_archived": True,
            "usage_context": None,
        },
        "cache_hit_rate": cache_stats.hit_rate,
    }
)
```

**Why This Matters**:
- Debugging: Understand what RAG retrieved and why
- Trust: Validate RAG suggestions against human expectations
- Improvement: Identify low-quality retrievals for tuning

### Deliverables

- [ ] Guardian `review_engine.py` enhanced with RAG
- [ ] Traceability logging implemented
- [ ] Test on 3 real PRs (ecosystemiser, hive-ai, hive-db)
- [ ] Measure: Review quality improvement (qualitative feedback)
- [ ] Document: Integration patterns for other agents

---

## Week 4: Full Indexing & Golden Set Evaluation

### Part A: Full Codebase Indexing

**Scope Expansion**:
```python
# Index all Python files
packages_chunks = chunker.chunk_directory("packages/", recursive=True)
apps_chunks = chunker.chunk_directory("apps/", recursive=True)
scripts_chunks = chunker.chunk_directory("scripts/", recursive=True)

# CRITICAL: Index architectural memory (.md files)
arch_memory_chunks = []

# Integration reports
for report in Path("scripts/archive/cleanup_project/cleanup/").glob("*.md"):
    arch_memory_chunks.extend(chunker.chunk_markdown(report))

# Migration guides
for guide in Path("claudedocs/").glob("*migration*.md"):
    arch_memory_chunks.extend(chunker.chunk_markdown(guide))

# Dry run plans
for plan in Path("scripts/archive/").glob("*dry_run*.md"):
    arch_memory_chunks.extend(chunker.chunk_markdown(plan))

# Archive READMEs
for readme in Path("scripts/archive/").glob("**/README.md"):
    arch_memory_chunks.extend(chunker.chunk_markdown(readme))
```

**New Functionality Needed**:
```python
# hive_ai/rag/chunker.py

def chunk_markdown(self, file_path: Path) -> list[CodeChunk]:
    """
    Chunk markdown files for architectural memory.

    Splits on headers (##) and treats each section as a chunk.
    """
    content = file_path.read_text(encoding="utf-8")
    sections = self._split_markdown_by_headers(content)

    chunks = []
    for section in sections:
        chunks.append(CodeChunk(
            code=section.content,
            chunk_type=ChunkType.DOCSTRING,  # Reuse for text
            file_path=str(file_path),
            signature=section.header,
            docstring=section.summary,
            purpose="architectural_memory",
            usage_context="documentation",
        ))

    return chunks
```

**Expected Stats**:
- Python files: ~2,000 → ~15,000 chunks
- Markdown files: ~50 → ~500 chunks
- **Total**: ~15,500 chunks
- Storage: ~200 MB (FAISS + metadata)
- Indexing time: ~2-3 minutes

### Part B: Golden Set Evaluation Framework

**Using RAGAS** (Recommendation from expert review):

```python
# tests/rag/test_golden_set_ragas.py

from ragas import evaluate
from ragas.metrics import (
    context_precision,
    context_recall,
    faithfulness,
    answer_relevancy,
)

def test_golden_set_with_ragas():
    """Evaluate RAG quality using RAGAS metrics."""

    # Load golden set
    golden_set = load_golden_queries()

    # Generate RAG responses
    results = []
    for query_spec in golden_set:
        context = retriever.retrieve_with_context(
            query=query_spec["query"],
            k=5,
        )

        results.append({
            "question": query_spec["query"],
            "contexts": [p.code for p in context.code_patterns],
            "answer": query_spec["expected_answer"],
            "ground_truth": query_spec["expected_file"],
        })

    # Evaluate with RAGAS
    evaluation = evaluate(
        results,
        metrics=[
            context_precision,
            context_recall,
            faithfulness,
            answer_relevancy,
        ],
    )

    print(evaluation)

    # Assert quality thresholds
    assert evaluation["context_precision"] >= 0.85
    assert evaluation["context_recall"] >= 0.80
    assert evaluation["faithfulness"] >= 0.90
```

**Golden Set Examples**:
```yaml
# tests/rag/golden_set.yaml

queries:
  - query: "How do I add a new CI/CD quality check?"
    expected_file: ".github/workflows/ci.yml"
    expected_section: "quality-checks"
    expected_answer: "Add a new job to ci.yml under jobs: section"
    tags: ["ci-cd", "workflow"]

  - query: "Show me database connection pooling patterns"
    expected_file: "packages/hive-db/src/hive_db/pool.py"
    expected_function: "ConnectionPool.__init__"
    expected_answer: "Use ConnectionPool with DI pattern"
    tags: ["database", "architecture"]

  - query: "How to implement async retry with exponential backoff?"
    expected_file: "packages/hive-async/src/hive_async/__init__.py"
    expected_function: "async_retry"
    expected_answer: "Use async_retry decorator from hive_async"
    tags: ["async", "patterns"]

  - query: "What are the rules for configuration management?"
    expected_file: "packages/hive-config/README.md"
    expected_section: "DI Pattern"
    expected_answer: "Use create_config_from_sources with DI"
    tags: ["config", "golden-rules"]

  - query: "Why was the old authentication system archived?"
    expected_file: "scripts/archive/README.md"
    expected_section: "Authentication"
    expected_answer: "Replaced by OAuth2 flow in v3.0"
    tags: ["deprecation", "security"]
```

**Target Metrics**:
- Context Precision: ≥85% (retrieved contexts are relevant)
- Context Recall: ≥80% (all relevant contexts retrieved)
- Faithfulness: ≥90% (answer consistent with context)
- Answer Relevancy: ≥85% (answer addresses query)

### Deliverables

- [ ] Markdown chunking implemented
- [ ] Full codebase indexed (15,500 chunks)
- [ ] Golden set created (20+ queries)
- [ ] RAGAS evaluation framework integrated
- [ ] Baseline metrics documented
- [ ] Quality improvement plan based on evaluation

---

## Week 5: Incremental Indexing

### Git Hook Strategy (Refined from Feedback)

**Use `pre-push` instead of `post-commit`** (Expert recommendation):
- Batch multiple commits before re-indexing
- Doesn't slow down local `git commit`
- Runs once before pushing to remote

**Implementation**:
```bash
#!/usr/bin/env python3
# .git/hooks/pre-push

"""
Incremental RAG re-indexing on push.

Runs efficiently on batched commits before pushing to remote.
"""

import sys
from pathlib import Path
from hive_ai.rag import RAGIndexer, EnhancedRAGRetriever

def get_modified_files_in_push():
    """Get files modified in commits about to be pushed."""
    import subprocess

    # Get remote and local refs
    remote_ref = sys.argv[2] if len(sys.argv) > 2 else "origin/main"
    local_ref = "HEAD"

    # Files changed between remote and local
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{remote_ref}..{local_ref}"],
        capture_output=True,
        text=True,
    )

    return [Path(f) for f in result.stdout.strip().split("\n") if f]

def main():
    print("🔍 RAG: Checking for files to re-index...")

    modified = get_modified_files_in_push()

    # Filter for Python and metadata files
    targets = [
        f for f in modified
        if f.suffix in [".py", ".md"]
        or f.name in ["scripts_metadata.json", "USAGE_MATRIX.md"]
    ]

    if not targets:
        print("✅ RAG: No indexable files modified")
        return 0

    print(f"⏳ RAG: Re-indexing {len(targets)} modified files...")

    try:
        # Load existing index
        retriever = EnhancedRAGRetriever()
        retriever.load("data/rag_index")

        # Chunk modified files
        chunker = HierarchicalChunker()
        new_chunks = []

        for file_path in targets:
            if file_path.suffix == ".py":
                new_chunks.extend(chunker.chunk_file(file_path))
            elif file_path.suffix == ".md":
                new_chunks.extend(chunker.chunk_markdown(file_path))

        # Re-index
        retriever.index_chunks(new_chunks)

        # Save updated index
        retriever.save("data/rag_index")

        print(f"✅ RAG: Re-indexed {len(new_chunks)} chunks in {len(targets)} files")
        return 0

    except Exception as e:
        print(f"⚠️ RAG: Re-indexing failed: {e}")
        print("   (Continuing with push - RAG will be stale)")
        return 0  # Don't block push on RAG failure

if __name__ == "__main__":
    sys.exit(main())
```

**Installation**:
```bash
# Install hook
cp scripts/rag/pre-push-hook.py .git/hooks/pre-push
chmod +x .git/hooks/pre-push

# Test
git push --dry-run
```

### Deliverables

- [ ] `pre-push` hook implemented
- [ ] Efficient batched re-indexing
- [ ] Failure handling (don't block push)
- [ ] Performance: <10 sec for typical push
- [ ] Documentation for developers

---

## Week 6: Extract to `hive-rag` Package

### Two-API Design (Expert Recommendation)

**API 1: Developer-Facing**
```python
# For CLI, VS Code extension, developer tools

from hive_rag import RAGQuery

# Simple query interface
result = RAGQuery.search(
    query="How do I add a CI/CD check?",
    project_root=".",
    k=5,
)

print(result.format_markdown())
```

**API 2: Agent-Facing**
```python
# For autonomous agents (Guardian, AI Planner, etc.)

from hive_rag import EnhancedRAGRetriever, RetrievalQuery

class MyAgent:
    def __init__(self):
        self.rag = EnhancedRAGRetriever()

    async def process_task_async(self, task: str):
        # Programmatic query
        context = self.rag.retrieve_with_context(
            query=RetrievalQuery(
                query=task,
                k=10,
                use_hybrid=True,
                filters={"usage_context": "CI/CD"},
            ),
            include_golden_rules=True,
        )

        # Use context in agent reasoning
        return self._reason_with_context(task, context)
```

### Package Structure

```
packages/hive-rag/
├── src/hive_rag/
│   ├── __init__.py              # Public API
│   ├── core/                    # Core functionality
│   │   ├── chunking/
│   │   │   ├── code_chunker.py
│   │   │   └── markdown_chunker.py
│   │   ├── embeddings/
│   │   │   └── embedding_generator.py
│   │   └── retrieval/
│   │       ├── vector_store.py
│   │       ├── keyword_search.py
│   │       └── hybrid_retriever.py
│   ├── integration/             # Agent integrations
│   │   ├── guardian.py
│   │   ├── ai_planner.py
│   │   └── base.py
│   └── cli/                     # Developer tools
│       └── query.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── golden_set/
│       ├── queries.yaml
│       └── test_ragas.py
└── README.md
```

### Migration Plan

1. Copy `hive-ai/rag/` → `hive-rag/core/`
2. Create integration layer for agents
3. Add CLI for developers
4. Update imports in Guardian, AI Planner
5. Validate with full test suite
6. Update documentation

### Deliverables

- [ ] `hive-rag` package created
- [ ] Two-API design implemented
- [ ] CLI tool for developers
- [ ] Integration layer for agents
- [ ] Migration guide for other agents
- [ ] Full test coverage maintained

---

## Success Metrics - Phase 2

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Guardian Review Quality** | +30% improvement | User feedback, PR acceptance rate |
| **Golden Set Accuracy** | >90% @ k=5 | RAGAS context_precision |
| **Retrieval Latency** | <150ms p95 | Performance monitoring |
| **Cache Hit Rate** | >85% | hive-cache metrics |
| **Index Freshness** | <1 day lag | Git hook execution rate |

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Guardian integration breaks existing reviews | Gradual rollout, A/B testing |
| Full indexing takes too long | Parallel chunking, optimize batch size |
| Golden set evaluation shows poor quality | Iterative tuning, query reformulation |
| Git hook slows down push | `pre-push` instead of `post-commit`, async indexing |
| Package extraction breaks dependencies | Thorough testing, gradual migration |

---

## Next Review

**Date**: End of Week 6
**Deliverables**: All Phase 2 objectives complete
**Success Criteria**: Guardian using RAG in production, >90% golden set accuracy

---

**Prepared by**: Claude Code (RAG Team)
**Approved by**: Expert Reviewer
**Start Date**: Week 3
**Status**: Ready to Execute
