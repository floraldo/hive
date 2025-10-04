"""Tests for HiveCacheClient."""
import time
import pytest
from hive_cache import CacheConfig, HiveCacheClient
from hive_cache.exceptions import CacheConnectionError

@pytest.fixture
def cache_config():
    """Test cache configuration."""
    return CacheConfig(redis_url='redis://localhost:6379/15', max_connections=5, default_ttl=3600, circuit_breaker_threshold=3, health_check_interval=10.0)

@pytest.fixture
async def cache_client_async(cache_config):
    """Test cache client."""
    client = HiveCacheClient(cache_config)
    await client.initialize()
    yield client
    await client.close()

@pytest.mark.core
@pytest.mark.asyncio
async def test_cache_client_initialization_async(cache_config):
    """Test cache client initialization."""
    client = HiveCacheClient(cache_config)
    await client.initialize()
    assert client._redis_pool is not None
    assert client._circuit_breaker is not None
    await client.close()

@pytest.mark.core
@pytest.mark.asyncio
async def test_set_and_get_async(cache_client_async):
    """Test basic set and get operations."""
    key = ('test_key',)
    value = {'data': 'test_value', 'number': 42}
    success = await cache_client_async.set(key, value, ttl=60)
    assert success is True
    retrieved = await cache_client_async.get(key)
    assert retrieved == value
    await cache_client_async.delete(key)

@pytest.mark.core
@pytest.mark.asyncio
async def test_get_nonexistent_key_async(cache_client_async):
    """Test getting non-existent key."""
    result = await cache_client_async.get('nonexistent_key', default='default_value')
    assert result == 'default_value'

@pytest.mark.core
@pytest.mark.asyncio
async def test_delete_async(cache_client_async):
    """Test delete operation."""
    key = ('delete_test',)
    value = 'test_value'
    await cache_client_async.set(key, value)
    assert await cache_client_async.get(key) == value
    success = await cache_client_async.delete(key)
    assert success is True
    assert await cache_client_async.get(key) is None

@pytest.mark.core
@pytest.mark.asyncio
async def test_exists_async(cache_client_async):
    """Test exists operation."""
    key = ('exists_test',)
    value = 'test_value'
    assert await cache_client_async.exists(key) is False
    await cache_client_async.set(key, value)
    assert await cache_client_async.exists(key) is True
    await cache_client_async.delete(key)

@pytest.mark.core
@pytest.mark.asyncio
async def test_ttl_operations_async(cache_client_async):
    """Test TTL-related operations."""
    key = ('ttl_test',)
    value = 'test_value'
    await cache_client_async.set(key, value, ttl=60)
    ttl = await cache_client_async.ttl(key)
    assert 50 <= ttl <= 60
    success = await cache_client_async.extend_ttl(key, 120)
    assert success is True
    new_ttl = await cache_client_async.ttl(key)
    assert 110 <= new_ttl <= 120
    await cache_client_async.delete(key)

@pytest.mark.core
@pytest.mark.asyncio
async def test_pattern_operations_async(cache_client_async):
    """Test pattern-based operations."""
    keys = ['pattern_test_1', 'pattern_test_2', 'pattern_test_3']
    for key in keys:
        await cache_client_async.set(key, f'value_{key}')
    deleted_count = await cache_client_async.delete_pattern('pattern_test_*')
    assert deleted_count == len(keys)
    for key in keys:
        assert await cache_client_async.exists(key) is False

@pytest.mark.core
@pytest.mark.asyncio
async def test_get_or_set_async(cache_client_async):
    """Test get_or_set operation."""
    key = 'get_or_set_test'

    def factory():
        return {'computed': True, 'timestamp': time.time()}
    value1 = await cache_client_async.get_or_set(key, factory, ttl=60)
    assert value1['computed'] is True
    value2 = await cache_client_async.get_or_set(key, factory, ttl=60)
    assert value2 == value1
    await cache_client_async.delete(key)

@pytest.mark.core
@pytest.mark.asyncio
async def test_mget_mset_async(cache_client_async):
    """Test multiple get/set operations."""
    data = {'key1': 'value1', 'key2': {'nested': 'value2'}, 'key3': [1, 2, 3]}
    success = await cache_client_async.mset(data, ttl=60)
    assert success is True
    retrieved = await cache_client_async.mget(list(data.keys()))
    assert retrieved == data
    for key in data.keys():
        await cache_client_async.delete(key)

