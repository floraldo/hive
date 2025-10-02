#!/bin/bash
# Full codebase RAG indexing with all hive packages in path

# Add all hive package source directories to PYTHONPATH
export PYTHONPATH="\
packages/hive-ai/src:\
packages/hive-async/src:\
packages/hive-bus/src:\
packages/hive-cache/src:\
packages/hive-config/src:\
packages/hive-db/src:\
packages/hive-errors/src:\
packages/hive-logging/src:\
packages/hive-performance/src:\
packages/hive-tests/src:\
packages/hive-orchestration/src:\
${PYTHONPATH}"

# Run the original indexing script (simpler version without complex imports)
python -c "
import sys
from pathlib import Path

# The PYTHONPATH is already set, so imports will work
from hive_ai.rag.chunker import HierarchicalChunker
from hive_ai.rag.embeddings import EmbeddingGenerator
from hive_ai.rag.retriever import EnhancedRAGRetriever

print('RAG modules imported successfully')
print('Ready to run indexing...')

# Import and run the indexer
import importlib.util
spec = importlib.util.spec_from_file_location('indexer_module', 'scripts/rag/index_hive_codebase_fixed.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.main()
"
