# BaseApplication Migration Guide

**Project**: Project Launchpad Phase 2
**Audience**: Developers migrating Hive apps to BaseApplication
**Version**: 1.0.0
**Date**: 2025-10-04

## Overview

This guide walks you through migrating existing Hive applications to use the new `BaseApplication` class from `hive-app-toolkit`. The migration eliminates boilerplate code while maintaining all existing functionality.

## Prerequisites

- Project Unify V2 complete (unified configuration)
- Golden Rule 37 active (configuration enforcement)
- App using `load_config_for_app()` or ready to migrate
- Understanding of async/await patterns

## Migration Benefits

**Before Migration**:
- 200-300 lines of manual boilerplate per app
- Manual resource initialization
- Custom shutdown handling
- Inconsistent patterns across apps
- Easy to forget resource cleanup

**After Migration**:
- 20-50 lines of focused business logic
- Automatic resource management
- Guaranteed graceful shutdown
- Consistent pattern across all apps
- Impossible to forget cleanup

## Migration Steps

### Step 1: Review Current Entry Point

Identify your app's entry point (usually `main.py`, `__main__.py`, or `app.py`).

**Common patterns you'll replace**:
- Manual configuration loading
- Manual database connection setup
- Manual cache client creation
- Manual event bus initialization
- Custom signal handlers
- Manual shutdown logic

### Step 2: Create New BaseApplication Class

Create a new file or replace your entry point with a BaseApplication subclass.

**Template**:
```python
from hive_app_toolkit import BaseApplication


class MyApp(BaseApplication):
    """Your application description"""

    # REQUIRED: Set your app name
    app_name = "my-app"  # Must match directory name in apps/

    async def initialize_services(self):
        """Initialize your app-specific services"""
        # Move service initialization here
        # Use: self.config, self.db, self.cache, self.event_bus
        pass

    async def run(self):
        """Main application logic"""
        # Move your main loop or server startup here
        pass

    async def cleanup_services(self):
        """Optional: Clean up app services"""
        # Most apps don't need this - resource cleanup is automatic
        pass


if __name__ == "__main__":
    app = MyApp()
    app.start()  # Blocks until shutdown
```

### Step 3: Move Configuration Loading

**Before** (manual):
```python
from hive_config import load_config_for_app

config = load_config_for_app("my-app")
```

**After** (automatic):
```python
# No code needed! BaseApplication loads config automatically
# Access via: self.config
```

**In initialize_services**:
```python
async def initialize_services(self):
    # Config already loaded and available
    timeout = self.config.worker.timeout
    poll_interval = self.config.worker.poll_interval
```

### Step 4: Move Resource Initialization

**Before** (manual):
```python
from hive_db import get_sqlite_connection
from hive_cache import get_cache_client
from hive_bus import get_event_bus

db = get_sqlite_connection()
cache = get_cache_client()
bus = get_event_bus()
```

**After** (automatic):
```python
# No code needed! BaseApplication initializes resources automatically
# Access via: self.db, self.cache, self.event_bus
```

**In initialize_services**:
```python
async def initialize_services(self):
    # Resources already initialized and available
    self.my_service = MyService(
        config=self.config,
        db=self.db,  # Already connected
        cache=self.cache,  # Already initialized
        bus=self.event_bus  # Already created
    )
```

### Step 5: Move Main Application Logic

**Pattern A: Long-Running Worker**

**Before**:
```python
async def main():
    running = True

    def handle_signal(sig):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    while running:
        await poll_tasks()
        await asyncio.sleep(30)

    # Cleanup
    await cleanup()
```

**After**:
```python
async def run(self):
    # Signal handling automatic!
    while not self._shutdown_requested:
        await self.poll_tasks()
        await asyncio.sleep(30)
    # Cleanup automatic!
```

**Pattern B: FastAPI Service**

**Before**:
```python
app = FastAPI(title="My Service")

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

**After**:
```python
async def initialize_services(self):
    self.fastapi_app = FastAPI(title="My Service")

    @self.fastapi_app.get("/health")
    async def health():
        return await self.health_check()

async def run(self):
    config = uvicorn.Config(
        self.fastapi_app,
        host=self.config.api.host,
        port=self.config.api.port
    )
    server = uvicorn.Server(config)
    await server.serve()
```

**Pattern C: CLI Application**

**Before**:
```python
import click

@click.command()
@click.option("--task-id")
def main(task_id):
    # Process task
    pass

if __name__ == "__main__":
    main()
```

**After**:
```python
async def initialize_services(self):
    self.cli = create_cli_interface()

async def run(self):
    # For CLI mode
    if self.config.cli_mode:
        self.cli()
    else:
        # For daemon mode
        while not self._shutdown_requested:
            await self.process_tasks()
```

### Step 6: Move Shutdown Logic

**Before** (manual):
```python
try:
    await main()
finally:
    if db:
        db.close()
    if cache:
        await cache.close()
    if bus:
        await bus.close()
