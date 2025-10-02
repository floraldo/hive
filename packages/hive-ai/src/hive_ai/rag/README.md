# Hive RAG - Retrieval-Augmented Generation for Code

**Version**: 0.1.0
**Status**: Phase 1 Implementation Complete

RAG infrastructure for semantic code search and context augmentation in Hive platform agents.

## Features

### ✅ Phase 1 (Completed)

- **🧬 AST-Aware Chunking**: Intelligent Python code parsing with signature + docstring enrichment
- **📊 Metadata-Rich Indexing**: Operational context from `scripts_metadata.json`, `USAGE_MATRIX.md`, archive notes
- **🔍 Hybrid Search**: Combines semantic (vector) + keyword (BM25) retrieval
- **⚡ High Performance**: Multi-level caching, batch processing, FAISS vector store
- **🎯 Structured Context**: LLM-ready prompt generation with code patterns + golden rules
- **🏗️ Production Ready**: Integration with `hive-cache`, `hive-logging`, proper DI patterns

### ✅ Phase 2 - Week 4 (In Progress)

- **📝 Markdown Chunking**: Header-based sectioning for architectural memory
- **🗂️ Documentation Indexing**: READMEs, migration guides, integration reports, archive notes
- **📋 Golden Set Evaluation**: 22 curated queries with ground truth for quality validation
- **🎯 TDD Approach**: Test-first development with RAGAS metrics framework

## Architecture

```
hive-ai/rag/
├── models.py               # Data models (CodeChunk, StructuredContext)
├── chunker.py              # AST-aware code chunking
├── metadata_loader.py      # Operational metadata extraction
├── embeddings.py           # Sentence-transformers with caching
├── vector_store.py         # FAISS semantic search
├── keyword_search.py       # BM25 keyword search
└── retriever.py            # Hybrid retrieval orchestrator
```

## Quick Start

### Basic Usage

```python
from hive_ai.rag import (
    HierarchicalChunker,
    EmbeddingGenerator,
    EnhancedRAGRetriever,
)

# 1. Chunk code files
chunker = HierarchicalChunker()
chunks = chunker.chunk_directory("packages/hive-ai/src/hive_ai")

# 2. Index chunks
retriever = EnhancedRAGRetriever()
retriever.index_chunks(chunks)

# 3. Retrieve context
context = retriever.retrieve_with_context(
    query="How do I implement async retry with backoff?",
    include_golden_rules=True,
)

# 4. Use in LLM prompt
prompt = f"""
{context.to_prompt_section()}

Your task: Implement async retry logic following Hive patterns.
"""
```

### Advanced Usage

```python
from hive_ai.rag import RetrievalQuery, ChunkType

# Custom retrieval query
query = RetrievalQuery(
    query="database connection pooling",
    k=10,
    exclude_archived=True,
    usage_context="CI/CD",  # Filter by usage context
    chunk_types=[ChunkType.FUNCTION, ChunkType.CLASS],
    use_hybrid=True,
    semantic_weight=0.7,
    keyword_weight=0.3,
)

results = retriever.retrieve(query)

for result in results:
    print(f"[{result.score:.2f}] {result.chunk.file_path}:{result.chunk.signature}")
    print(f"  Purpose: {result.chunk.purpose}")
    print(f"  Method: {result.retrieval_method}")
```

### Markdown Chunking (Phase 2)

```python
# Index documentation and architectural memory
chunker = HierarchicalChunker()

# Chunk individual markdown file
md_chunks = chunker.chunk_markdown("claudedocs/migration_guide.md")

# Chunk entire directory including markdown
all_chunks = chunker.chunk_all_files(
    "packages/hive-config",
    recursive=True,
    include_markdown=True,  # Include README.md and other docs
)

# Architectural memory is automatically tagged
for chunk in md_chunks:
    if chunk.purpose:
        print(f"Purpose: {chunk.purpose}")  # "Migration guide", "Component documentation", etc.
    if chunk.is_archived:
        print("This is archived documentation")
```

## Key Concepts

### CodeChunk

Enhanced code unit with rich metadata:

```python
@dataclass
class CodeChunk:
    # Core content
    code: str
    chunk_type: ChunkType  # CLASS, FUNCTION, METHOD, MODULE
    file_path: str

    # AST metadata
    signature: str
    imports: list[str]
    parent_class: str | None
    docstring: str

    # Operational metadata (from scripts_metadata.json, USAGE_MATRIX.md)
    purpose: str | None
    usage_context: str | None  # "CI/CD", "Manual", "Testing"
    execution_type: str | None

    # Architectural memory (from archive/, migration reports)
    deprecation_reason: str | None
    is_archived: bool
    replacement_pattern: str | None
```

### Hybrid Search

Combines two complementary retrieval methods:

1. **Semantic Search** (70% weight): Vector similarity using `sentence-transformers/all-MiniLM-L6-v2`
2. **Keyword Search** (30% weight): BM25 exact matching for function names, variables

**Why Hybrid?**
- Semantic finds conceptually similar code
- Keyword finds exact matches (`fix_bare_except`, specific error messages)
- Combined: Best of both worlds

### Metadata Enrichment

Chunks are enriched with operational context:

- **Purpose**: What the script/function does (from `scripts_metadata.json`)
- **Usage Context**: CI/CD, Manual, Testing, etc. (from `USAGE_MATRIX.md`)
- **Deprecation**: Why archived, what replaces it (from `archive/README.md`)

