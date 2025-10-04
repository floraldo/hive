"""
BaseApplication - Unified application lifecycle framework.

Provides standardized foundation for all Hive platform apps:
- Automatic unified configuration loading
- Resource management (database, cache, event bus)
- Lifecycle automation (startup, shutdown, cleanup)
- Health monitoring and graceful degradation

Apps inherit from BaseApplication and implement only business logic.
"""

from __future__ import annotations

import asyncio
import signal
from abc import ABC, abstractmethod
from typing import Any

from hive_config import HiveConfig, load_config_for_app
from hive_logging import get_logger


class BaseApplication(ABC):
    """
    Base class for all Hive platform applications.

    Provides unified lifecycle management, resource initialization,
    and graceful shutdown handling.

    **Apps must implement**:
    - `app_name`: str (class variable)
    - `initialize_services()`: Setup app-specific services
    - `run()`: Main application logic

    **Apps optionally override**:
    - `cleanup_services()`: Custom service cleanup
    - `health_check()`: Custom health validation

    **Example** (Long-running worker):
        ```python
        from hive_app_toolkit import BaseApplication

        class MyWorkerApp(BaseApplication):
            app_name = "my-worker"

            async def initialize_services(self):
                self.worker = WorkerService(
                    config=self.config,
                    db=self.db,
                    cache=self.cache
                )

            async def run(self):
                while not self._shutdown_requested:
                    await self.worker.poll_tasks()
                    await asyncio.sleep(30)

        if __name__ == "__main__":
            app = MyWorkerApp()
            app.start()
        ```
    """

    # REQUIRED: Apps must set this class variable
    app_name: str

    def __init__(self, config: HiveConfig | None = None):
        """
        Initialize base application.

        Args:
            config: Optional pre-loaded configuration (for testing).
                   If not provided, loads via load_config_for_app(app_name).

        Raises:
            ValueError: If app_name class variable not defined
        """
        # Validate app_name is defined
        if not hasattr(self, "app_name") or not self.app_name:
            raise ValueError(f"{self.__class__.__name__} must define 'app_name' class variable")

        # Load unified configuration (Project Unify V2)
        self.config = config or load_config_for_app(self.app_name)

        # Setup logging
        self.logger = get_logger(f"{self.app_name}.app")

        # Resource containers (initialized in setup_resources)
        self.db: Any | None = None  # DatabaseManager from hive-db
        self.cache: Any | None = None  # CacheClient from hive-cache
        self.event_bus: Any | None = None  # EventBus from hive-bus

        # Lifecycle state
        self._running = False
        self._shutdown_requested = False
        self._shutdown_event = asyncio.Event()

        # Signal handlers (registered in start())
        self._original_sigterm = None
        self._original_sigint = None

        self.logger.info(f"{self.app_name} initialized")

    # ============================================================================
    # LIFECYCLE METHODS
    # ============================================================================

    def start(self) -> None:
        """
        Start the application (blocking).

        This is the main entry point. Handles:
        1. Signal handler registration (SIGTERM, SIGINT)
        2. Resource setup
        3. Service initialization
        4. Running main logic
        5. Graceful shutdown
        6. Resource cleanup

        Raises:
            Exception: If startup fails (after cleanup attempt)
        """
        try:
            # Run async startup
            asyncio.run(self._async_start())

        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")

        except Exception as e:
            self.logger.error(f"Application failed: {e}", exc_info=True)
            raise

        finally:
            self.logger.info(f"{self.app_name} stopped")

    async def _async_start(self) -> None:
        """
        Async startup sequence.

        Internal method. Use start() instead.
        """
        try:
            # Register signal handlers for graceful shutdown
            self._register_signal_handlers()

            # Setup phase
            self.logger.info("Setting up resources...")
            await self.setup_resources()

            self.logger.info("Initializing services...")
            await self.initialize_services()

            # Run phase
            self._running = True
            self.logger.info(f"{self.app_name} running")

            await self.run()

        except Exception as e:
            self.logger.error(f"Startup failed: {e}", exc_info=True)
            raise

        finally:
            # Shutdown phase (always runs)
            await self.shutdown()

            # Restore original signal handlers
            self._restore_signal_handlers()

    async def shutdown(self) -> None:
        """
        Graceful shutdown sequence.

        Guaranteed to run even if app crashes.
        Cleans up all resources in reverse order of initialization.

        Idempotent: safe to call multiple times.
        """
        if self._shutdown_requested:
            return  # Already shutting down

        self._shutdown_requested = True
        self._shutdown_event.set()

        self.logger.info("Shutting down...")

        try:
            # 1. App-specific cleanup
            await self.cleanup_services()

            # 2. Base resource cleanup
            await self.cleanup_resources()

            self.logger.info("Shutdown complete")

        except Exception as e:
            self.logger.error(f"Shutdown error: {e}", exc_info=True)

        finally:
            self._running = False

    def _register_signal_handlers(self) -> None:
        """
        Register signal handlers for graceful shutdown.

        Handles SIGTERM and SIGINT to trigger shutdown.
        """
        loop = asyncio.get_running_loop()

        # Define shutdown handler
        def handle_signal(signum: int) -> None:
            """Handle shutdown signals"""
            signame = signal.Signals(signum).name
            self.logger.info(f"Received {signame}, initiating shutdown...")
            asyncio.create_task(self.shutdown())

        # Register handlers
        try:
            loop.add_signal_handler(signal.SIGTERM, handle_signal, signal.SIGTERM)
            loop.add_signal_handler(signal.SIGINT, handle_signal, signal.SIGINT)
            self.logger.debug("Signal handlers registered")
        except NotImplementedError:
            # Signal handlers not supported on this platform (Windows)
            self.logger.warning("Signal handlers not supported on this platform")

    def _restore_signal_handlers(self) -> None:
        """Restore original signal handlers"""
        try:
            loop = asyncio.get_running_loop()
            loop.remove_signal_handler(signal.SIGTERM)
            loop.remove_signal_handler(signal.SIGINT)
            self.logger.debug("Signal handlers restored")
        except (NotImplementedError, RuntimeError):
            # Not supported or loop already closed
            pass

    # ============================================================================
    # RESOURCE MANAGEMENT
    # ============================================================================

    async def setup_resources(self) -> None:
        """
        Initialize platform resources.

        Resources are created in dependency order:
        1. Database (most fundamental)
        2. Cache (depends on config)
        3. Event Bus (depends on config)

        Raises:
            Exception: If resource setup fails (after cleanup attempt)
        """
        try:
            # Database
            if hasattr(self.config, "database") and getattr(self.config.database, "enabled", True):
                self.db = await self._create_database_manager()
                self.logger.info("Database initialized")

            # Cache
            if hasattr(self.config, "cache") and getattr(self.config.cache, "enabled", True):
                self.cache = await self._create_cache_client()
                self.logger.info("Cache initialized")

            # Event Bus
            if hasattr(self.config, "bus") and getattr(self.config.bus, "enabled", True):
                self.event_bus = await self._create_event_bus()
                self.logger.info("Event bus initialized")

        except Exception as e:
            self.logger.error(f"Resource setup failed: {e}")
            # Cleanup any partially initialized resources
            await self.cleanup_resources()
            raise

    async def cleanup_resources(self) -> None:
        """
        Clean up platform resources.

        Cleanup happens in reverse order of initialization.
        Continues even if individual cleanups fail (fail-safe design).

        Logs warnings for cleanup failures but doesn't raise exceptions.
        """
        errors = []

        # Event Bus (last created, first destroyed)
        if self.event_bus:
            try:
                if hasattr(self.event_bus, "close"):
                    await self.event_bus.close()
                self.logger.info("Event bus closed")
            except Exception as e:
                errors.append(f"Event bus cleanup: {e}")
            finally:
                self.event_bus = None

        # Cache
        if self.cache:
            try:
                if hasattr(self.cache, "close"):
                    await self.cache.close()
                self.logger.info("Cache closed")
            except Exception as e:
                errors.append(f"Cache cleanup: {e}")
            finally:
                self.cache = None

        # Database (first created, last destroyed)
        if self.db:
            try:
                if hasattr(self.db, "close"):
                    await self.db.close()
                self.logger.info("Database closed")
            except Exception as e:
                errors.append(f"Database cleanup: {e}")
            finally:
                self.db = None

        # Log any cleanup errors (but don't fail)
        if errors:
            error_msg = "; ".join(errors)
            self.logger.warning(f"Cleanup warnings: {error_msg}")

    # ============================================================================
    # RESOURCE FACTORIES
    # ============================================================================

    async def _create_database_manager(self) -> Any:
        """
        Create database manager from config.

        Returns:
            DatabaseManager instance from hive-db

        Raises:
            ImportError: If hive-db not available
            Exception: If database creation fails
        """
        try:
            from hive_db import create_database_manager

            return await create_database_manager(self.config.database)
        except ImportError as e:
            self.logger.warning(f"hive-db not available: {e}")
            raise

    async def _create_cache_client(self) -> Any:
        """
        Create cache client from config.

        Returns:
            CacheClient instance from hive-cache

        Raises:
            ImportError: If hive-cache not available
            Exception: If cache creation fails
        """
        try:
            from hive_cache import create_cache_client

            return await create_cache_client(self.config.cache)
        except ImportError as e:
            self.logger.warning(f"hive-cache not available: {e}")
            raise

    async def _create_event_bus(self) -> Any:
        """
        Create event bus from config.

        Returns:
            EventBus instance from hive-bus

        Raises:
            ImportError: If hive-bus not available
            Exception: If event bus creation fails
        """
        try:
            from hive_bus import create_event_bus

            return await create_event_bus(self.config.bus)
        except ImportError as e:
            self.logger.warning(f"hive-bus not available: {e}")
            raise

    # ============================================================================
    # HEALTH & MONITORING
    # ============================================================================

    async def health_check(self) -> dict[str, Any]:
        """
        Comprehensive health check.

        Checks status of all initialized resources.
        Apps can override to add custom health checks.

        Returns:
            Health status dict with component status:
            ```python
            {
                "status": "healthy" | "degraded" | "unhealthy",
                "app": str,
                "running": bool,
                "resources": {
                    "database": {...},
                    "cache": {...},
                    "bus": {...}
                }
            }
            ```
        """
        health: dict[str, Any] = {
            "status": "healthy",
            "app": self.app_name,
            "running": self._running,
            "resources": {},
        }

        # Check database
        if self.db:
            try:
                if hasattr(self.db, "health"):
                    health["resources"]["database"] = await self.db.health()
                else:
                    health["resources"]["database"] = {"status": "unknown"}
            except Exception as e:
                health["resources"]["database"] = {"status": "unhealthy", "error": str(e)}
                health["status"] = "degraded"

        # Check cache
        if self.cache:
            try:
                if hasattr(self.cache, "health"):
                    health["resources"]["cache"] = await self.cache.health()
                else:
                    health["resources"]["cache"] = {"status": "unknown"}
            except Exception as e:
                health["resources"]["cache"] = {"status": "unhealthy", "error": str(e)}
                health["status"] = "degraded"

        # Check event bus
        if self.event_bus:
            try:
                if hasattr(self.event_bus, "health"):
                    health["resources"]["bus"] = await self.event_bus.health()
                else:
                    health["resources"]["bus"] = {"status": "unknown"}
            except Exception as e:
                health["resources"]["bus"] = {"status": "unhealthy", "error": str(e)}
                health["status"] = "degraded"

        return health

    # ============================================================================
    # ABSTRACT METHODS (Apps Must Implement)
    # ============================================================================

    @abstractmethod
    async def initialize_services(self) -> None:
        """
        Initialize app-specific services.

        Called after setup_resources(), before run().
        Use self.config, self.db, self.cache, self.event_bus.

        Example:
            ```python
            async def initialize_services(self):
                self.planning_service = PlanningService(
                    config=self.config,
                    db=self.db,
                    cache=self.cache,
                    bus=self.event_bus
                )
            ```

        Raises:
            Exception: If service initialization fails
        """
        pass

    @abstractmethod
    async def run(self) -> None:
        """
        Main application logic.

        Called after initialize_services().
        This is where the app does its work.

        **For long-running apps**:
            ```python
            async def run(self):
                while not self._shutdown_requested:
                    await self.do_work()
                    await asyncio.sleep(poll_interval)
            ```

        **For one-shot apps**:
            ```python
            async def run(self):
                await self.process_task()
            ```

        **Use shutdown event** (recommended for clean shutdown):
            ```python
            async def run(self):
                while not self._shutdown_requested:
                    try:
                        await asyncio.wait_for(
                            self.do_work(),
                            timeout=poll_interval
                        )
                    except asyncio.TimeoutError:
                        continue  # Check shutdown flag
            ```

        Raises:
            Exception: If main logic fails
        """
        pass

    async def cleanup_services(self) -> None:
        """
        Optional: Clean up app-specific services.

        Called during shutdown, before cleanup_resources().
        Override if you have custom cleanup needs.

        Default: no-op (most apps don't need custom cleanup)

        Example:
            ```python
            async def cleanup_services(self):
                if self.planning_service:
                    await self.planning_service.stop()
            ```
        """
        # Default implementation: no-op
        # Apps override this if they need custom service cleanup
        return
