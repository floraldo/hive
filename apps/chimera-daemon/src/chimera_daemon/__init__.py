"""Chimera Daemon - Autonomous Execution Service.

Layer 2 of Project Colossus: Transforms orchestration framework into autonomous system.

Components:
- ChimeraDaemon: Background service for autonomous workflow execution
- TaskQueue: SQLite-backed task queue with CRUD operations
- ChimeraAPI: REST API for task submission and status retrieval
- ExecutorPool: Parallel execution pool for concurrent workflows

Usage:
    from chimera_daemon import ChimeraDaemon

    daemon = ChimeraDaemon()
    await daemon.start()  # Runs autonomously
"""

__version__ = "0.1.0"

__all__ = [
    "__version__",
]
