# Hive Archivist

**Intelligent Task & Memory Nexus - Proactive Knowledge Curator**

Transforms the Hive orchestration system from stateless task execution into a **learning platform** with infinite, searchable memory.

## Vision

Instead of agents starting every task from scratch, they receive **task-relevant context** from a RAG-powered knowledge base, reducing token usage by **80-90%** while dramatically improving decision quality.

## Architecture

### Dual-Mode Operation

#### 1. **Librarian Mode** (Real-time)
- Listens to `task.completed` events on hive-bus
- Parses completed tasks into **Structured Knowledge Fragments**
- Indexes fragments into vector database for semantic search
- Links all fragments to original `task_id` for traceability

#### 2. **Curator Mode** (Scheduled)
- Runs nightly deep analysis on knowledge graph
- Merges duplicate/redundant fragments
- Identifies emerging patterns across tasks
- Archives cold data (>90 days, <5 retrievals)

### Knowledge Fragment Types

Each completed task generates multiple indexed vectors:

1. **Summary**: 2-3 sentence executive summary
2. **Errors**: Each error with context + resolution
3. **Decisions**: Key architectural/design choices
4. **Artifacts**: Code files, reports, diagrams created

All fragments linked by `task_id` for full traceability.

## Integration Points

### Packages Used
- `hive-bus`: Event subscription for `task.completed`
- `hive-ai`: Vector store + embedding generation
- `hive-orchestration`: Task DB access for metadata
- `hive-logging`: Structured logging for operations

### Data Flow

```
Task Completed
    ↓
hive-bus event: task.completed
    ↓
Librarian Service
    ↓
Fragment Parser → [summary, errors, decisions, artifacts]
    ↓
Embedding Generator (multi-vector approach)
    ↓
Vector Store (ChromaDB)
    ↓
Update task DB with related_document_ids
```

## Usage

### Real-time Mode (Production)

```python
from hive_archivist.services.librarian import LibrarianService

# Start real-time indexing
librarian = LibrarianService()
await librarian.start()

# Service runs continuously, listening for task completions
```

### Curator Mode (Scheduled)

```python
from hive_archivist.services.curator import CuratorService

# Run nightly maintenance
curator = CuratorService()
await curator.run_maintenance()
```

## Configuration

### Environment Variables
```bash
# Vector store configuration
VECTOR_STORE_PROVIDER=chromadb  # or 'faiss'
VECTOR_STORE_COLLECTION=hive_knowledge
VECTOR_DIMENSION=384  # for sentence-transformers/all-MiniLM-L6-v2

# Curator settings
CURATOR_SCHEDULE=0 2 * * *  # 2 AM daily
ARCHIVE_THRESHOLD_DAYS=90
ARCHIVE_MIN_RETRIEVALS=5
```

## Development

### Setup
```bash
cd apps/hive-archivist
poetry install
```

### Testing
```bash
poetry run pytest
```

### Linting
```bash
poetry run ruff check .
poetry run ruff format .
```

## Golden Rules Compliance

- ✅ Uses `hive_logging` (not print statements)
- ✅ Uses `hive_bus` for event communication
- ✅ Uses `hive_ai` packages for vector operations
- ✅ Uses `hive_orchestration` for DB access
- ✅ No hardcoded paths (uses hive_config)
- ✅ Proper error handling with hive_errors
- ✅ Type hints on all functions
- ✅ Docstrings on public functions

## Future Enhancements

### Phase 2 (Curator Mode)
- Duplicate fragment detection and merging
- Pattern recognition across tasks
- Dynamic relevance ranking
- Cold data archival

### Phase 3 (Advanced Features)
- Cross-task dependency analysis
- Automated best practice extraction
- Knowledge graph visualization
- Predictive context pre-loading

## Success Metrics

- **Token Reduction**: 80-90% for specialized tasks
- **Indexing Speed**: <500ms per task completion
- **Search Latency**: <100ms for context retrieval
- **Knowledge Growth**: Fragments indexed per day
- **Retrieval Accuracy**: Relevance score distribution

---

**Status**: Phase 1 (Librarian Mode) - In Development
**Owner**: Hive Platform Team
**Last Updated**: 2025-10-04
