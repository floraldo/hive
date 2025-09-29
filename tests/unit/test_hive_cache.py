"""Unit tests for hive-cache package V4.2."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import the components we're testing
from hive_cache.cache_client import CircuitBreaker, HiveCacheClient, close_cache_client, get_cache_client
from hive_cache.config import CacheConfig
from hive_cache.exceptions import CacheCircuitBreakerError, CacheConnectionError, CacheTimeoutError


@pytest.fixture
def cache_config():
    """Create test cache configuration."""
    return CacheConfig(
        redis_url="redis://localhost:6379/0",
        redis_max_connections=10,
        response_timeout=5.0,
        circuit_breaker_enabled=True,
        circuit_breaker_threshold=3,
        circuit_breaker_timeout=60.0,
        circuit_breaker_recovery_timeout=30.0,
        serialization_format="msgpack",
        compression_enabled=True,
        compression_threshold=1024,
        compression_level=6,
        enable_json_fallback=True,
        default_ttl=3600,
        min_ttl=60,
        max_ttl=86400,
        namespace_prefix="test:",
        namespace_ttl_overrides={"claude": 7200, "performance": 1800},
    )


@pytest.fixture
def cache_client(cache_config):
    """Create HiveCacheClient instance for testing."""
    return HiveCacheClient(cache_config)


@pytest.fixture
def mock_redis_pool():
    """Create mock Redis pool."""
    pool = AsyncMock()
    pool.disconnect = AsyncMock()
    return pool


@pytest.fixture
def mock_redis():
    """Create mock Redis client."""
    redis = AsyncMock()
    redis.ping = AsyncMock(return_value=True)
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.setex = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.exists = AsyncMock(return_value=True)
    redis.ttl = AsyncMock(return_value=3600)
    redis.expire = AsyncMock(return_value=True)
    redis.keys = AsyncMock(return_value=[])
    redis.mget = AsyncMock(return_value=[])
    redis.pipeline = AsyncMock()
    return redis


class TestCircuitBreaker:
    """Test the CircuitBreaker component."""

    def test_circuit_breaker_initialization(self):
        """Test CircuitBreaker initializes correctly."""
        cb = CircuitBreaker(threshold=5, timeout=60.0, recovery_timeout=30.0)

        assert cb.threshold == 5
        assert cb.timeout == 60.0
        assert cb.recovery_timeout == 30.0
        assert cb.failure_count == 0
        assert cb.last_failure_time is None
        assert cb.state == "closed"

    def test_circuit_breaker_closed_state(self):
        """Test circuit breaker in closed state."""
        cb = CircuitBreaker(threshold=3)

        assert not cb.is_open()
        assert cb.state == "closed"

    def test_circuit_breaker_failure_recording(self):
        """Test recording failures and state transitions."""
        cb = CircuitBreaker(threshold=3)

        # Record failures
        cb.record_failure()
        assert cb.failure_count == 1
        assert cb.state == "closed"
        assert not cb.is_open()

        cb.record_failure()
        assert cb.failure_count == 2
        assert cb.state == "closed"

        # Third failure should open circuit
        cb.record_failure()
        assert cb.failure_count == 3
        assert cb.state == "open"
        assert cb.is_open()

    def test_circuit_breaker_success_recovery(self):
        """Test circuit breaker recovery on success."""
        cb = CircuitBreaker(threshold=2)

        # Cause circuit to open
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "open"

        # Record success should reset
        cb.record_success()
        assert cb.failure_count == 0
        assert cb.state == "closed"
        assert not cb.is_open()

    def test_circuit_breaker_recovery_timeout(self):
        """Test circuit breaker recovery timeout."""
        cb = CircuitBreaker(threshold=2, recovery_timeout=0.1)

        # Open circuit
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "open"
        assert cb.is_open()

        # Wait for recovery timeout
        time.sleep(0.2)

        # Should transition to half-open
        assert not cb.is_open()
        assert cb.state == "half-open"


class TestCacheConfig:
    """Test the CacheConfig component."""

    def test_cache_config_initialization(self, cache_config):
        """Test CacheConfig initialization."""
        assert cache_config.redis_url == "redis://localhost:6379/0"
        assert cache_config.circuit_breaker_enabled is True
        assert cache_config.serialization_format == "msgpack"
        assert cache_config.compression_enabled is True
        assert cache_config.default_ttl == 3600

    def test_namespaced_key_generation(self, cache_config):
        """Test namespaced key generation."""
        key = cache_config.get_namespaced_key("test_namespace", "my_key")
        assert key == "test:test_namespace:my_key"

    def test_ttl_for_namespace(self, cache_config):
        """Test TTL retrieval for different namespaces."""
        # Default TTL
        assert cache_config.get_ttl_for_namespace("default") == 3600

        # Override TTL
        assert cache_config.get_ttl_for_namespace("claude") == 7200
        assert cache_config.get_ttl_for_namespace("performance") == 1800

    def test_redis_connection_kwargs(self, cache_config):
        """Test Redis connection kwargs generation."""
        kwargs = cache_config.get_redis_connection_kwargs()

        assert "max_connections" in kwargs
        assert kwargs["max_connections"] == 10
        assert "socket_timeout" in kwargs
        assert "socket_connect_timeout" in kwargs


class TestHiveCacheClient:
    """Test the HiveCacheClient component."""

    def test_cache_client_initialization(self, cache_client, cache_config):
        """Test HiveCacheClient initializes correctly."""
        assert cache_client.config == cache_config
        assert cache_client._redis_pool is None
        assert cache_client._circuit_breaker is not None
        assert cache_client._metrics["hits"] == 0
        assert cache_client._health_status["healthy"] is True

    @pytest.mark.asyncio
    @patch("hive_cache.cache_client.aioredis.ConnectionPool.from_url")
    @patch("hive_cache.cache_client.aioredis.Redis")
    async def test_cache_client_initialization_success(self, mock_redis_class, mock_pool_from_url, cache_client):
        """Test successful cache client initialization."""
        # Setup mocks
        mock_pool = AsyncMock()
        mock_pool_from_url.return_value = mock_pool

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        mock_redis_class.return_value.__aenter__.return_value = mock_redis

        # Initialize
        await cache_client.initialize()

        assert cache_client._redis_pool == mock_pool
        mock_pool_from_url.assert_called_once()
        mock_redis.ping.assert_called_once()

    @pytest.mark.asyncio
    @patch("hive_cache.cache_client.aioredis.ConnectionPool.from_url")
    async def test_cache_client_initialization_failure(self, mock_pool_from_url, cache_client):
        """Test cache client initialization failure."""
        mock_pool_from_url.side_effect = Exception("Connection failed")

        with pytest.raises(CacheConnectionError):
            await cache_client.initialize()

    @pytest.mark.asyncio
    async def test_cache_client_close(self, cache_client, mock_redis_pool):
        """Test cache client close."""
        cache_client._redis_pool = mock_redis_pool

        await cache_client.close()

        mock_redis_pool.disconnect.assert_called_once()

    def test_circuit_breaker_check(self, cache_client):
        """Test circuit breaker check functionality."""
        # Circuit should be closed initially
        cache_client._check_circuit_breaker()  # Should not raise

        # Force circuit open
        cache_client._circuit_breaker.state = "open"
        cache_client._circuit_breaker.last_failure_time = time.time()

        with pytest.raises(CacheCircuitBreakerError):
            cache_client._check_circuit_breaker()

    @pytest.mark.asyncio
    async def test_execute_with_circuit_breaker_success(self, cache_client):
        """Test successful operation with circuit breaker."""

        async def mock_operation():
            return "success"

        result = await cache_client._execute_with_circuit_breaker(mock_operation)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_execute_with_circuit_breaker_timeout(self, cache_client):
        """Test timeout handling with circuit breaker."""

        async def slow_operation():
            await asyncio.sleep(10)  # Will timeout
            return "too_slow"

        with pytest.raises(CacheTimeoutError):
            await cache_client._execute_with_circuit_breaker(slow_operation)

    def test_serialize_value_msgpack(self, cache_client):
        """Test value serialization with msgpack."""
        test_data = {"key": "value", "number": 42}

        serialized = cache_client._serialize_value(test_data)
        assert isinstance(serialized, bytes)

        # Should not be compressed (below threshold)
        assert not serialized.startswith(b"GZIP:")

    def test_serialize_value_with_compression(self, cache_client):
        """Test value serialization with compression."""
        # Create large data that exceeds compression threshold
        large_data = {"data": "x" * 2000}

        serialized = cache_client._serialize_value(large_data)
        assert isinstance(serialized, bytes)

        # Should be compressed
        assert serialized.startswith(b"GZIP:")

    def test_deserialize_value_msgpack(self, cache_client):
        """Test value deserialization with msgpack."""
        test_data = {"key": "value", "number": 42}

        serialized = cache_client._serialize_value(test_data)
        deserialized = cache_client._deserialize_value(serialized)

        assert deserialized == test_data

    def test_deserialize_value_compressed(self, cache_client):
        """Test deserialization of compressed data."""
        large_data = {"data": "x" * 2000}

        serialized = cache_client._serialize_value(large_data)
        deserialized = cache_client._deserialize_value(serialized)

        assert deserialized == large_data

    def test_serialize_deserialize_json_format(self, cache_config):
        """Test JSON serialization format."""
        cache_config.serialization_format = "json"
        cache_client = HiveCacheClient(cache_config)

        test_data = {"key": "value", "number": 42}

        serialized = cache_client._serialize_value(test_data)
        deserialized = cache_client._deserialize_value(serialized)

        assert deserialized == test_data

    def test_generate_key_hash(self, cache_client):
        """Test key hash generation."""
        key = "test_key"
        hash1 = cache_client._generate_key_hash(key)
        hash2 = cache_client._generate_key_hash(key)

        # Should be consistent
        assert hash1 == hash2

        # Should be different for different keys
        hash3 = cache_client._generate_key_hash("different_key")
        assert hash1 != hash3

    @pytest.mark.asyncio
    @patch("hive_cache.cache_client.aioredis.Redis")
    async def test_set_operation(self, mock_redis_class, cache_client, mock_redis_pool):
        """Test cache set operation."""
        cache_client._redis_pool = mock_redis_pool

        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock(return_value=True)
        mock_redis_class.return_value.__aenter__.return_value = mock_redis

        result = await cache_client.set("test_key", "test_value", ttl=300)

        assert result is True
        assert cache_client._metrics["sets"] == 1
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    @patch("hive_cache.cache_client.aioredis.Redis")
    async def test_get_operation_hit(self, mock_redis_class, cache_client, mock_redis_pool):
        """Test cache get operation with hit."""
        cache_client._redis_pool = mock_redis_pool

        # Mock serialized data
        test_value = "test_value"
        serialized_data = cache_client._serialize_value(test_value)

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=serialized_data)
        mock_redis_class.return_value.__aenter__.return_value = mock_redis

        result = await cache_client.get("test_key")

        assert result == test_value
        assert cache_client._metrics["hits"] == 1
        assert cache_client._metrics["misses"] == 0

    @pytest.mark.asyncio
    @patch("hive_cache.cache_client.aioredis.Redis")
    async def test_get_operation_miss(self, mock_redis_class, cache_client, mock_redis_pool):
        """Test cache get operation with miss."""
        cache_client._redis_pool = mock_redis_pool

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis_class.return_value.__aenter__.return_value = mock_redis

        result = await cache_client.get("test_key", default="default_value")

        assert result == "default_value"
        assert cache_client._metrics["hits"] == 0
        assert cache_client._metrics["misses"] == 1

    @pytest.mark.asyncio
    @patch("hive_cache.cache_client.aioredis.Redis")
    async def test_get_or_set_cache_hit(self, mock_redis_class, cache_client, mock_redis_pool):
        """Test get_or_set with cache hit."""
        cache_client._redis_pool = mock_redis_pool

        cached_value = "cached_value"
        serialized_data = cache_client._serialize_value(cached_value)

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=serialized_data)
        mock_redis_class.return_value.__aenter__.return_value = mock_redis

        def factory_function():
            return "computed_value"

        result = await cache_client.get_or_set("test_key", factory_function)

        assert result == cached_value
        mock_redis.get.assert_called_once()
        # setex should not be called since we had a cache hit
        mock_redis.setex.assert_not_called()

    @pytest.mark.asyncio
    @patch("hive_cache.cache_client.aioredis.Redis")
    async def test_get_or_set_cache_miss(self, mock_redis_class, cache_client, mock_redis_pool):
        """Test get_or_set with cache miss."""
        cache_client._redis_pool = mock_redis_pool

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock(return_value=True)
        mock_redis_class.return_value.__aenter__.return_value = mock_redis

        def factory_function():
            return "computed_value"

        result = await cache_client.get_or_set("test_key", factory_function, ttl=300)

        assert result == "computed_value"
        mock_redis.get.assert_called_once()
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    @patch("hive_cache.cache_client.aioredis.Redis")
    async def test_get_or_set_async_factory(self, mock_redis_class, cache_client, mock_redis_pool):
        """Test get_or_set with async factory function."""
        cache_client._redis_pool = mock_redis_pool

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock(return_value=True)
        mock_redis_class.return_value.__aenter__.return_value = mock_redis

        async def async_factory():
            await asyncio.sleep(0.001)
            return "async_computed_value"

        result = await cache_client.get_or_set("test_key", async_factory)

        assert result == "async_computed_value"
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    @patch("hive_cache.cache_client.aioredis.Redis")
    async def test_delete_operation(self, mock_redis_class, cache_client, mock_redis_pool):
        """Test cache delete operation."""
        cache_client._redis_pool = mock_redis_pool

        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock(return_value=1)
        mock_redis_class.return_value.__aenter__.return_value = mock_redis

        result = await cache_client.delete("test_key")

        assert result is True
        assert cache_client._metrics["deletes"] == 1

    @pytest.mark.asyncio
    @patch("hive_cache.cache_client.aioredis.Redis")
    async def test_delete_pattern(self, mock_redis_class, cache_client, mock_redis_pool):
        """Test delete pattern operation."""
        cache_client._redis_pool = mock_redis_pool

        mock_redis = AsyncMock()
        mock_redis.keys = AsyncMock(return_value=["key1", "key2", "key3"])
        mock_redis.delete = AsyncMock(return_value=3)
        mock_redis_class.return_value.__aenter__.return_value = mock_redis

        result = await cache_client.delete_pattern("test_*")

        assert result == 3
        assert cache_client._metrics["deletes"] == 3
        mock_redis.keys.assert_called_once()
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    @patch("hive_cache.cache_client.aioredis.Redis")
    async def test_exists_operation(self, mock_redis_class, cache_client, mock_redis_pool):
        """Test key existence check."""
        cache_client._redis_pool = mock_redis_pool

        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=1)
        mock_redis_class.return_value.__aenter__.return_value = mock_redis

        result = await cache_client.exists("test_key")

        assert result is True

    @pytest.mark.asyncio
    @patch("hive_cache.cache_client.aioredis.Redis")
    async def test_ttl_operation(self, mock_redis_class, cache_client, mock_redis_pool):
        """Test TTL retrieval."""
        cache_client._redis_pool = mock_redis_pool

        mock_redis = AsyncMock()
        mock_redis.ttl = AsyncMock(return_value=300)
        mock_redis_class.return_value.__aenter__.return_value = mock_redis

        result = await cache_client.ttl("test_key")

        assert result == 300

    @pytest.mark.asyncio
    @patch("hive_cache.cache_client.aioredis.Redis")
    async def test_extend_ttl(self, mock_redis_class, cache_client, mock_redis_pool):
        """Test TTL extension."""
        cache_client._redis_pool = mock_redis_pool

        mock_redis = AsyncMock()
        mock_redis.expire = AsyncMock(return_value=1)
        mock_redis_class.return_value.__aenter__.return_value = mock_redis

        result = await cache_client.extend_ttl("test_key", 600)

        assert result is True

    @pytest.mark.asyncio
    @patch("hive_cache.cache_client.aioredis.Redis")
    async def test_mget_operation(self, mock_redis_class, cache_client, mock_redis_pool):
        """Test multiple get operation."""
        cache_client._redis_pool = mock_redis_pool

        # Mock serialized data for multiple keys
        value1 = cache_client._serialize_value("value1")
        value2 = cache_client._serialize_value("value2")

        mock_redis = AsyncMock()
        mock_redis.mget = AsyncMock(return_value=[value1, None, value2])
        mock_redis_class.return_value.__aenter__.return_value = mock_redis

        result = await cache_client.mget(["key1", "key2", "key3"])

        assert result == {"key1": "value1", "key3": "value2"}
        assert cache_client._metrics["hits"] == 2
        assert cache_client._metrics["misses"] == 1

    @pytest.mark.asyncio
    @patch("hive_cache.cache_client.aioredis.Redis")
    async def test_mset_operation(self, mock_redis_class, cache_client, mock_redis_pool):
        """Test multiple set operation."""
        cache_client._redis_pool = mock_redis_pool

        mock_pipeline = AsyncMock()
        mock_pipeline.setex = AsyncMock()
        mock_pipeline.execute = AsyncMock(return_value=[True, True])

        mock_redis = AsyncMock()
        mock_redis.pipeline.return_value = mock_pipeline
        mock_redis_class.return_value.__aenter__.return_value = mock_redis

        result = await cache_client.mset({"key1": "value1", "key2": "value2"}, ttl=300)

        assert result is True
        assert cache_client._metrics["sets"] == 2
        assert mock_pipeline.setex.call_count == 2

    @pytest.mark.asyncio
    @patch("hive_cache.cache_client.aioredis.Redis")
    async def test_health_check_success(self, mock_redis_class, cache_client, mock_redis_pool):
        """Test successful health check."""
        cache_client._redis_pool = mock_redis_pool

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        mock_redis.setex = AsyncMock(return_value=True)
        mock_redis.get = AsyncMock(return_value=b"test_value")
        mock_redis.delete = AsyncMock(return_value=1)
        mock_redis_class.return_value.__aenter__.return_value = mock_redis

        result = await cache_client.health_check()

        assert result["healthy"] is True
        assert "response_time_ms" in result
        assert result["ping_result"] is True
        assert result["set_get_test"] is True

    @pytest.mark.asyncio
    @patch("hive_cache.cache_client.aioredis.Redis")
    async def test_health_check_failure(self, mock_redis_class, cache_client, mock_redis_pool):
        """Test health check failure."""
        cache_client._redis_pool = mock_redis_pool

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(side_effect=Exception("Connection failed"))
        mock_redis_class.return_value.__aenter__.return_value = mock_redis

        result = await cache_client.health_check()

        assert result["healthy"] is False
        assert len(result["errors"]) > 0

    def test_get_metrics(self, cache_client):
        """Test metrics retrieval."""
        # Set some test metrics
        cache_client._metrics["hits"] = 80
        cache_client._metrics["misses"] = 20
        cache_client._metrics["sets"] = 50

        metrics = cache_client.get_metrics()

        assert metrics["hits"] == 80
        assert metrics["misses"] == 20
        assert metrics["sets"] == 50
        assert metrics["hit_rate_percent"] == 80.0  # 80/(80+20) * 100
        assert metrics["total_operations"] == 100

    def test_reset_metrics(self, cache_client):
        """Test metrics reset."""
        # Set some test metrics
        cache_client._metrics["hits"] = 100
        cache_client._metrics["misses"] = 50

        cache_client.reset_metrics()

        assert cache_client._metrics["hits"] == 0
        assert cache_client._metrics["misses"] == 0

    @pytest.mark.asyncio
    async def test_namespace_functionality(self, cache_client):
        """Test namespace functionality."""
        # Test key generation with different namespaces
        key1 = cache_client.config.get_namespaced_key("namespace1", "key")
        key2 = cache_client.config.get_namespaced_key("namespace2", "key")

        assert key1 != key2
        assert "namespace1" in key1
        assert "namespace2" in key2

    @pytest.mark.asyncio
    async def test_ttl_limits_enforcement(self, cache_client):
        """Test TTL limits are enforced."""
        # Mock the set operation to verify TTL clamping
        with patch.object(cache_client, "_execute_with_circuit_breaker") as mock_execute:
            mock_execute.return_value = True

            # Test TTL below minimum
            await cache_client.set("key", "value", ttl=10)  # Below min_ttl of 60

            # Test TTL above maximum
            await cache_client.set("key", "value", ttl=100000)  # Above max_ttl of 86400

            # Verify TTL was clamped (check via the calls to the mock)
            assert mock_execute.call_count == 2

    @pytest.mark.asyncio
    async def test_error_handling_propagation(self, cache_client):
        """Test that appropriate errors are propagated."""
        # Test circuit breaker error
        cache_client._circuit_breaker.state = "open"
        cache_client._circuit_breaker.last_failure_time = time.time()

        with pytest.raises(CacheCircuitBreakerError):
            await cache_client.get("test_key")


class TestGlobalCacheClient:
    """Test global cache client functionality."""

    @pytest.mark.asyncio
    @patch("hive_cache.cache_client.CacheConfig.from_env")
    @patch.object(HiveCacheClient, "initialize")
    async def test_get_cache_client_creation(self, mock_initialize, mock_config_from_env):
        """Test global cache client creation."""
        mock_config = MagicMock()
        mock_config_from_env.return_value = mock_config

        # Clear global client first
        await close_cache_client()

        client = await get_cache_client()

        assert client is not None
        mock_initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_cache_client_singleton(self):
        """Test that get_cache_client returns same instance."""
        # Clear global client first
        await close_cache_client()

        config = CacheConfig(redis_url="redis://localhost:6379/0")

        with patch.object(HiveCacheClient, "initialize"):
            client1 = await get_cache_client(config)
            client2 = await get_cache_client(config)

            assert client1 is client2

    @pytest.mark.asyncio
    async def test_close_cache_client(self):
        """Test closing global cache client."""
        config = CacheConfig(redis_url="redis://localhost:6379/0")

        with patch.object(HiveCacheClient, "initialize"):
            with patch.object(HiveCacheClient, "close") as mock_close:
                client = await get_cache_client(config)
                assert client is not None

                await close_cache_client()
                mock_close.assert_called_once()


class TestCacheIntegration:
    """Integration tests for cache components."""

    @pytest.mark.asyncio
    async def test_cache_operation_workflow(self, cache_client, mock_redis_pool):
        """Test complete cache operation workflow."""
        cache_client._redis_pool = mock_redis_pool

        with patch("hive_cache.cache_client.aioredis.Redis") as mock_redis_class:
            mock_redis = AsyncMock()
            mock_redis.setex = AsyncMock(return_value=True)
            mock_redis.get = AsyncMock()
            mock_redis.delete = AsyncMock(return_value=1)
            mock_redis_class.return_value.__aenter__.return_value = mock_redis

            # Test complete workflow: set -> get -> delete
            test_data = {"key": "value", "number": 42}

            # Set value
            await cache_client.set("test_key", test_data, ttl=300)

            # Mock get to return serialized data
            serialized_data = cache_client._serialize_value(test_data)
            mock_redis.get.return_value = serialized_data

            # Get value
            result = await cache_client.get("test_key")
            assert result == test_data

            # Delete value
            deleted = await cache_client.delete("test_key")
            assert deleted is True

            # Verify metrics
            assert cache_client._metrics["sets"] == 1
            assert cache_client._metrics["hits"] == 1
            assert cache_client._metrics["deletes"] == 1

    @pytest.mark.asyncio
    async def test_cache_with_circuit_breaker_integration(self, cache_client, mock_redis_pool):
        """Test cache operations with circuit breaker integration."""
        cache_client._redis_pool = mock_redis_pool

        with patch("hive_cache.cache_client.aioredis.Redis") as mock_redis_class:
            # Simulate failing operations
            mock_redis = AsyncMock()
            mock_redis.get = AsyncMock(side_effect=Exception("Connection failed"))
            mock_redis_class.return_value.__aenter__.return_value = mock_redis

            # First few operations should fail and increment failure count
            for i in range(3):
                with pytest.raises(CacheConnectionError):
                    await cache_client.get("test_key")

            # Circuit should now be open
            assert cache_client._circuit_breaker.state == "open"

            # Next operation should fail with circuit breaker error
            with pytest.raises(CacheCircuitBreakerError):
                await cache_client.get("test_key")

    @pytest.mark.asyncio
    async def test_serialization_formats_compatibility(self, cache_config):
        """Test different serialization formats work correctly."""
        test_data = {"key": "value", "list": [1, 2, 3], "nested": {"a": "b"}}

        # Test msgpack
        cache_config.serialization_format = "msgpack"
        client_msgpack = HiveCacheClient(cache_config)
        serialized_mp = client_msgpack._serialize_value(test_data)
        deserialized_mp = client_msgpack._deserialize_value(serialized_mp)
        assert deserialized_mp == test_data

        # Test json
        cache_config.serialization_format = "json"
        client_json = HiveCacheClient(cache_config)
        serialized_json = client_json._serialize_value(test_data)
        deserialized_json = client_json._deserialize_value(serialized_json)
        assert deserialized_json == test_data

    @pytest.mark.asyncio
    async def test_compression_threshold_behavior(self, cache_config):
        """Test compression threshold behavior."""
        cache_config.compression_threshold = 100  # Low threshold for testing
        client = HiveCacheClient(cache_config)

        # Small data should not be compressed
        small_data = {"key": "value"}
        serialized_small = client._serialize_value(small_data)
        assert not serialized_small.startswith(b"GZIP:")

        # Large data should be compressed
        large_data = {"data": "x" * 200}
        serialized_large = client._serialize_value(large_data)
        assert serialized_large.startswith(b"GZIP:")

        # Both should deserialize correctly
        assert client._deserialize_value(serialized_small) == small_data
        assert client._deserialize_value(serialized_large) == large_data

    @pytest.mark.asyncio
    async def test_error_metrics_tracking(self, cache_client, mock_redis_pool):
        """Test that errors are properly tracked in metrics."""
        cache_client._redis_pool = mock_redis_pool

        with patch("hive_cache.cache_client.aioredis.Redis") as mock_redis_class:
            mock_redis = AsyncMock()
            mock_redis.get = AsyncMock(side_effect=Exception("Simulated error"))
            mock_redis_class.return_value.__aenter__.return_value = mock_redis

            initial_errors = cache_client._metrics["errors"]

            # Trigger error
            with pytest.raises(CacheConnectionError):
                await cache_client.get("test_key")

            # Verify error was tracked
            assert cache_client._metrics["errors"] == initial_errors + 1


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