```

**After** (automatic):
```python
# No code needed! BaseApplication handles all cleanup
# Override cleanup_services() ONLY if you have custom cleanup:

async def cleanup_services(self):
    # Optional - only if you have custom resources to clean
    if self.my_custom_service:
        await self.my_custom_service.stop()
```

### Step 7: Update Tests

**Before**:
```python
async def test_app():
    app = MyApp()
    await app.main()
```

**After**:
```python
async def test_app():
    # Inject test config for dependency injection
    test_config = create_test_config()
    app = MyApp(config=test_config)

    # Initialize without running
    await app.setup_resources()
    await app.initialize_services()

    # Test your services
    assert app.my_service is not None

    # Cleanup
    await app.cleanup_services()
    await app.cleanup_resources()
```

## Complete Migration Examples

### Example 1: Worker App (ai-planner)

**Before** (200+ lines):
```python
import asyncio
import signal
from hive_config import load_config_for_app
from hive_db import get_sqlite_connection
from hive_cache import get_cache_client
from hive_bus import get_event_bus
from hive_logging import get_logger

logger = get_logger(__name__)
running = True

def handle_shutdown(sig):
    global running
    running = False
    logger.info("Shutdown signal received")

async def main():
    # Load config
    config = load_config_for_app("ai-planner")

    # Initialize resources
    db = get_sqlite_connection()
    cache = get_cache_client()
    bus = get_event_bus()

    # Create service
    planner = PlanningService(config, db, cache, bus)

    # Setup signal handlers
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    # Main loop
    try:
        while running:
            await planner.poll_tasks()
            await asyncio.sleep(config.worker.poll_interval)
    finally:
        # Cleanup
        await planner.stop()
        if db:
            db.close()
        if cache:
            await cache.close()
        if bus:
            await bus.close()

if __name__ == "__main__":
    asyncio.run(main())
```

**After** (35 lines):
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

    async def cleanup_services(self):
        """Stop planning service"""
        if self.planning_service:
            await self.planning_service.stop()


if __name__ == "__main__":
    app = AIPlannerApp()
    app.start()
```

**Reduction**: 200+ lines → 35 lines (83% reduction)

### Example 2: FastAPI Service (ecosystemiser)

**Before** (442 lines in main.py):
```python
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ecosystemiser.settings import get_settings
from hive_logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

app = FastAPI(
    title=settings.api.title,
    description=settings.api.description,
    version=settings.api.version
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api.cors_origins,
    allow_methods=settings.api.cors_methods,
    allow_headers=settings.api.cors_headers,
    allow_credentials=True,
)

# ... 400+ more lines of route definitions ...

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )
```

**After** (45 lines):
```python
from hive_app_toolkit import BaseApplication
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


class EcoSystemiserApp(BaseApplication):
    """Energy system optimization platform"""

    app_name = "ecosystemiser"

    async def initialize_services(self):
        """Initialize FastAPI app and routers"""
        self.fastapi_app = FastAPI(
            title="EcoSystemiser",
            version=self.config.api.version,
            description="Energy system optimization platform"
        )

        # CORS middleware
        self.fastapi_app.add_middleware(
            CORSMiddleware,
            allow_origins=self.config.api.cors_origins,
            allow_methods=self.config.api.cors_methods,
            allow_headers=self.config.api.cors_headers,
            allow_credentials=True,
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
            port=self.config.api.port,
            reload=self.config.debug
        )
        server = uvicorn.Server(config)
        await server.serve()


if __name__ == "__main__":
    app = EcoSystemiserApp()
    app.start()
```

**Note**: Router definitions move to separate files (already a best practice)

**Reduction**: 442 lines → 45 lines (90% reduction in boilerplate)

## Common Migration Patterns

### Pattern: Conditional Resource Initialization

**Before**:
```python
if config.cache.enabled:
    cache = get_cache_client()
else:
    cache = None
```

**After**:
```python
# BaseApplication handles this automatically!
# self.cache will be None if config.cache.enabled = False
```

### Pattern: Custom Health Checks

**Before**:
```python
def health():
    return {
        "status": "healthy",
        "database": db.ping(),
        "custom": my_service.health()
    }
```

**After**:
```python
async def health_check(self):
    # Get base health (includes db, cache, bus)
    health = await super().health_check()

    # Add custom checks
    if self.my_service:
        health["resources"]["my_service"] = await self.my_service.health()

    return health
```

### Pattern: Graceful Shutdown with Timeout

**Before**:
```python
async def shutdown_with_timeout():
    try:
        await asyncio.wait_for(cleanup(), timeout=30.0)
    except asyncio.TimeoutError:
        logger.warning("Cleanup timeout, forcing shutdown")
```

**After**:
```python
async def cleanup_services(self):
    # Add timeout to your custom cleanup
    try:
        await asyncio.wait_for(
            self.my_service.stop(),
            timeout=30.0
        )
    except asyncio.TimeoutError:
        self.logger.warning("Service cleanup timeout")
    # Base cleanup continues automatically
```

