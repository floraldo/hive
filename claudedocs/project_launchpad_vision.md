# Project Launchpad - Vision Document

**Status**: Vision - Ready After Project Unify V2 Solidification
**Foundation**: Built on unified configuration system
**Goal**: Standardize application lifecycle across all 10 Hive apps

## The Vision

Every Hive application currently reinvents the wheel for startup, configuration, resource management, and shutdown. Project Launchpad will create a `BaseApplication` class that makes `main.py` trivial and boilerplate-free.

## Current State (Before Launchpad)

**Each app manually handles**:
- Configuration loading (now unified, but still manual)
- Database connection setup
- Cache client initialization
- Event bus creation
- Logging configuration
- Graceful shutdown handling
- Health check endpoints
- Resource cleanup

**Result**: ~200-300 lines of boilerplate per app, duplicated 10 times

## Future State (After Launchpad)

**Typical main.py** (AI-Planner example):

```python
from hive_app_toolkit import BaseApplication
from ai_planner.services import PlanningService

class AIPlannerApp(BaseApplication):
    """AI Planning application"""

    app_name = "ai-planner"

    async def initialize_services(self):
        """Initialize app-specific services"""
        self.planning_service = PlanningService(
            config=self.config,  # Provided by BaseApplication
            db=self.db,          # Provided by BaseApplication
            cache=self.cache,    # Provided by BaseApplication
            bus=self.event_bus   # Provided by BaseApplication
        )

    async def run(self):
        """Main application logic"""
        await self.planning_service.start()
        await self.planning_service.poll_for_tasks()

if __name__ == "__main__":
    app = AIPlannerApp()
    app.start()  # Handles everything automatically
```

**That's it.** No boilerplate, no resource management, no shutdown logic.

## BaseApplication Responsibilities

The `BaseApplication` class in `hive-app-toolkit` will handle:

### 1. Configuration (Leverages Project Unify V2)
```python
class BaseApplication:
    def __init__(self):
        # Automatic unified config loading
        self.config = load_config_for_app(self.app_name)
```

### 2. Resource Initialization
```python
async def setup_resources(self):
    # Database
    self.db = create_database_manager(self.config.database)

    # Cache
    self.cache = create_cache_client(self.config.cache)

    # Event Bus
    self.event_bus = create_event_bus(self.config.bus)

    # Logging
    self.logger = get_app_logger(self.app_name, self.config.logging)
```

### 3. Lifecycle Management
```python
def start(self):
    """Complete startup sequence"""
    asyncio.run(self._async_start())

async def _async_start(self):
    # Setup phase
    await self.setup_resources()
    await self.initialize_services()  # App-specific (abstract)

    # Run phase
    try:
        await self.run()  # App-specific (abstract)
    except KeyboardInterrupt:
        await self.shutdown()

async def shutdown(self):
    """Graceful shutdown"""
    await self.cleanup_services()  # App-specific (optional)
    await self.cleanup_resources()  # Base class handles
```

### 4. Health & Monitoring
```python
async def health_check(self) -> dict:
    """Standard health check"""
    return {
        "status": "healthy",
        "app": self.app_name,
        "resources": {
            "database": await self.db.health(),
            "cache": await self.cache.health(),
            "bus": await self.event_bus.health()
        }
    }
```

## Impact

**Before**:
- 10 apps × 250 lines boilerplate = 2,500 lines
- Inconsistent patterns
- Easy to forget resource cleanup
- Duplicated error handling

**After**:
- 1 BaseApplication class (~500 lines)
- 10 apps × ~50 lines = 500 lines
- **Net reduction**: 2,000 lines eliminated
- Consistent patterns everywhere
- Guaranteed proper cleanup
- Centralized error handling

## Architecture

```
hive-app-toolkit/
  base_application.py        # BaseApplication class
  resource_managers/
    database.py              # create_database_manager()
    cache.py                 # create_cache_client()
    bus.py                   # create_event_bus()
  lifecycle/
    startup.py               # Startup sequence
    shutdown.py              # Graceful shutdown
```

## Abstract Methods (Apps Must Implement)

```python
class BaseApplication(ABC):
    app_name: str  # Class variable

    @abstractmethod
    async def initialize_services(self):
        """Initialize app-specific services"""
        pass

    @abstractmethod
    async def run(self):
        """Main application logic"""
        pass

    async def cleanup_services(self):
        """Optional cleanup for app services"""
        pass  # Default: no-op
```

## Migration Path

**Phase 1**: Create BaseApplication in hive-app-toolkit
**Phase 2**: Migrate 1 app as proof-of-concept (ai-planner)
**Phase 3**: Systematic migration of remaining 9 apps
**Phase 4**: Deprecate manual startup patterns

## Dependencies

✅ **Project Unify V2**: Complete
✅ **Unified Config**: All apps using `load_config_for_app()`
⏳ **Golden Rule 37**: Prevents regression
⏳ **App Migrations**: All apps on unified config

## Success Criteria

- All 10 apps inherit from BaseApplication
- Each app's main.py < 100 lines
- Consistent startup/shutdown across platform
- Zero resource leaks
- Standardized health checks

## Next Steps After Project Unify V2

1. ✅ Complete Project Unify V2 core infrastructure
2. ⏳ Implement Golden Rule 37 (the immune system)
3. ⏳ Migrate all 10 apps to unified config
4. 🎯 **Launch Project Launchpad**
   - Design BaseApplication API
   - Implement in hive-app-toolkit
   - Migrate apps one by one
   - Celebrate massive code reduction

## The Ultimate Goal

**Project Unify V2** unified configuration.
**Project Launchpad** will unify application lifecycle.

Together, they represent the ultimate essentialisation of the Hive platform - every app configured the same way, every app started the same way, every app shutdown the same way.

**Essence over accumulation. Always.**
