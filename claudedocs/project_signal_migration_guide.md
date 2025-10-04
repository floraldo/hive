# Project Signal: Unified Observability Migration Guide

## Overview

Project Signal standardizes observability across the Hive platform using decorator-based patterns from `hive-performance`. This guide covers migrating from app-specific observability to unified decorators.

## Migration Phases

### Phase 1: Build Decorator API ✅ COMPLETE
- ✅ Created 5 core decorators: `@timed`, `@counted`, `@traced`, `@measure_memory`, `@track_errors`
- ✅ Created 3 composite decorators: `@track_request`, `@track_cache_operation`, `@track_adapter_request`
- ✅ All 21 tests passing with comprehensive coverage
- ✅ Documentation updated

### Phase 2: Standardization (IN PROGRESS)
- Extract ObservabilityManager pattern to BaseApplication
- Migrate EcoSystemiser to use unified decorators
- Establish platform-wide patterns

### Phase 3: Platform Adoption (PENDING)
Priority order:
1. hive-orchestrator (coordination metrics critical)
2. ai-planner, ai-deployer, ai-reviewer (AI operation metrics)
3. ecosystemiser (migrate to unified decorators)
4. Guardian Agent (learning/feedback metrics)

### Phase 4: Golden Rule Enforcement (PENDING)
Create Golden Rule 35 for observability standards

## EcoSystemiser Migration

### Old Pattern (observability.py)

```python
# OLD: Explicit Prometheus metrics with custom decorators
from ecosystemiser.observability import (
    track_time,
    count_calls,
    trace_span,
    http_request_duration_seconds,
    http_requests_total,
)

@track_time(http_request_duration_seconds, {"endpoint": "/api/users"})
@count_calls(http_requests_total, {"endpoint": "/api/users"})
async def handle_request(request):
    return await process(request)
```

### New Pattern (hive-performance)

```python
# NEW: Unified decorators with metric name strings
from hive_performance import track_request

@track_request("api.users.get", labels={"endpoint": "/users"})
async def handle_request(request):
    return await process(request)
```

## Migration Steps

### Step 1: Install hive-performance decorators

```python
# Add to imports
from hive_performance import (
    # Core decorators
    timed, counted, traced, track_errors, measure_memory,
    # Composite decorators
    track_request, track_cache_operation, track_adapter_request,
)
```

### Step 2: Replace custom decorators

#### HTTP/API Request Tracking

```python
# BEFORE
@track_time(http_request_duration_seconds, {"endpoint": "/users"})
@count_calls(http_requests_total, {"endpoint": "/users"})
async def get_users():
    pass

# AFTER
@track_request("api.users.get", labels={"endpoint": "/users"})
async def get_users():
    pass
```

#### Cache Operations

```python
# BEFORE
@track_cache_operation("redis")
async def get_from_cache(key):
    pass

# AFTER
@track_cache_operation("redis", "get")
async def get_from_cache(key):
    pass
```

#### External Adapter Requests

```python
# BEFORE
@track_adapter_request("weather_api")
async def fetch_weather(location):
    pass

# AFTER
@track_adapter_request("weather_api")  # Same API!
async def fetch_weather(location):
    pass
```

### Step 3: Replace context managers with decorators

```python
# BEFORE
from ecosystemiser.observability import trace_span

async def process_data():
    with trace_span("data.processing", attributes={"source": "api"}):
        result = await process()
    return result

# AFTER
from hive_performance import traced

@traced("data.processing", attributes={"source": "api"})
async def process_data():
    result = await process()
    return result
```

### Step 4: Keep domain-specific metrics

Domain-specific Prometheus metrics should remain in `observability.py`:
- `climate_data_quality_score`
- `climate_data_gaps_total`
- `climate_adapter_data_points_total`
- `ClimateMetricsCollector` class

These are business-specific and not suitable for platform-level abstraction.

### Step 5: Keep ObservabilityManager for now

The `ObservabilityManager` class will be extracted to `BaseApplication` in a future phase. For now, keep:
- OpenTelemetry provider setup
- Auto-instrumentation (FastAPI, HTTPX, Redis)
- Lifecycle management (init/shutdown)

## Benefits of Migration

### 1. Simplified Imports
```python
# OLD: 5+ imports from observability
from ecosystemiser.observability import (
    track_time, count_calls, trace_span,
    http_request_duration_seconds, http_requests_total,
)

# NEW: 1 import
from hive_performance import track_request
```

### 2. Less Boilerplate
```python
# OLD: Manage Prometheus metrics + decorators
http_request_duration = Histogram("http_request_duration", ...)
http_requests_total = Counter("http_requests_total", ...)

@track_time(http_request_duration, {"endpoint": "/api"})
@count_calls(http_requests_total, {"endpoint": "/api"})
async def handler():
    pass

# NEW: Just metric name
@track_request("api.handler", labels={"endpoint": "/api"})
async def handler():
    pass
```

### 3. Consistent Patterns Platform-Wide
All apps use same decorator patterns for:
- HTTP request tracking
- Cache operations
- External adapter requests
- Error tracking
- Performance monitoring

### 4. Zero-Config Defaults
No need to create Prometheus registries or configure exporters - decorators work immediately.

## Compatibility Notes

### Prometheus Metrics Preservation
The new decorators use the same underlying Prometheus metric types:
- `@timed` → Histogram (compatible with old `track_time`)
- `@counted` → Counter (compatible with old `count_calls`)
- `@traced` → OpenTelemetry spans (compatible with old `trace_span`)

### Metric Naming Convention
Old: `climate_http_request_duration_seconds`
New: `api.request.duration` (with labels `{service: "climate"}`)

This follows OpenTelemetry conventions and enables better aggregation across services.

### Label Compatibility
Both old and new patterns support labels:
```python
# OLD
metric.labels(adapter="weather", status="success").inc()

# NEW
@counted("adapter.calls", labels={"adapter": "weather", "status": "success"})
```

## Testing Strategy

### 1. Parallel Deployment
Run old and new decorators side-by-side temporarily:
```python
from ecosystemiser.observability import track_time, http_request_duration_seconds
from hive_performance import timed

@track_time(http_request_duration_seconds, {"endpoint": "/api"})  # OLD
@timed("api.request.duration", labels={"endpoint": "/api"})       # NEW
async def handler():
    pass
```

Compare metrics output to ensure consistency.

### 2. Gradual Migration
Migrate one module at a time:
1. Start with low-traffic endpoints
2. Validate metrics in monitoring dashboard
3. Gradually expand to high-traffic endpoints
4. Remove old decorators when confident

### 3. Monitoring Validation
Check that all expected metrics appear:
```python
from hive_performance import get_all_metrics_summary

# After running tests
summary = get_all_metrics_summary()
print(summary)
# Should show all tracked metrics
```

## Next Steps

1. **Extract ObservabilityManager** → Move to `BaseApplication` in `hive-lifecycle`
2. **Migrate EcoSystemiser** → Replace old decorators with unified patterns
3. **Platform Adoption** → Roll out to other apps (orchestrator, ai-planner, etc.)
4. **Golden Rule** → Enforce observability standards via AST validation

## Resources

- Core decorators: `packages/hive-performance/src/hive_performance/decorators.py`
- Composite decorators: `packages/hive-performance/src/hive_performance/composite_decorators.py`
- Tests: `packages/hive-performance/tests/unit/test_decorators.py`
- README: `packages/hive-performance/README.md`
