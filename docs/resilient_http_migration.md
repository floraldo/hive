# Resilient HTTP Client Migration Guide

Migrate existing HTTP requests to use circuit breaker-protected resilient clients for improved fault tolerance.

## Why Migrate?

**Problem**: Direct `requests.get()` / `requests.post()` calls can cause:
- Cascading failures when external services are down
- Thread exhaustion from hanging requests
- No automatic retry or backoff
- Difficulty diagnosing external service issues

**Solution**: `ResilientHttpClient` provides:
- Circuit breaker protection per domain
- Automatic retry with exponential backoff
- Configurable timeouts
- Request/failure statistics
- Graceful degradation

## Quick Migration Examples

### Synchronous HTTP Calls

**Before** - Direct requests usage:
```python
import requests

# No protection against external failures
response = requests.get("https://api.example.com/data", timeout=10)
data = response.json()
```

**After** - With resilient client:
```python
from hive_async import get_resilient_http_client

client = get_resilient_http_client()

# Now protected by circuit breaker, with automatic retry
response = client.get("https://api.example.com/data", timeout=10)
data = response.json()
```

### Async HTTP Calls

**Before** - Direct aiohttp/httpx usage:
```python
import aiohttp

async with aiohttp.ClientSession() as session:
    async with session.get("https://api.example.com/data") as response:
        data = await response.json()
```

**After** - With async resilient client:
```python
from hive_async import get_async_resilient_http_client

client = get_async_resilient_http_client()

response = await client.get("https://api.example.com/data", timeout=10)
data = await response.json()
```

## Migration Strategy

### Step 1: Identify External API Calls

Search for patterns:
```bash
# Find synchronous requests calls
grep -r "requests\.(get|post|put|delete)" --include="*.py"

# Find async HTTP calls
grep -r "aiohttp\.|httpx\." --include="*.py"
```

### Step 2: Replace with Resilient Client

For each HTTP call:

1. **Import the resilient client**:
```python
from hive_async import get_resilient_http_client  # Sync
from hive_async import get_async_resilient_http_client  # Async
```

2. **Get client instance**:
```python
client = get_resilient_http_client()  # Reuses singleton
```

3. **Replace request call**:
```python
# OLD: response = requests.get(url, timeout=5)
# NEW: response = client.get(url, timeout=5)
```

### Step 3: Handle Circuit Breaker Exceptions

Add handling for when circuit breaker is open:

```python
from hive_async import get_resilient_http_client
from hive_errors import CircuitBreakerOpenError

client = get_resilient_http_client()

try:
    response = client.get("https://api.example.com/data")
    data = response.json()
except CircuitBreakerOpenError as e:
    # Circuit breaker is open - external service is degraded
    logger.warning(f"Circuit breaker open: {e}")
    # Use cached data or return graceful degradation
    data = get_cached_fallback_data()
except requests.RequestException as e:
    # Individual request failed (within circuit breaker tolerance)
    logger.error(f"Request failed: {e}")
    raise
```

## Configuration

### Custom Client Configuration

For specialized needs, create custom client instances:

```python
from hive_async import ResilientHttpClient

# Custom configuration for sensitive operations
critical_client = ResilientHttpClient(
    failure_threshold=5,       # Open circuit after 5 failures
    recovery_timeout=60,       # Wait 60s before retry
    default_timeout=30.0,      # 30s request timeout
    max_retries=3              # Retry up to 3 times
)

response = critical_client.get("https://critical-api.example.com/data")
```

### Tuning Guidelines

**Failure Threshold** - How many failures before circuit opens:
- **Low traffic APIs** (< 10 req/min): `failure_threshold=2-3`
- **Medium traffic APIs** (10-100 req/min): `failure_threshold=5` (default)
- **High traffic APIs** (> 100 req/min): `failure_threshold=10-20`

**Recovery Timeout** - Seconds before attempting to close circuit:
- **Fast-recovering services**: `recovery_timeout=15-30`
- **Standard services**: `recovery_timeout=60` (default)
- **Slow services**: `recovery_timeout=120-300`

**Max Retries**:
- **Idempotent operations** (GET): `max_retries=3`
- **Non-idempotent operations** (POST): `max_retries=1`

## Monitoring

### Check Circuit Breaker Status

```python
client = get_resilient_http_client()

# Get statistics
stats = client.get_stats()
print(f"Total requests: {stats['total_requests']}")
print(f"Success rate: {stats['successful_requests'] / stats['total_requests']:.1%}")
print(f"Circuit breaker blocks: {stats['circuit_breaker_blocks']}")

# Check per-domain circuit breakers
for domain, breaker_status in stats['circuit_breakers'].items():
    print(f"{domain}: {breaker_status['state']}")
```

### Manual Circuit Breaker Reset

If you know an external service has recovered:

```python
client = get_resilient_http_client()

# Reset circuit breaker for specific domain
client.reset_circuit_breaker("api.example.com")

# Or reset all circuit breakers
client.reset_circuit_breaker()
```

## Real-World Examples

### Example 1: Deployment Health Checks

**File**: `packages/hive-deployment/src/hive_deployment/deployment.py`

**Before**:
```python
def health_check(app_url: str, timeout: int = 10):
    health_url = f"{app_url}/health"
    response = requests.get(health_url, timeout=timeout, verify=True)
    return response.status_code == 200
```

