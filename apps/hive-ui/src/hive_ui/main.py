"""hive-ui - hive-ui - Hive platform service"""

from __future__ import annotations

import asyncio

from hive_logging import get_logger

from .api.main import create_app
from .config import HiveUiConfig

logger = get_logger(__name__)


async def main_async() -> None:
    """Main entry point for hive-ui."""
    # Initialize configuration (DI pattern - Golden Rule compliant)
    config = HiveUiConfig()

    logger.info("Starting hive-ui...")
    # Initialize cache client
    from hive_cache import get_cache_client

    _ = await get_cache_client()  # Cache connected
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
