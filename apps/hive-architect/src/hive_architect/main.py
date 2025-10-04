"""hive-architect - hive-architect - Hive platform service"""

from __future__ import annotations

import asyncio

from hive_logging import get_logger

from .api.main import create_app
from .config import HiveArchitectConfig

logger = get_logger(__name__)


async def main_async() -> None:
    """Main entry point for hive-architect."""
    # Initialize configuration (DI pattern - Golden Rule compliant)
    config = HiveArchitectConfig()

    logger.info("Starting hive-architect...")
    # Initialize database connection
    from hive_db import get_sqlite_connection

    _db = await get_sqlite_connection(config.database_path)
    logger.info(f"Connected to database: {config.database_path}")
    # Initialize cache client
    from hive_cache import get_cache_client

    _cache = await get_cache_client()
    logger.info("Connected to cache")
    # Create FastAPI application
    app = create_app(config)

    # Start uvicorn server
    import uvicorn

    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        log_level=config.log_level.lower(),
    )


if __name__ == "__main__":
    asyncio.run(main_async())
