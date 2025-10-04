# BaseApplication API Specification

**Project**: Project Launchpad
**Status**: Design Phase
**Version**: 1.0.0
**Date**: 2025-10-04

## Executive Summary

`BaseApplication` is the unified application lifecycle framework for all Hive platform apps. It eliminates 2,000+ lines of boilerplate code by providing a standardized foundation for configuration, resource management, startup, shutdown, and health monitoring.

## Design Principles

1. **Inherit→Extend Pattern**: Apps inherit from `BaseApplication` and implement only business logic
2. **Dependency Injection**: All resources (config, db, cache, bus) provided via constructor/properties
3. **Lifecycle Automation**: Startup, shutdown, and resource cleanup handled automatically
4. **Fail-Safe Design**: Graceful degradation and guaranteed resource cleanup
5. **Minimal API Surface**: Only 3 abstract methods apps must implement

## Core Architecture

### BaseApplication Class

```python
from abc import ABC, abstractmethod
from typing import Any
import asyncio

from hive_config import HiveConfig, load_config_for_app
from hive_logging import get_logger
from hive_db import DatabaseManager
from hive_cache import CacheClient
from hive_bus import EventBus


class BaseApplication(ABC):
    """
    Base class for all Hive platform applications.

    Provides unified lifecycle management, resource initialization,
    and graceful shutdown handling.

    Apps must implement:
    - app_name: str (class variable)
    - initialize_services(): Setup app-specific services
    - run(): Main application logic

    Apps optionally override:
    - cleanup_services(): Custom service cleanup
    - health_check(): Custom health validation
    """

    # REQUIRED: Apps must set this class variable
    app_name: str

    def __init__(self, config: HiveConfig | None = None):
        """
        Initialize base application.

        Args:
            config: Optional pre-loaded configuration (for testing)
        """
        if not hasattr(self, 'app_name') or not self.app_name:
            raise ValueError(
                f"{self.__class__.__name__} must define 'app_name' class variable"
            )

        # Load unified configuration
        self.config = config or load_config_for_app(self.app_name)

        # Setup logging
        self.logger = get_logger(f"{self.app_name}.app")

        # Resource containers (initialized in setup_resources)
        self.db: DatabaseManager | None = None
        self.cache: CacheClient | None = None
        self.event_bus: EventBus | None = None

        # Lifecycle state
        self._running = False
        self._shutdown_requested = False

        self.logger.info(f"{self.app_name} initialized")

    # === LIFECYCLE METHODS ===

    def start(self):
        """
        Start the application (blocking).

        This is the main entry point. Handles:
        1. Resource setup
        2. Service initialization
        3. Running main logic
        4. Graceful shutdown
        """
        try:
            asyncio.run(self._async_start())
        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
        except Exception as e:
            self.logger.error(f"Application failed: {e}", exc_info=True)
            raise
        finally:
            self.logger.info(f"{self.app_name} stopped")

    async def _async_start(self):
        """Async startup sequence"""
        try:
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
            # Shutdown phase
            await self.shutdown()

    async def shutdown(self):
        """
        Graceful shutdown sequence.

        Guaranteed to run even if app crashes.
        Cleans up all resources in reverse order.
        """
        if self._shutdown_requested:
            return  # Already shutting down

        self._shutdown_requested = True
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

    # === RESOURCE MANAGEMENT ===

    async def setup_resources(self):
        """
        Initialize platform resources.

        Resources are created in dependency order:
        1. Database (most fundamental)
        2. Cache (depends on config)
        3. Event Bus (depends on config)
        """
        try:
            # Database
            if self.config.database.enabled:
                self.db = await self._create_database_manager()
                self.logger.info("Database initialized")

            # Cache
            if self.config.cache.enabled:
                self.cache = await self._create_cache_client()
                self.logger.info("Cache initialized")

            # Event Bus
            if self.config.bus.enabled:
                self.event_bus = await self._create_event_bus()
                self.logger.info("Event bus initialized")

        except Exception as e:
            self.logger.error(f"Resource setup failed: {e}")
            await self.cleanup_resources()
            raise

    async def cleanup_resources(self):
        """
        Clean up platform resources.

        Cleanup happens in reverse order of initialization.
        Continues even if individual cleanups fail.
        """
        errors = []

        # Event Bus (last created, first destroyed)
        if self.event_bus:
            try:
                await self.event_bus.close()
                self.logger.info("Event bus closed")
            except Exception as e:
                errors.append(f"Event bus cleanup: {e}")

        # Cache
        if self.cache:
            try:
                await self.cache.close()
                self.logger.info("Cache closed")
            except Exception as e:
                errors.append(f"Cache cleanup: {e}")

        # Database (first created, last destroyed)
        if self.db:
            try:
                await self.db.close()
                self.logger.info("Database closed")
            except Exception as e:
                errors.append(f"Database cleanup: {e}")

        if errors:
            error_msg = "; ".join(errors)
            self.logger.warning(f"Cleanup warnings: {error_msg}")

    # === RESOURCE FACTORIES ===

    async def _create_database_manager(self) -> DatabaseManager:
        """Create database manager from config"""
        from hive_db import create_database_manager
        return await create_database_manager(self.config.database)

    async def _create_cache_client(self) -> CacheClient:
        """Create cache client from config"""
        from hive_cache import create_cache_client
        return await create_cache_client(self.config.cache)

    async def _create_event_bus(self) -> EventBus:
        """Create event bus from config"""
        from hive_bus import create_event_bus
        return await create_event_bus(self.config.bus)

    # === HEALTH & MONITORING ===

    async def health_check(self) -> dict[str, Any]:
        """
        Comprehensive health check.

        Returns:
            Health status dict with component status
        """
        health = {
            "status": "healthy",
            "app": self.app_name,
            "running": self._running,
            "resources": {}
        }

        # Check each resource
        if self.db:
            try:
                health["resources"]["database"] = await self.db.health()
            except Exception as e:
                health["resources"]["database"] = {"status": "unhealthy", "error": str(e)}
                health["status"] = "degraded"

        if self.cache:
            try:
                health["resources"]["cache"] = await self.cache.health()
            except Exception as e:
                health["resources"]["cache"] = {"status": "unhealthy", "error": str(e)}
                health["status"] = "degraded"

        if self.event_bus:
            try:
                health["resources"]["bus"] = await self.event_bus.health()
            except Exception as e:
                health["resources"]["bus"] = {"status": "unhealthy", "error": str(e)}
                health["status"] = "degraded"

        return health

    # === ABSTRACT METHODS (Apps Must Implement) ===

    @abstractmethod
    async def initialize_services(self):
        """
        Initialize app-specific services.

        Called after setup_resources(), before run().
        Use self.config, self.db, self.cache, self.event_bus.

        Example:
            self.planning_service = PlanningService(
                config=self.config,
                db=self.db,
                cache=self.cache,
                bus=self.event_bus
            )
        """
        pass

    @abstractmethod
    async def run(self):
        """
        Main application logic.

        Called after initialize_services().
        This is where the app does its work.

        For long-running apps:
            while not self._shutdown_requested:
                await self.do_work()
                await asyncio.sleep(poll_interval)

        For one-shot apps:
            await self.process_task()
        """
        pass

    async def cleanup_services(self):
        """
        Optional: Clean up app-specific services.

        Called during shutdown, before cleanup_resources().
        Override if you have custom cleanup needs.

        Default: no-op (most apps don't need custom cleanup)
        """
        pass
```

