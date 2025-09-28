# Singleton Elimination & Dependency Injection Analysis

## Executive Summary

The Hive platform contains multiple problematic singleton patterns that create:
- **Race conditions** during initialization
- **Testing difficulties** due to global state
- **Tight coupling** between components
- **Initialization order dependencies**
- **Thread safety issues**

This analysis identifies all singleton anti-patterns and provides a comprehensive refactoring plan to implement proper dependency injection.

## Problematic Singletons Identified

### 🔴 Critical - High Risk Singletons

#### 1. Configuration Singleton
**File**: `packages/hive-config/src/hive_config/unified_config.py`
**Pattern**: Global `_config_instance`
```python
_config_instance: Optional[HiveConfig] = None

def load_config() -> HiveConfig:
    global _config_instance
    if _config_instance is None:
        _config_instance = HiveConfig()
    return _config_instance
```
**Issues**:
- Thread safety concerns
- Cannot test with different configurations
- Initialization order dependency

#### 2. Database Connection Pool Singletons
**Files**:
- `apps/hive-orchestrator/src/hive_orchestrator/core/db/async_connection_pool.py`
- `apps/hive-orchestrator/src/hive_orchestrator/core/claude/claude_service.py`

**Pattern**: Class-level singleton with `__new__` override
```python
class AsyncConnectionPool:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance
```
**Issues**:
- Race conditions in multi-threaded environments
- Cannot create multiple pools for testing
- Tight coupling to global configuration

#### 3. Error Reporter Singleton
**File**: `apps/hive-orchestrator/src/hive_orchestrator/core/errors/error_reporter.py`
**Pattern**: Global instance with lazy initialization
```python
_reporter_instance: Optional[ErrorReporter] = None

def get_error_reporter() -> ErrorReporter:
    global _reporter_instance
    if _reporter_instance is None:
        _reporter_instance = ErrorReporter()
    return _reporter_instance
```
**Issues**:
- Cannot mock for testing
- Global state sharing across tests

#### 4. Claude Service Singleton
**File**: `apps/hive-orchestrator/src/hive_orchestrator/core/claude/claude_service.py`
**Pattern**: Thread-safe singleton with lock
```python
class ClaudeService:
    _instance = None
    _lock = Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
        return cls._instance
```
**Issues**:
- Still prevents multiple instances for testing
- Depends on global configuration

### 🟡 Medium Risk Singletons

#### 5. Climate Service Singleton
**File**: `apps/ecosystemiser/src/EcoSystemiser/profile_loader/climate/service.py`
```python
_global_service: Optional[ClimateService] = None

def get_enhanced_climate_service() -> ClimateService:
    global _global_service
    if _global_service is None:
        _global_service = ClimateService()
    return _global_service
```

#### 6. Adapter Factory Singleton
**File**: `apps/ecosystemiser/src/EcoSystemiser/profile_loader/climate/adapters/factory.py`
```python
_adapter_instances: Dict[str, BaseAdapter] = {}
```

#### 7. Job Manager Singleton
**File**: `apps/ecosystemiser/src/EcoSystemiser/profile_loader/climate/job_manager.py`
```python
_job_manager_instance = None

def get_job_manager():
    global _job_manager_instance
    if _job_manager_instance is None:
        _job_manager_instance = JobManager()
    return _job_manager_instance
```

### 🟢 Acceptable Singletons (Keep)

#### 1. Logger Instances
**Pattern**: Per-module logger instances
**Rationale**: Logging is inherently global and thread-safe

#### 2. Environment Configuration
**Pattern**: Process-level environment variables
**Rationale**: Environment is truly global to the process

## Dependency Chain Analysis

### Current Problematic Dependencies
```
get_config() → ClaudeService → AsyncConnectionPool → EventBus
     ↓
ErrorReporter → Database Connection → Global Config
     ↓
ClimateService → AdapterFactory → Global Config
```

### Issues with Current Chain
1. **Circular Dependencies**: Components depend on global config which may not be initialized
2. **Initialization Order**: No guaranteed order of singleton creation
3. **Testing Isolation**: Cannot test components in isolation
4. **Resource Leaks**: Singletons hold resources across test runs

## Dependency Injection Implementation Plan

### Phase 1: Create DI Container Framework

#### 1.1 Create Core DI Container
**File**: `packages/hive-di/src/hive_di/container.py`

Features:
- Service registration with lifecycle management
- Dependency resolution with circular dependency detection
- Factory pattern support
- Scoped instances (singleton, transient, scoped)
- Configuration-driven registration

#### 1.2 Create Service Interfaces
**Pattern**: Abstract base classes for all major services
- `IConfigurationService`
- `IDatabaseConnectionService`
- `IEventBusService`
- `IErrorReportingService`
- `IClaudeService`

#### 1.3 Implement Service Factories
**Pattern**: Factory classes that create configured instances
- `ConfigurationServiceFactory`
- `DatabaseServiceFactory`
- `EventBusServiceFactory`

### Phase 2: Replace Configuration Singleton

#### 2.1 Create Injectable Configuration Service
```python
class ConfigurationService(IConfigurationService):
    def __init__(self, config_source: ConfigSource):
        self._config = config_source.load()

    def get_database_config(self) -> DatabaseConfig:
        return self._config.database
```

