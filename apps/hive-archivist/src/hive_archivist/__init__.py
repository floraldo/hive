"""Hive Archivist - Intelligent Task & Memory Nexus

Proactive knowledge curator that transforms completed tasks into searchable
knowledge fragments, enabling 80-90% token reduction through RAG-powered context injection.

Architecture:
- Librarian: Real-time event-driven indexing of completed tasks
- Curator: Scheduled deep analysis and knowledge graph maintenance
- Fragment Parser: Extracts structured knowledge (summaries, errors, decisions)
- Vector Indexer: Stores fragments in RAG for semantic search

Usage:
    from hive_archivist import ArchivistService

    # Real-time mode (event-driven)
    archivist = ArchivistService(mode='librarian', bus=event_bus)
    await archivist.start_async()

    # Curator mode (scheduled)
    archivist = ArchivistService(mode='curator')
    results = await archivist.run_maintenance_async()

    # Dual mode (both)
    archivist = ArchivistService(mode='both', bus=event_bus)
    await archivist.start_async()  # Starts librarian
    results = await archivist.run_maintenance_async()  # Run curator on demand
"""

from __future__ import annotations

from .archivist_service import ArchivistService
from .indexing.fragment_parser import FragmentParser, KnowledgeFragment
from .indexing.vector_indexer import VectorIndexer
from .services.curator import CuratorService
from .services.librarian import LibrarianService

__version__ = "1.0.0"

__all__ = [
    "ArchivistService",
    "CuratorService",
    "FragmentParser",
    "KnowledgeFragment",
    "LibrarianService",
    "VectorIndexer",
    "__version__",
]
