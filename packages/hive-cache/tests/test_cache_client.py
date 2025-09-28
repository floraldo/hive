"""Tests for HiveCacheClient."""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
import time

from hive_cache import HiveCacheClient, CacheConfig
from hive_cache.exceptions import CacheError, CacheConnectionError


@pytest.fixture
def cache_config():
    """Test cache configuration."""
    return CacheConfig(
        redis_url="redis://localhost:6379/15",  # Use test database
        max_connections=5,
        default_ttl=3600,
        circuit_breaker_threshold=3,
        health_check_interval=10.0
    )


@pytest.fixture
async def cache_client(cache_config):
    """Test cache client."""
    client = HiveCacheClient(cache_config)
    await client.initialize()
    yield client
    await client.close()


@pytest.mark.asyncio
async def test_cache_client_initialization(cache_config):
    """Test cache client initialization."""
    client = HiveCacheClient(cache_config)
    await client.initialize()

    assert client._redis_pool is not None
    assert client._circuit_breaker is not None

    await client.close()


@pytest.mark.asyncio
async def test_set_and_get(cache_client):
    """Test basic set and get operations."""
    # Test data
    key = "test_key"
    value = {"data": "test_value", "number": 42}

    # Set value
    success = await cache_client.set(key, value, ttl=60)
    assert success is True

    # Get value
    retrieved = await cache_client.get(key)
    assert retrieved == value

    # Cleanup
    await cache_client.delete(key)


@pytest.mark.asyncio
async def test_get_nonexistent_key(cache_client):
    """Test getting non-existent key."""
    result = await cache_client.get("nonexistent_key", default="default_value")
    assert result == "default_value"


@pytest.mark.asyncio
async def test_delete(cache_client):
    """Test delete operation."""
    key = "delete_test"
    value = "test_value"

    # Set and verify
    await cache_client.set(key, value)
    assert await cache_client.get(key) == value

    # Delete and verify
    success = await cache_client.delete(key)
    assert success is True
    assert await cache_client.get(key) is None


@pytest.mark.asyncio
async def test_exists(cache_client):
    """Test exists operation."""
    key = "exists_test"
    value = "test_value"

    # Key should not exist initially
    assert await cache_client.exists(key) is False

    # Set key and test existence
    await cache_client.set(key, value)
    assert await cache_client.exists(key) is True

    # Cleanup
    await cache_client.delete(key)


@pytest.mark.asyncio
async def test_ttl_operations(cache_client):
    """Test TTL-related operations."""
    key = "ttl_test"
    value = "test_value"

    # Set with TTL
    await cache_client.set(key, value, ttl=60)

    # Check TTL
    ttl = await cache_client.ttl(key)
    assert 50 <= ttl <= 60  # Allow some variation

    # Extend TTL
    success = await cache_client.extend_ttl(key, 120)
    assert success is True

    # Check new TTL
    new_ttl = await cache_client.ttl(key)
    assert 110 <= new_ttl <= 120

    # Cleanup
    await cache_client.delete(key)


@pytest.mark.asyncio
async def test_pattern_operations(cache_client):
    """Test pattern-based operations."""
    # Set multiple keys
    keys = ["pattern_test_1", "pattern_test_2", "pattern_test_3"]
    for key in keys:
        await cache_client.set(key, f"value_{key}")

    # Delete by pattern
    deleted_count = await cache_client.delete_pattern("pattern_test_*")
    assert deleted_count == len(keys)

    # Verify keys are deleted
    for key in keys:
        assert await cache_client.exists(key) is False


@pytest.mark.asyncio
async def test_get_or_set(cache_client):
    """Test get_or_set operation."""
    key = "get_or_set_test"

    def factory():
        return {"computed": True, "timestamp": time.time()}

    # First call should compute value
    value1 = await cache_client.get_or_set(key, factory, ttl=60)
    assert value1["computed"] is True

    # Second call should return cached value
    value2 = await cache_client.get_or_set(key, factory, ttl=60)
    assert value2 == value1

    # Cleanup
    await cache_client.delete(key)


@pytest.mark.asyncio
async def test_mget_mset(cache_client):
    """Test multiple get/set operations."""
    # Test data
    data = {
        "key1": "value1",
        "key2": {"nested": "value2"},
        "key3": [1, 2, 3]
    }

    # Set multiple values
    success = await cache_client.mset(data, ttl=60)
    assert success is True

    # Get multiple values
    retrieved = await cache_client.mget(list(data.keys()))
    assert retrieved == data

    # Cleanup
    for key in data.keys():
        await cache_client.delete(key)


