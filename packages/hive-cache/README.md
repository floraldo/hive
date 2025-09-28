# Hive Cache

High-performance Redis-based caching package for the Hive platform, designed to optimize Claude API calls and I/O operations with intelligent TTL management and circuit breaker patterns.

## Features

- **Async Redis Operations**: Full async/await support with connection pooling
- **Intelligent TTL Management**: Smart expiration based on content type and usage patterns
- **Circuit Breaker Integration**: Fail-safe operation with Redis outages
- **Multi-format Serialization**: MessagePack, JSON, and binary support
- **Compression**: Automatic compression for large payloads
- **Key Namespacing**: Organized cache hierarchies
- **Performance Monitoring**: Built-in metrics and health checks
- **Claude API Optimization**: Specialized caching for Claude responses

## Quick Start

```python
from hive_cache import get_cache_client

# Get async cache client
cache = await get_cache_client()

# Store data with TTL
await cache.set("user:123", user_data, ttl=3600)

# Retrieve data
user = await cache.get("user:123")

# Pattern operations
await cache.delete_pattern("session:*")

# Health check
health = await cache.health_check()
```

## Cache Strategies

### Claude API Caching
```python
from hive_cache import ClaudeAPICache

claude_cache = await ClaudeAPICache.create()

# Cache Claude responses with intelligent TTL
response = await claude_cache.get_or_fetch(
    prompt="Analyze this code",
    model="claude-3-opus",
    fetcher=lambda: claude_api.complete(prompt)
)
```

### Performance Caching
```python
from hive_cache import PerformanceCache

perf_cache = await PerformanceCache.create()

# Cache expensive computations
result = await perf_cache.cached_computation(
    "fibonacci_1000",
    fibonacci,
    args=(1000,),
    ttl=86400
)
```

## Configuration

```python
from hive_cache import CacheConfig

config = CacheConfig(
    redis_url="redis://localhost:6379/0",
    max_connections=20,
    socket_keepalive=True,
    health_check_interval=30,
    circuit_breaker_threshold=5,
    default_ttl=3600,
    compression_threshold=1024
)

cache = await get_cache_client(config)
```

## Installation

```bash
pip install hive-cache
```

For development:
```bash
poetry install
```