**Value**: Agents understand not just *what* code does, but *how* and *when* to use it.

## Integration Points

### With Guardian Agent

```python
from guardian_agent.intelligence import UnifiedIntelligenceCore
from hive_ai.rag import EnhancedRAGRetriever

class GuardianWithRAG:
    def __init__(self, uic: UnifiedIntelligenceCore):
        self.uic = uic
        self.rag = EnhancedRAGRetriever()

        # Index Hive codebase
        self._index_hive_codebase()

    async def review_with_context_async(self, code: str):
        # Get RAG context
        context = self.rag.retrieve_with_context(
            query=f"Review this code:\n{code[:500]}",
            include_golden_rules=True,
        )

        # Combine with UIC knowledge graph
        uic_insights = await self.uic.query_unified_intelligence_async(...)

        # Generate review with full context
        return self._generate_review(code, context, uic_insights)
```

### With hive-cache

RAG automatically uses `hive-cache` for:
- Embedding caching (1 week TTL)
- Hot cache for frequently accessed embeddings
- ~90% cache hit rate in practice

### With hive-logging

All RAG operations are logged:

```python
from hive_logging import get_logger

logger = get_logger(__name__)

# Logs include:
# - Chunking progress
# - Indexing stats
# - Retrieval performance
# - Cache hit rates
```

## Performance

### Benchmarks (Phase 1)

- **Chunking**: ~500 files/sec with AST parsing
- **Embedding**: ~100 chunks/sec (batch=32, CPU)
- **Retrieval**: <100ms p95 for hybrid search
- **Cache Hit Rate**: ~90% for repeated queries

### Optimization

**Batch Processing**:
```python
# Bad: Sequential embedding
for chunk in chunks:
    embedding_generator.embed_chunk(chunk)

# Good: Batch embedding (10-50x faster)
embedding_generator.embed_chunks_batch(chunks, batch_size=32)
```

**Caching**:
- Embeddings cached in Redis (1 week TTL)
- Hot cache for active session
- Check `retriever.get_stats()` for cache performance

## Configuration

### Embedding Model

Default: `sentence-transformers/all-MiniLM-L6-v2` (384-dim, fast, good quality)

**Alternative Models**:
```python
# Higher quality, slower
embedder = EmbeddingGenerator(
    model_name="BAAI/bge-large-en-v1.5",  # 1024-dim
)

# Faster, lower quality
embedder = EmbeddingGenerator(
    model_name="sentence-transformers/all-MiniLM-L12-v2",  # 384-dim, faster
)
```

### Hybrid Search Weights

```python
query = RetrievalQuery(
    query="...",
    semantic_weight=0.7,  # Increase for conceptual similarity
    keyword_weight=0.3,   # Increase for exact matching
)
```

**Tuning Guide**:
- Code patterns, algorithms → semantic=0.8, keyword=0.2
- Function names, error messages → semantic=0.5, keyword=0.5
- General queries → semantic=0.7, keyword=0.3 (default)

## Persistence

### Save/Load Index

```python
# Save retriever state
retriever.save("data/rag_index")

# Load in new session
retriever = EnhancedRAGRetriever()
retriever.load("data/rag_index")
```

**What's saved**:
- FAISS vector index
- Code chunks metadata
- (Embeddings regenerated from cache)

## Golden Rules Integration

RAG includes simplified golden rules integration:

```python
context = retriever.retrieve_with_context(
    query="async database operations",
    include_golden_rules=True,  # Include relevant rules
)

# Output includes:
# - Rule #10: No print() statements - Use hive_logging
# - Rule #11: Use hive packages for infrastructure
```

**Future**: Full integration with `hive-tests` AST validator for complete rule coverage.

## Troubleshooting

### No Results Returned

**Check**:
1. Are chunks indexed? `retriever.get_stats()`
2. Are filters too restrictive? Try `exclude_archived=False`
3. Is query too specific? Try broader terms

### Slow Retrieval

**Solutions**:
1. Reduce `k`: Fewer results = faster
2. Check cache hit rate: `embedding_generator.get_stats()`
3. Use semantic-only search: `use_hybrid=False`

### Poor Quality Results

**Solutions**:
1. Adjust hybrid weights (more semantic for concepts, more keyword for exact matches)
2. Check chunk quality: Are docstrings and signatures complete?
3. Expand indexed codebase: More context = better results

## Roadmap

### Phase 2 (Weeks 3-6)

- [ ] Extract to standalone `hive-rag` package
- [ ] Cross-encoder re-ranking for top-k results
- [ ] Full codebase indexing (all apps + packages)
- [ ] Context7 MCP integration (external docs)
- [ ] Incremental indexing (Git hook)
- [ ] Golden set evaluation framework

### Phase 3 (Future)

- [ ] Multi-modal RAG (diagrams, configs, YAML)
- [ ] Git history RAG (decision archaeology)
- [ ] Feedback loops (RAG quality improvement)
- [ ] Query expansion & reformulation

## Contributing

RAG follows Hive's golden rules:

- Use `hive_logging.get_logger()`, not `print()`
- Type hints on all public functions
- Docstrings for all classes/methods
- Integration tests for core functionality

## License

MIT - See LICENSE file for details

---

**For questions or issues**: See main Hive README or file issues in the Hive repository.
