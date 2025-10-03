"""
Cache latency micro-benchmark to identify performance bottlenecks.

This benchmark isolates different components of cache operations to identify
the root cause of the 20ms P95 latency issue.
"""

import asyncio
import json
import statistics
import time
from dataclasses import dataclass

import aioredis
import msgpack

from hive_cache import CacheConfig, HiveCacheClient

try:
    import orjson

    HAS_ORJSON = True
except ImportError:
    HAS_ORJSON = False


@dataclass
class BenchmarkResult:
    """Container for benchmark results."""

    name: str
    mean_ms: float
    p95_ms: float
    p99_ms: float
    min_ms: float
    max_ms: float
    operations: int
    duration_seconds: float


async def benchmark_operation(operation_func, iterations: int = 1000) -> BenchmarkResult:
    """Benchmark an async operation."""
    operation_name = operation_func.__name__
    latencies = []

    # Warmup
    for _ in range(10):
        try:
            await operation_func()
        except Exception:
            pass

    # Actual benchmark
    start_time = time.time()

    for _ in range(iterations):
        op_start = time.perf_counter()
        try:
            await operation_func()
        except Exception as e:
            print(f"Operation {operation_name} failed: {e}")
            continue
        op_end = time.perf_counter()
        latencies.append((op_end - op_start) * 1000)  # Convert to milliseconds

    end_time = time.time()

    if not latencies:
        return BenchmarkResult(operation_name, 0, 0, 0, 0, 0, 0, 0)

    latencies.sort()

    return BenchmarkResult(
        name=operation_name,
        mean_ms=statistics.mean(latencies),
        p95_ms=latencies[int(len(latencies) * 0.95)],
        p99_ms=latencies[int(len(latencies) * 0.99)],
        min_ms=min(latencies),
        max_ms=max(latencies),
        operations=len(latencies),
        duration_seconds=end_time - start_time,
    )