@pytest.mark.asyncio
async def test_scan_keys(cache_client):
    """Test key scanning."""
    # Set test keys
    test_keys = [f"scan_test_{i}" for i in range(5)]
    for key in test_keys:
        await cache_client.set(key, f"value_{key}")

    # Scan keys
    found_keys = []
    async for key in cache_client.scan_keys("scan_test_*"):
        found_keys.append(key)

    assert len(found_keys) == len(test_keys)
    assert all(key in test_keys for key in found_keys)

    # Cleanup
    await cache_client.delete_pattern("scan_test_*")


@pytest.mark.asyncio
async def test_namespaces(cache_client):
    """Test namespace functionality."""
    key = "namespace_test"
    value1 = "value_in_namespace1"
    value2 = "value_in_namespace2"

    # Set same key in different namespaces
    await cache_client.set(key, value1, namespace="ns1")
    await cache_client.set(key, value2, namespace="ns2")

    # Verify values are separate
    assert await cache_client.get(key, namespace="ns1") == value1
    assert await cache_client.get(key, namespace="ns2") == value2

    # Cleanup
    await cache_client.delete(key, namespace="ns1")
    await cache_client.delete(key, namespace="ns2")


@pytest.mark.asyncio
async def test_serialization_formats(cache_config):
    """Test different serialization formats."""
    # Test with different serialization formats
    formats = ["msgpack", "json"]

    for fmt in formats:
        config = cache_config.copy(update={"serialization_format": fmt})
        client = HiveCacheClient(config)
        await client.initialize()

        try:
            # Test complex data
            test_data = {
                "string": "test",
                "number": 42,
                "float": 3.14,
                "list": [1, 2, 3],
                "nested": {"key": "value"}
            }

            await client.set("serialization_test", test_data)
            retrieved = await client.get("serialization_test")

            assert retrieved == test_data

        finally:
            await client.close()


@pytest.mark.asyncio
async def test_compression(cache_client):
    """Test compression functionality."""
    # Large data that should trigger compression
    large_data = {"data": "x" * 2000}  # Larger than compression threshold

    await cache_client.set("compression_test", large_data)
    retrieved = await cache_client.get("compression_test")

    assert retrieved == large_data

    # Cleanup
    await cache_client.delete("compression_test")


@pytest.mark.asyncio
async def test_health_check(cache_client):
    """Test health check functionality."""
    health = await cache_client.health_check()

    assert isinstance(health, dict)
    assert "healthy" in health
    assert "last_check" in health
    assert "response_time_ms" in health


def test_metrics(cache_client):
    """Test metrics collection."""
    metrics = cache_client.get_metrics()

    assert isinstance(metrics, dict)
    assert "hits" in metrics
    assert "misses" in metrics
    assert "sets" in metrics
    assert "deletes" in metrics
    assert "hit_rate_percent" in metrics


@pytest.mark.asyncio
async def test_circuit_breaker_functionality():
    """Test circuit breaker behavior."""
    # Mock a failing Redis connection
    config = CacheConfig(
        redis_url="redis://invalid:6379/0",
        circuit_breaker_threshold=2,
        circuit_breaker_timeout=60.0
    )

    client = HiveCacheClient(config)

    # This should fail to initialize
    with pytest.raises(CacheConnectionError):
        await client.initialize()


@pytest.mark.asyncio
async def test_ttl_clamping(cache_client):
    """Test TTL clamping to configured limits."""
    key = "ttl_clamp_test"
    value = "test_value"

    # Test with TTL above maximum
    await cache_client.set(key, value, ttl=999999)
    ttl = await cache_client.ttl(key)
    assert ttl <= cache_client.config.max_ttl

    # Cleanup
    await cache_client.delete(key)


@pytest.mark.asyncio
async def test_key_generation(cache_client):
    """Test cache key generation and namespacing."""
    config = cache_client.config

    # Test normal key
    key = config.get_namespaced_key("test_ns", "test_key")
    assert key.startswith(config.key_prefix)
    assert "test_ns" in key
    assert "test_key" in key

    # Test very long key (should be hashed)
    long_key = "x" * 300
    hashed_key = config.get_namespaced_key("test_ns", long_key)
    assert len(hashed_key) <= config.max_key_length