## Usage Patterns

### Pattern 1: Long-Running Worker (AI-Planner)

```python
from hive_app_toolkit import BaseApplication
from ai_planner.services import PlanningService


class AIPlannerApp(BaseApplication):
    """AI Planning application"""

    app_name = "ai-planner"

    async def initialize_services(self):
        """Initialize planning service"""
        self.planning_service = PlanningService(
            config=self.config,
            db=self.db,
            cache=self.cache,
            bus=self.event_bus
        )

    async def run(self):
        """Poll for planning tasks"""
        while not self._shutdown_requested:
            await self.planning_service.poll_tasks()
            await asyncio.sleep(self.config.worker.poll_interval)


if __name__ == "__main__":
    app = AIPlannerApp()
    app.start()
```

**Result**: 20 lines instead of 250 lines

### Pattern 2: FastAPI Service (EcoSystemiser)

```python
from hive_app_toolkit import BaseApplication
import uvicorn
from fastapi import FastAPI


class EcoSystemiserApp(BaseApplication):
    """Energy system optimization platform"""

    app_name = "ecosystemiser"

    async def initialize_services(self):
        """Initialize FastAPI app and routers"""
        self.fastapi_app = FastAPI(
            title="EcoSystemiser",
            version=self.config.api.version
        )

        # Import and mount routers
        from ecosystemiser.api import climate_router, solver_router
        self.fastapi_app.include_router(climate_router)
        self.fastapi_app.include_router(solver_router)

    async def run(self):
        """Run FastAPI server"""
        config = uvicorn.Config(
            self.fastapi_app,
            host=self.config.api.host,
            port=self.config.api.port
        )
        server = uvicorn.Server(config)
        await server.serve()


if __name__ == "__main__":
    app = EcoSystemiserApp()
    app.start()
```

**Result**: 30 lines instead of 442 lines

### Pattern 3: CLI Application (Hive-Orchestrator)