**After**:
```python
from hive_async import get_resilient_http_client
from hive_errors import CircuitBreakerOpenError

def health_check(app_url: str, timeout: int = 10):
    client = get_resilient_http_client()
    health_url = f"{app_url}/health"

    try:
        response = client.get(health_url, timeout=timeout, verify=True)
        return response.status_code == 200
    except CircuitBreakerOpenError:
        # Circuit breaker open means repeated failures
        logger.warning(f"Circuit breaker open for {app_url} - marking unhealthy")
        return False
    except requests.RequestException as e:
        logger.error(f"Health check failed for {app_url}: {e}")
        return False
```

### Example 2: Production Monitoring

**File**: `scripts/operational_excellence/production_monitor.py`

**Before**:
```python
def check_endpoint(url: str):
    response = requests.get(url, timeout=5, headers={"User-Agent": "Monitor"})
    return {
        "status_code": response.status_code,
        "response_time": response.elapsed.total_seconds()
    }
```

**After**:
```python
from hive_async import get_resilient_http_client
from hive_errors import CircuitBreakerOpenError

def check_endpoint(url: str):
    client = get_resilient_http_client()

    try:
        response = client.get(url, timeout=5, headers={"User-Agent": "Monitor"})
        return {
            "status_code": response.status_code,
            "response_time": response.elapsed.total_seconds(),
            "circuit_breaker_open": False
        }
    except CircuitBreakerOpenError:
        return {
            "status_code": 503,
            "response_time": 0,
            "circuit_breaker_open": True,
            "error": "Circuit breaker protection active"
        }
    except requests.RequestException as e:
        return {
            "status_code": 500,
            "response_time": 0,
            "circuit_breaker_open": False,
            "error": str(e)
        }
```

### Example 3: AI Model API Calls

Already implemented in `packages/hive-ai/src/hive_ai/models/client.py`:

```python
from hive_async import AsyncCircuitBreaker

class ModelClient:
    def __init__(self, config: AIConfig):
        self._circuit_breakers: dict[str, AsyncCircuitBreaker] = {}

    def _get_circuit_breaker(self, provider: str) -> AsyncCircuitBreaker:
        if provider not in self._circuit_breakers:
            self._circuit_breakers[provider] = AsyncCircuitBreaker(
                failure_threshold=self.config.failure_threshold,
                recovery_timeout=self.config.recovery_timeout
            )
        return self._circuit_breakers[provider]

    async def generate_async(self, prompt: str, model: str | None = None):
        circuit_breaker = self._get_circuit_breaker(model_config.provider)
        response = await circuit_breaker.call_async(
            provider.generate_async, prompt, model_config.name, **params
        )
        return response
```

## Testing Circuit Breaker Behavior

### Simulate Failures

```python
from hive_async import ResilientHttpClient
import requests

client = ResilientHttpClient(failure_threshold=3, recovery_timeout=10)

# Simulate 3 failures to open circuit
for i in range(3):
    try:
        client.get("https://nonexistent-api.example.com/data")
    except requests.RequestException:
        print(f"Failure {i+1}")

# Next request should be blocked by circuit breaker
try:
    client.get("https://nonexistent-api.example.com/data")
except CircuitBreakerOpenError as e:
    print(f"Circuit breaker is now OPEN: {e}")
```

### Verify Recovery

```python
import time

# Wait for recovery timeout
time.sleep(10)

# Circuit should attempt to close (half-open state)
try:
    response = client.get("https://api.example.com/data")
    print("Circuit breaker recovered - request succeeded")
except CircuitBreakerOpenError:
    print("Circuit still open")
```

## Rollout Plan

### Phase 1: Non-Critical Endpoints
- Monitoring scripts
- Admin tools
- Background jobs

### Phase 2: API Integrations
- Third-party API calls
- External data sources
- Webhook deliveries

### Phase 3: Critical Path
- Health checks
- Service-to-service calls
- Customer-facing integrations

### Phase 4: Validation
- Monitor circuit breaker statistics
- Verify expected failure handling
- Tune thresholds based on observed patterns

## Troubleshooting

### Circuit Breaker Opening Too Frequently

**Problem**: Circuit opens after normal transient errors

**Solution**: Increase `failure_threshold`:
```python
client = ResilientHttpClient(failure_threshold=10)  # Was 3, now 10
```

### Circuit Breaker Not Opening

**Problem**: Service degraded but circuit stays closed

**Solution**: Decrease `failure_threshold` or check exception types:
```python
# Ensure correct exception type is configured
client = ResilientHttpClient(
    failure_threshold=3,
    expected_exception=requests.RequestException  # Default
)
```

### Slow Recovery

**Problem**: Circuit stays open too long after service recovers

**Solution**: Reduce `recovery_timeout`:
```python
client = ResilientHttpClient(recovery_timeout=30)  # Was 60, now 30
```

## Best Practices

1. **Use global singleton for general requests**: `get_resilient_http_client()`
2. **Create custom instances for specialized needs**: Critical paths, specific SLAs
3. **Always handle CircuitBreakerOpenError**: Provide graceful degradation
4. **Monitor circuit breaker statistics**: Track blocks and failures
5. **Tune thresholds based on traffic patterns**: More traffic = higher threshold
6. **Test circuit breaker behavior**: Verify opens and closes as expected
7. **Document external dependencies**: Track which services have circuit breakers