class CacheLatencyBenchmark:
    """Comprehensive cache latency benchmark suite."""

    def __init__(self):
        self.test_data = {
            "small": {"key": "value", "number": 42},
            "medium": {"data": "x" * 1000, "items": list(range(100))},
            "large": {"payload": "x" * 10000, "array": list(range(1000))},
        }

    async def benchmark_direct_redis(self) -> list[BenchmarkResult]:
        """Benchmark direct aioredis operations."""
        results = []

        # Direct Redis connection
        redis = aioredis.from_url("redis://localhost:6379/15")

        try:
            # Test ping latency
            async def ping_operation():
                await redis.ping()

            results.append(await benchmark_operation(ping_operation))

            # Test set/get with different data sizes
            for size_name, data in self.test_data.items():
                serialized_data = msgpack.packb(data)

                async def set_operation(name=size_name, ser_data=serialized_data):
                    await redis.set(f"bench_{name}", ser_data, ex=60)

                async def get_operation(name=size_name):
                    result = await redis.get(f"bench_{name}")
                    if result:
                        msgpack.unpackb(result)

                # Set operation
                set_result = await benchmark_operation(set_operation)
                set_result.name = f"direct_redis_set_{size_name}"
                results.append(set_result)

                # Get operation
                get_result = await benchmark_operation(get_operation)
                get_result.name = f"direct_redis_get_{size_name}"
                results.append(get_result)

        finally:
            await redis.close()

        return results

    async def benchmark_serialization(self) -> list[BenchmarkResult]:
        """Benchmark different serialization methods."""
        results = []

        for size_name, data in self.test_data.items():
            # JSON serialization
            async def json_serialize(d=data):
                json.dumps(d)

            async def json_deserialize(d=data):
                serialized = json.dumps(d)
                json.loads(serialized)

            # msgpack serialization
            async def msgpack_serialize(d=data):
                msgpack.packb(d)

            async def msgpack_deserialize(d=data):
                serialized = msgpack.packb(d)
                msgpack.unpackb(serialized)

            # Benchmark each method
            for operation in [json_serialize, json_deserialize, msgpack_serialize, msgpack_deserialize]:
                result = await benchmark_operation(operation)
                result.name = f"{operation.__name__}_{size_name}"
                results.append(result)

            # orjson if available
            if HAS_ORJSON:

                async def orjson_serialize(d=data):
                    orjson.dumps(d)

                async def orjson_deserialize(d=data):
                    serialized = orjson.dumps(d)
                    orjson.loads(serialized)

                for operation in [orjson_serialize, orjson_deserialize]:
                    result = await benchmark_operation(operation)
                    result.name = f"{operation.__name__}_{size_name}"
                    results.append(result)

        return results

    async def benchmark_connection_pool_overhead(self) -> list[BenchmarkResult]:
        """Benchmark connection pool vs direct connection overhead."""
        results = []

        # Connection pool approach (current implementation style)
        pool = aioredis.ConnectionPool.from_url("redis://localhost:6379/15", max_connections=20)

        async def pool_get_operation():
            async with aioredis.Redis(connection_pool=pool) as redis:
                await redis.get("test_key")

        # Direct connection approach
        redis_direct = aioredis.from_url("redis://localhost:6379/15")

        async def direct_get_operation():
            await redis_direct.get("test_key")

        try:
            # Setup test data
            async with aioredis.Redis(connection_pool=pool) as redis:
                await redis.set("test_key", "test_value", ex=60)

            # Benchmark pool approach
            pool_result = await benchmark_operation(pool_get_operation)
            pool_result.name = "connection_pool_overhead"
            results.append(pool_result)

            # Benchmark direct approach
            direct_result = await benchmark_operation(direct_get_operation)
            direct_result.name = "direct_connection"
            results.append(direct_result)

        finally:
            await pool.disconnect()
            await redis_direct.close()

        return results

    async def benchmark_hive_cache_client(self) -> list[BenchmarkResult]:
        """Benchmark the current HiveCacheClient implementation."""
        results = []

        config = CacheConfig(
            redis_url="redis://localhost:6379/15",
            max_connections=20,
            response_timeout=0.1,  # Reduce from 5s to 100ms
            circuit_breaker_enabled=False,  # Disable for pure performance test
        )

        client = HiveCacheClient(config)

        try:
            await client.initialize_async()

            # Test different data sizes
            for size_name, data in self.test_data.items():

                async def set_operation(name=size_name, d=data):
                    await client.set_async(f"hive_bench_{name}", d, ttl_async=60)

                async def get_operation(name=size_name):
                    await client.get_async(f"hive_bench_{name}")

                # Set operation
                set_result = await benchmark_operation(set_operation)
                set_result.name = f"hive_cache_set_{size_name}"
                results.append(set_result)

                # Get operation
                get_result = await benchmark_operation(get_operation)
                get_result.name = f"hive_cache_get_{size_name}"
                results.append(get_result)

        except Exception as e:
            print(f"HiveCacheClient benchmark failed: {e}")
            # Create mock results to show the problem
            for size_name in self.test_data.keys():
                for op in ["set", "get"]:
                    results.append(
                        BenchmarkResult(
                            name=f"hive_cache_{op}_{size_name}_FAILED",
                            mean_ms=0,
                            p95_ms=0,
                            p99_ms=0,
                            min_ms=0,
                            max_ms=0,
                            operations=0,
                            duration_seconds=0,
                        ),
                    )

        finally:
            try:
                await client.close_async()
            except Exception:
                pass

        return results

    async def run_all_benchmarks(self) -> dict[str, list[BenchmarkResult]]:
        """Run all benchmark suites."""
        print("Starting cache latency benchmark suite...")

        benchmarks = {
            "direct_redis": self.benchmark_direct_redis,
            "serialization": self.benchmark_serialization,
            "connection_overhead": self.benchmark_connection_pool_overhead,
            "hive_cache": self.benchmark_hive_cache_client,
        }

        results = {}

        for name, benchmark_func in benchmarks.items():
            print(f"\nRunning {name} benchmark...")
            try:
                results[name] = await benchmark_func()
                print(f"  ✅ {name} completed ({len(results[name])} tests)")
            except Exception as e:
                print(f"  ❌ {name} failed: {e}")
                results[name] = []

        return results

    def print_results(self, all_results: dict[str, list[BenchmarkResult]]):
        """Print formatted benchmark results."""
        print("\n" + "=" * 80)
        print("CACHE LATENCY BENCHMARK RESULTS")
        print("=" * 80)

        # Print summary table
        print(f"\n{'Operation':<40} {'Mean':<8} {'P95':<8} {'P99':<8} {'Status':<10}")
        print("-" * 80)

        critical_issues = []

        for category, results in all_results.items():
            if not results:
                continue

            print(f"\n{category.upper()}:")
            for result in results:
                status = "✅ GOOD" if result.p95_ms < 5.0 else "⚠️ SLOW" if result.p95_ms < 15.0 else "❌ CRITICAL"

                if result.p95_ms > 10.0:
                    critical_issues.append(f"{result.name}: {result.p95_ms:.2f}ms P95")

                print(
                    f"  {result.name:<38} {result.mean_ms:>6.2f}ms {result.p95_ms:>6.2f}ms {result.p99_ms:>6.2f}ms {status}",
                )

        # Analysis section
        print("\n" + "=" * 80)
        print("PERFORMANCE ANALYSIS")
        print("=" * 80)

        if critical_issues:
            print("\n🚨 CRITICAL PERFORMANCE ISSUES:")
            for issue in critical_issues:
                print(f"  • {issue}")

        # Find fastest operations for comparison
        all_results_flat = [r for results in all_results.values() for r in results if r.operations > 0]
        if all_results_flat:
            fastest = min(all_results_flat, key=lambda x: x.p95_ms)
            slowest = max(all_results_flat, key=lambda x: x.p95_ms)

            print("\n📊 PERFORMANCE COMPARISON:")
            print(f"  Fastest operation: {fastest.name} ({fastest.p95_ms:.2f}ms P95)")
            print(f"  Slowest operation: {slowest.name} ({slowest.p95_ms:.2f}ms P95)")
            print(f"  Performance gap: {slowest.p95_ms / fastest.p95_ms:.1f}x slower")

        print("\n🎯 TARGET: < 1ms P95 latency for local Redis operations")
        print("📋 CURRENT ISSUE: ~20ms P95 latency in V4.2 certification")


async def main():
    """Run the cache latency benchmark."""
    benchmark = CacheLatencyBenchmark()
    results = await benchmark.run_all_benchmarks()
    benchmark.print_results(results)


if __name__ == "__main__":
    asyncio.run(main())
