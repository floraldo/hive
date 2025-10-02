# RAG System Usage Guide

Production-ready git-aware RAG indexing system for the Hive platform.

## Quick Start

### Initial Setup

1. **Install Dependencies** (requires Python 3.11+):
```bash
poetry install
# OR
pip install sentence-transformers faiss-cpu aiofiles
```

2. **Run Full Initial Indexing**:
```bash
python scripts/rag/index_hive_codebase.py
```

Expected output:
- Files processed: ~1,032 (856 Python + 176 Markdown)
- Chunks created: ~16,000
- Indexing time: <60 seconds
- Output: `data/rag_index/` directory

### Daily Usage

#### Incremental Indexing (Automatic)

The pre-push git hook automatically updates the RAG index before every `git push`.

```bash
git push  # Hook runs automatically
```

To bypass temporarily:
```bash
git push --no-verify
```

#### Incremental Indexing (Manual)

```bash
# Auto-detect changes since last indexing
python scripts/rag/incremental_index.py

# Index specific commit range
python scripts/rag/incremental_index.py --since-commit HEAD~5

# Force re-index all files
python scripts/rag/incremental_index.py --force

# Verbose output
python scripts/rag/incremental_index.py --verbose
```

## Emergency Controls

### Disable Automatic Indexing

Create a lock file to disable the pre-push hook:

```bash
touch rag_indexing.lock
```

To re-enable, remove the lock file:
```bash
rm rag_indexing.lock
```

Note: The lock file is automatically ignored by git.

### Monitoring

All indexing activity is logged to:
```
logs/rag_indexing.log
```

Log format:
```
2025-10-02 20:30:15 - rag_indexer - INFO - Starting incremental RAG indexing
2025-10-02 20:30:15 - rag_indexer - INFO - Mode: incremental
2025-10-02 20:30:15 - rag_indexer - INFO - Current HEAD: 81d36262
2025-10-02 20:30:15 - rag_indexer - INFO - Found 5 files to index
2025-10-02 20:30:16 - rag_indexer - INFO - Indexed 10 git commits
2025-10-02 20:30:16 - rag_indexer - INFO - Incremental indexing complete
2025-10-02 20:30:16 - rag_indexer - INFO - Files processed: 5
2025-10-02 20:30:16 - rag_indexer - INFO - Chunks created: 25
2025-10-02 20:30:16 - rag_indexer - INFO - Elapsed time: 1.2s
```

## Features

### Git-Aware Indexing

The system indexes not just code, but its evolution:

- **File metadata**: Author, last modified date, total commits
- **Commit history**: Recent commits for each file (last 5)
- **Commit messages**: Searchable commit messages and bodies
- **Change tracking**: Incremental updates based on git diff

### Performance

- **Full indexing**: ~16,000 chunks in <60 seconds
- **Incremental**: <10 seconds for typical commits (5-10 files)
- **Git commit indexing**: ~100 commits in 0.27 seconds

### Index Contents

The RAG index includes:

1. **Code chunks**: Python files with hierarchical chunking
2. **Documentation**: Markdown files (READMEs, claudedocs/)
3. **Git metadata**: Commit messages, authors, timestamps
4. **Architectural context**: Package structure, dependencies

## Troubleshooting

### Hook Not Running

Check if the hook is executable:
```bash
ls -l .git/hooks/pre-push
chmod +x .git/hooks/pre-push
```

### Indexing Errors

Check the log file:
```bash
tail -50 logs/rag_indexing.log
```

### Reset Index

To rebuild from scratch:
```bash
rm -rf data/rag_index/
python scripts/rag/index_hive_codebase.py
```

### Unicode/Encoding Issues

All subprocess calls use UTF-8 encoding with error replacement. If you encounter issues, check:
```bash
python -c "import sys; print(sys.getdefaultencoding())"
```

## Integration with Guardian Agent

The RAG system integrates with the Guardian agent for PR review:

```python
from guardian_agent.review.rag_comment_engine import RAGEnhancedCommentEngine

# Create engine (read-only mode)
engine = RAGEnhancedCommentEngine(rag_index_dir="data/rag_index")

# Analyze PR
comments = await engine.analyze_pr(pr_number=123)
```

See `apps/guardian-agent/src/guardian_agent/review/rag_comment_engine.py` for details.

## Testing

### Integration Tests

```bash
pytest tests/integration/test_rag_guardian.py -v
```

Expected: 6 tests pass
- Database violation detection
- Logging violation detection
- Config deprecation detection
- Performance requirements (<150ms p95)
- Graceful degradation
- GitHub comment formatting

### Quality Evaluation

```bash
pytest tests/rag/test_combined_quality.py -v
```

Baseline targets:
- Context Precision: >0.7
- Context Recall: >0.8
- Answer Relevancy: >0.75
- Combined Quality Score: >0.75

## Architecture

```
scripts/rag/
├── index_hive_codebase.py     # Full codebase indexing
├── incremental_index.py        # Incremental git-aware indexing
└── README.md                   # This file

.git/hooks/
└── pre-push                    # Auto-indexing hook

data/rag_index/
├── faiss_index/                # Vector embeddings (FAISS)
├── metadata/                   # Chunk metadata
├── index_metadata.json         # Index version tracking
└── git_commits.json            # Indexed commit messages

logs/
└── rag_indexing.log            # Indexing audit trail

packages/hive-ai/src/hive_ai/rag/
├── chunker.py                  # Hierarchical chunking
├── embeddings.py               # Embedding generation
├── retriever.py                # Enhanced RAG retrieval
├── context_formatter.py        # Instructional priming
├── query_engine.py             # Query API
└── quality_metrics.py          # Combined quality evaluation

apps/guardian-agent/src/guardian_agent/review/
└── rag_comment_engine.py       # PR review integration
```

## Next Steps

1. **Validate Full Indexing**: Run initial indexing and verify output
2. **Run Integration Tests**: Ensure all tests pass
3. **Establish Baseline**: Run RAGAS evaluation on Golden Set
4. **Deploy Guardian**: Enable RAG-enhanced PR reviews
5. **Monitor Performance**: Track indexing times and quality metrics

## Support

- **Documentation**: `claudedocs/rag_phase2_week5_day1_complete.md`
- **Issues**: Check logs first, then review integration test output
- **Emergency**: Create `rag_indexing.lock` to disable auto-indexing