@pytest.mark.core
@pytest.mark.asyncio
async def test_scan_keys_async(cache_client_async):
    """Test key scanning."""
    test_keys = [f'scan_test_{i}' for i in range(5)]
    for key in test_keys:
        await cache_client_async.set(key, f'value_{key}')
    found_keys = []
    async for key in cache_client_async.scan_keys('scan_test_*'):
        found_keys.append(key)
    assert len(found_keys) == len(test_keys)
    assert all((key in test_keys for key in found_keys))
    await cache_client_async.delete_pattern('scan_test_*')

@pytest.mark.core
@pytest.mark.asyncio
async def test_namespaces_async(cache_client_async):
    """Test namespace functionality."""
    key = ('namespace_test',)
    value1 = ('value_in_namespace1',)
    value2 = 'value_in_namespace2'
    await cache_client_async.set(key, value1, namespace='ns1')
    await cache_client_async.set(key, value2, namespace='ns2')
    assert await cache_client_async.get(key, namespace='ns1') == value1
    assert await cache_client_async.get(key, namespace='ns2') == value2
    await cache_client_async.delete(key, namespace='ns1')
    await cache_client_async.delete(key, namespace='ns2')

@pytest.mark.core
@pytest.mark.asyncio
async def test_serialization_formats_async(cache_config):
    """Test different serialization formats."""
    formats = ['msgpack', 'json']
    for fmt in formats:
        config = (cache_config.copy(update={'serialization_format': fmt}),)
        client = HiveCacheClient(config)
        await client.initialize()
        try:
            test_data = {'string': 'test', 'number': 42, 'float': 3.14, 'list': [1, 2, 3], 'nested': {'key': 'value'}}
            await client.set('serialization_test', test_data)
            retrieved = await client.get('serialization_test')
            assert retrieved == test_data
        finally:
            await client.close()

@pytest.mark.core
@pytest.mark.asyncio
async def test_compression_async(cache_client_async):
    """Test compression functionality."""
    large_data = {'data': 'x' * 2000}
    await cache_client_async.set('compression_test', large_data)
    retrieved = await cache_client_async.get('compression_test')
    assert retrieved == large_data
    await cache_client_async.delete('compression_test')

@pytest.mark.core
@pytest.mark.asyncio
async def test_health_check_async(cache_client_async):
    """Test health check functionality."""
    health = await cache_client_async.health_check()
    assert isinstance(health, dict)
    assert 'healthy' in health
    assert 'last_check' in health
    assert 'response_time_ms' in health

@pytest.mark.core
def test_metrics(cache_client_async):
    """Test metrics collection."""
    metrics = cache_client_async.get_metrics()
    assert isinstance(metrics, dict)
    assert 'hits' in metrics
    assert 'misses' in metrics
    assert 'sets' in metrics
    assert 'deletes' in metrics
    assert 'hit_rate_percent' in metrics

@pytest.mark.core
@pytest.mark.asyncio
async def test_circuit_breaker_functionality_async():
    """Test circuit breaker behavior."""
    config = CacheConfig(redis_url='redis://invalid:6379/0', circuit_breaker_threshold=2, circuit_breaker_timeout=60.0)
    client = HiveCacheClient(config)
    with pytest.raises(CacheConnectionError):
        await client.initialize()

@pytest.mark.core
@pytest.mark.asyncio
async def test_ttl_clamping_async(cache_client_async):
    """Test TTL clamping to configured limits."""
    key = ('ttl_clamp_test',)
    value = 'test_value'
    await cache_client_async.set(key, value, ttl=999999)
    ttl = await cache_client_async.ttl(key)
    assert ttl <= cache_client_async.config.max_ttl
    await cache_client_async.delete(key)

@pytest.mark.core
@pytest.mark.asyncio
async def test_key_generation_async(cache_client_async):
    """Test cache key generation and namespacing."""
    config = cache_client_async.config
    key = config.get_namespaced_key('test_ns', 'test_key')
    assert key.startswith(config.key_prefix)
    assert 'test_ns' in key
    assert 'test_key' in key
    long_key = ('x' * 300,)
    hashed_key = config.get_namespaced_key('test_ns', long_key)
    assert len(hashed_key) <= config.max_key_length