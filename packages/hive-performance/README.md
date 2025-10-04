# Hive Performance

Performance monitoring, profiling, and optimization utilities.

## Features

- Async profiling and metrics collection
- System resource monitoring
- Performance analysis and reporting
- Integrated monitoring service

## Usage

```python
from hive_performance import MonitoringService, AsyncProfiler

monitor = MonitoringService()
profiler = AsyncProfiler()
```

## Components

- `async_profiler.py`: Async operation profiling
- `metrics_collector.py`: Performance metrics collection
- `monitoring_service.py`: Integrated monitoring orchestration
- `performance_analyzer.py`: Analysis and reporting
- `system_monitor.py`: System resource monitoring

##  Decorator-Based Observability (NEW)

Zero-config metrics, tracing, and monitoring via Python decorators.

### Core Decorators

Individual decorators for fine-grained control:

```python
from hive_performance import timed, counted, traced, track_errors, measure_memory

@timed("api.request_duration")          # Track execution time
@counted("api.requests")                 # Count function calls
@traced("api.handle_request")            # Distributed tracing
@track_errors("api.errors")              # Track error rates
@measure_memory("api.memory_usage")      # Track memory consumption
async def handle_request(request):
    return await process(request)
```

### Composite Decorators

High-level patterns for common scenarios (extracted from EcoSystemiser production usage):

```python
from hive_performance import track_request, track_cache_operation, track_adapter_request

# Track HTTP/API requests (combines @timed, @counted, @traced, @track_errors)
@track_request("api.users.get", labels={"endpoint": "/users"})
async def get_users(request):
    return await fetch_users()

# Track cache operations with hit/miss metrics
@track_cache_operation("redis", "get")
async def get_from_cache(key: str):
    return await redis.get(key)

# Track external adapter/API requests with success/failure status
@track_adapter_request("weather_api")
async def fetch_weather(location: str):
    return await api.get(f"/weather/{location}")
```

### Running Tests

```bash
# Core decorators (21 tests)
pytest packages/hive-performance/tests/unit/test_decorators.py -v

# Composite decorators (12 tests)
pytest packages/hive-performance/tests/unit/test_composite_decorators.py -v

# All tests (33 total)
pytest packages/hive-performance/tests/unit/ -v
```

**Test Coverage**:
- Core decorators: 21 tests (all 5 decorators: @timed, @counted, @traced, @track_errors, @measure_memory)
- Composite decorators: 12 tests (all 3 composites: @track_request, @track_cache_operation, @track_adapter_request)
- Integration tests: Performance overhead, thread safety, metric validation
- **Total: 33 passing tests**