## Common Gotchas and Solutions

### Gotcha 1: Forgetting `app_name` Class Variable

**Error**:
```
ValueError: MyApp must define 'app_name' class variable
```

**Solution**:
```python
class MyApp(BaseApplication):
    app_name = "my-app"  # Add this!
```

### Gotcha 2: Blocking in `run()` Method

**Wrong**:
```python
async def run(self):
    # This blocks forever, preventing shutdown
    uvicorn.run(self.fastapi_app)  # BLOCKING
```

**Right**:
```python
async def run(self):
    # This allows shutdown signals
    config = uvicorn.Config(self.fastapi_app)
    server = uvicorn.Server(config)
    await server.serve()  # ASYNC
```

### Gotcha 3: Not Checking Shutdown Flag

**Wrong**:
```python
async def run(self):
    while True:  # Never checks shutdown!
        await self.work()
```

**Right**:
```python
async def run(self):
    while not self._shutdown_requested:  # Checks shutdown
        await self.work()
        await asyncio.sleep(interval)
```

### Gotcha 4: Manual Signal Handlers

**Wrong**:
```python
async def initialize_services(self):
    # Don't do this - BaseApplication handles signals!
    signal.signal(signal.SIGTERM, my_handler)
```

**Right**:
```python
# No manual signal handling needed!
# BaseApplication registers handlers automatically
```

### Gotcha 5: Forgetting `await` in Async Methods

**Wrong**:
```python
async def initialize_services(self):
    self.service = MyService()
    self.service.start()  # Missing await!
```

**Right**:
```python
async def initialize_services(self):
    self.service = MyService()
    await self.service.start()  # Properly awaited
```

## Testing After Migration

### Unit Testing

```python
import pytest
from my_app import MyApp
from hive_config import create_test_config


@pytest.mark.asyncio
async def test_app_initialization():
    """Test app initializes correctly"""
    config = create_test_config("my-app")
    app = MyApp(config=config)

    await app.setup_resources()
    await app.initialize_services()

    assert app.my_service is not None
    assert app.db is not None

    await app.cleanup_resources()


@pytest.mark.asyncio
async def test_app_health_check():
    """Test health check includes all resources"""
    app = MyApp(config=create_test_config("my-app"))
    await app.setup_resources()
    await app.initialize_services()

    health = await app.health_check()

    assert health["status"] == "healthy"
    assert "database" in health["resources"]
    assert health["running"] is False  # Not started yet

    await app.cleanup_resources()
```

### Integration Testing

```python
@pytest.mark.integration
async def test_full_lifecycle():
    """Test complete app lifecycle"""
    app = MyApp()

    # Start in background
    task = asyncio.create_task(app._async_start())

    # Wait for startup
    await asyncio.sleep(2)

    # Verify running
    assert app._running is True

    # Trigger shutdown
    await app.shutdown()

    # Wait for completion
    await task

    # Verify stopped
    assert app._running is False
```

## Checklist

Use this checklist to ensure complete migration:

- [ ] Created BaseApplication subclass
- [ ] Set `app_name` class variable
- [ ] Moved service initialization to `initialize_services()`
- [ ] Moved main logic to `run()`
- [ ] Removed manual config loading (using `self.config`)
- [ ] Removed manual resource initialization (using `self.db`, `self.cache`, `self.event_bus`)
- [ ] Removed manual signal handlers
- [ ] Removed manual cleanup code (or moved to `cleanup_services()`)
- [ ] Updated main entry point to call `app.start()`
- [ ] Tested initialization
- [ ] Tested main logic
- [ ] Tested graceful shutdown
- [ ] Tested health checks
- [ ] Updated tests to use DI pattern
- [ ] Removed old boilerplate code
- [ ] Updated documentation

## Next Steps

1. **Test locally**: Run your migrated app and verify all functionality
2. **Check logs**: Ensure startup/shutdown messages appear correctly
3. **Test signals**: Send SIGTERM/SIGINT and verify graceful shutdown
4. **Health checks**: Verify health endpoint works (if applicable)
5. **Submit PR**: Document the migration in commit message
6. **Update docs**: Update app README with new startup instructions

## Getting Help

- **Specification**: See `claudedocs/base_application_api_spec.md`
- **Examples**: See migrated apps in `apps/*/`
- **Issues**: Check if similar migration already done
- **Questions**: Consult platform team or create issue

## Summary

BaseApplication eliminates boilerplate while improving:
- **Consistency**: All apps follow same lifecycle pattern
- **Safety**: Guaranteed resource cleanup even on crashes
- **Simplicity**: Focus on business logic, not infrastructure
- **Testability**: Dependency injection makes testing trivial

**Before**: 200-300 lines of boilerplate per app
**After**: 20-50 lines of focused business logic

**Net platform reduction**: ~1,500 lines (60% boilerplate eliminated)

The migration is straightforward and the benefits are immediate. Welcome to Project Launchpad!