```python
from hive_app_toolkit import BaseApplication
from hive_orchestrator.cli import create_cli


class OrchestratorApp(BaseApplication):
    """Hive orchestration service"""

    app_name = "hive-orchestrator"

    async def initialize_services(self):
        """Initialize orchestration engine"""
        from hive_orchestrator.engine import OrchestrationEngine

        self.engine = OrchestrationEngine(
            db=self.db,
            cache=self.cache,
            bus=self.event_bus,
            config=self.config
        )

    async def run(self):
        """Run CLI or daemon mode"""
        if self.config.orchestration.daemon_mode:
            # Daemon: continuous orchestration
            await self.engine.run_forever()
        else:
            # CLI: handle single command
            cli = create_cli(self.engine)
            cli()


if __name__ == "__main__":
    app = OrchestratorApp()
    app.start()
```

**Result**: 35 lines instead of 200+ lines

## Benefits

### Code Reduction
- **Before**: 10 apps × 250 lines avg = 2,500 lines boilerplate
- **After**: 1 BaseApplication (500 lines) + 10 apps × 50 lines = 1,000 lines total
- **Net Reduction**: 1,500 lines eliminated (60% reduction)

### Consistency
- **Unified Config**: Every app uses `load_config_for_app()` automatically
- **Standard Resources**: Database, cache, event bus initialized identically
- **Predictable Lifecycle**: Same startup/shutdown sequence everywhere

### Safety
- **Guaranteed Cleanup**: Resources freed even if app crashes
- **Fail-Safe Shutdown**: Continues cleanup even if individual steps fail
- **Error Isolation**: Resource failures don't prevent cleanup of other resources

### Developer Experience
- **Clear Contract**: Only 3 methods to implement (2 required, 1 optional)
- **No Boilerplate**: Focus on business logic, not infrastructure
- **Testing Support**: DI makes testing trivial (inject mock config/resources)

## Migration Path

### Phase 1: Create BaseApplication (This Document)
- Implement `BaseApplication` class in `hive-app-toolkit`
- Create resource factory functions
- Add lifecycle management
- Write comprehensive tests

### Phase 2: Proof of Concept (ai-planner)
- Migrate ai-planner to BaseApplication
- Validate pattern works for worker apps
- Iterate based on learnings
- Document migration process

### Phase 3: Systematic Migration (9 remaining apps)
- Migrate apps one by one
- ecosystemiser (FastAPI pattern)
- hive-orchestrator (CLI pattern)
- ai-reviewer (worker pattern)
- ai-deployer (worker pattern)
- guardian-agent (worker pattern)
- notification-service (API + worker)
- hive-archivist (worker pattern)
- event-dashboard (FastAPI pattern)
- qr-service (API pattern)

### Phase 4: Deprecation
- Mark old startup patterns as deprecated
- Update all documentation
- Add Golden Rule to enforce BaseApplication usage

## Testing Strategy

### Unit Tests
- Test BaseApplication lifecycle methods independently
- Test resource initialization with mocks
- Test shutdown in various failure scenarios
- Test health check aggregation

### Integration Tests
- Test full startup/shutdown cycle
- Test with real resources (database, cache, bus)
- Test graceful degradation (missing resources)
- Test shutdown under load

### End-to-End Tests
- Test complete app lifecycle
- Test signal handling (SIGTERM, SIGINT)
- Test resource cleanup verification
- Test health endpoint functionality

## Dependencies

**Required**:
- ✅ Project Unify V2 complete (unified configuration)
- ✅ Golden Rule 37 active (prevents regression)
- ✅ hive-config: `load_config_for_app()`
- ✅ hive-logging: `get_logger()`
- ⏳ hive-db: `create_database_manager()`
- ⏳ hive-cache: `create_cache_client()`
- ⏳ hive-bus: `create_event_bus()`

**Optional** (for specific apps):
- FastAPI (for API services)
- uvicorn (for FastAPI services)
- Click (for CLI apps)

## Success Criteria

- [ ] BaseApplication class implemented and tested
- [ ] All 10 apps inherit from BaseApplication
- [ ] Each app's main.py < 100 lines
- [ ] Consistent startup/shutdown across platform
- [ ] Zero resource leaks in tests
- [ ] Standardized health checks
- [ ] Net code reduction > 1,500 lines

## Next Steps

1. **Implement BaseApplication** in `packages/hive-app-toolkit/src/hive_app_toolkit/base_application.py`
2. **Create resource factories** for database, cache, event bus
3. **Write comprehensive tests** for lifecycle management
4. **Migrate ai-planner** as proof-of-concept
5. **Iterate and refine** based on real-world usage
6. **Document patterns** and migration guide
7. **Systematic migration** of remaining 9 apps
8. **Celebrate** massive code reduction and consistency gains

## Conclusion

`BaseApplication` represents the ultimate essentialization of the Hive platform's application lifecycle. Combined with Project Unify V2's unified configuration, it achieves the vision: **every app configured the same way, every app started the same way, every app shutdown the same way**.

**Essence over accumulation. Always.**
