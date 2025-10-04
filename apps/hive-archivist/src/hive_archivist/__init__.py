"""
Hive Archivist - Intelligent Task & Memory Nexus

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
    archivist = ArchivistService(mode='librarian')
    await archivist.start()

    # Curator mode (scheduled)
    archivist = ArchivistService(mode='curator')
    await archivist.run_maintenance()
"""

from __future__ import annotations

__version__ = "1.0.0"

__all__ = ["__version__"]