#### 2.2 Update All get_config() Usage
- Replace `get_config()` calls with injected `IConfigurationService`
- Update constructors to accept configuration dependencies
- Remove global configuration access

### Phase 3: Replace Database Connection Singletons

#### 3.1 Create Injectable Connection Service
```python
class DatabaseConnectionService(IDatabaseConnectionService):
    def __init__(self, config: DatabaseConfig):
        self._pool = ConnectionPool(
            min_connections=config.min_connections,
            max_connections=config.max_connections
        )

    async def get_connection(self) -> Connection:
        return await self._pool.acquire()
```

#### 3.2 Update Connection Pool Patterns
- Remove `_instance` class variables
- Accept configuration in constructor
- Enable multiple pools for testing

### Phase 4: Replace Service Singletons

#### 4.1 EventBus Dependency Injection
```python
class EventBus(IEventBusService):
    def __init__(self,
                 connection_service: IDatabaseConnectionService,
                 config: EventBusConfig):
        self._connection_service = connection_service
        self._config = config
```

#### 4.2 Error Reporter Dependency Injection
```python
class ErrorReporter(IErrorReportingService):
    def __init__(self,
                 connection_service: IDatabaseConnectionService,
                 event_bus: IEventBusService):
        self._connection_service = connection_service
        self._event_bus = event_bus
```

#### 4.3 Claude Service Dependency Injection
```python
class ClaudeService(IClaudeService):
    def __init__(self,
                 config: ClaudeConfig,
                 error_reporter: IErrorReportingService):
        self._config = config
        self._error_reporter = error_reporter
```

### Phase 5: Create Service Registration

#### 5.1 Container Configuration
```python
def configure_services(container: DIContainer) -> None:
    # Configuration
    container.register(IConfigurationService,
                      ConfigurationServiceFactory(),
                      lifecycle=Lifecycle.SINGLETON)

    # Database
    container.register(IDatabaseConnectionService,
                      DatabaseServiceFactory(),
                      lifecycle=Lifecycle.SINGLETON)

    # Event Bus
    container.register(IEventBusService,
                      EventBusFactory(),
                      lifecycle=Lifecycle.SINGLETON)

    # Error Reporting
    container.register(IErrorReportingService,
                      ErrorReporterFactory(),
                      lifecycle=Lifecycle.SINGLETON)
```

#### 5.2 Application Startup
```python
def initialize_application() -> DIContainer:
    container = DIContainer()
    configure_services(container)
    return container

# In main applications
container = initialize_application()
claude_service = container.resolve(IClaudeService)
```

### Phase 6: Update Tests

#### 6.1 Test Service Factories
```python
def create_test_container() -> DIContainer:
    container = DIContainer()

    # Mock services for testing
    container.register(IConfigurationService,
                      lambda: MockConfigurationService(),
                      lifecycle=Lifecycle.TRANSIENT)

    container.register(IDatabaseConnectionService,
                      lambda: InMemoryDatabaseService(),
                      lifecycle=Lifecycle.TRANSIENT)

    return container
```

#### 6.2 Test Isolation
- Each test gets its own container
- No shared state between tests
- Easy mocking of dependencies

## Implementation Schedule

### Week 1: Foundation
- [ ] Create DI container framework
- [ ] Define service interfaces
- [ ] Create basic service factories

### Week 2: Configuration Injection
- [ ] Replace configuration singleton
- [ ] Update all get_config() usage
- [ ] Test configuration injection

### Week 3: Database Injection
- [ ] Replace connection pool singletons
- [ ] Update database-dependent services
- [ ] Test database connection isolation

### Week 4: Service Injection
- [ ] Replace EventBus singleton
- [ ] Replace ErrorReporter singleton
- [ ] Replace ClaudeService singleton

### Week 5: Testing & Documentation
- [ ] Update all test suites
- [ ] Create migration documentation
- [ ] Performance validation

## Benefits of This Approach

### ✅ Improved Testability
- Each component can be tested in isolation
- Easy mocking and stubbing of dependencies
- No global state pollution between tests

### ✅ Eliminated Race Conditions
- No more singleton initialization races
- Explicit dependency ordering
- Thread-safe by design

### ✅ Better Configuration Management
- Multiple configurations for different environments
- Easy configuration testing and validation
- Clear configuration boundaries

### ✅ Enhanced Modularity
- Loose coupling between components
- Clear dependency interfaces
- Easier component replacement

### ✅ Simplified Testing
- Deterministic test behavior
- Fast test execution (no global cleanup)
- Parallel test execution support

## Migration Strategy

### Backward Compatibility
- Keep existing global functions as deprecated wrappers
- Provide migration period with warnings
- Gradual migration path for existing code

### Risk Mitigation
- Phase-by-phase implementation
- Extensive test coverage for each phase
- Performance benchmarking at each step
- Rollback plans for each phase

## Success Metrics

- **Test Execution Speed**: 50%+ improvement due to no global cleanup
- **Test Isolation**: 100% isolated tests with no shared state
- **Code Coverage**: Maintain or improve current coverage
- **Race Condition Elimination**: Zero race conditions in dependency creation
- **Configuration Flexibility**: Support for multiple configurations per process

This implementation will eliminate all problematic singleton patterns while maintaining the performance and functionality of the Hive platform.