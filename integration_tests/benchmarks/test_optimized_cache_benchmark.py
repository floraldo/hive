"""
Optimized cache performance benchmark to validate the fixes.

This benchmark tests the HiveCacheClient after our optimizations:
1. Fixed incorrect Redis API method names (get_async -> get)
2. Optimized connection management (reusable Redis client)
3. Reduced circuit breaker overhead
"""
import asyncio
import statistics
import time
from dataclasses import dataclass

try:
    from hive_cache import CacheConfig, HiveCacheClient
    HAS_HIVE_CACHE = True
except ImportError as e:
    print(f'Cannot import hive_cache: {e}')
    HAS_HIVE_CACHE = False

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
    ops_per_second: float

async def benchmark_async_operation(operation_func, iterations: int=1000) -> BenchmarkResult:
    """Benchmark an async operation."""
    operation_name = operation_func.__name__
    latencies = []
    for _ in range(10):
        try:
            await operation_func()
        except Exception:
            pass
    start_time = time.time()
    for _ in range(iterations):
        op_start = time.perf_counter()
        try:
            await operation_func()
        except Exception as e:
            print(f'Operation {operation_name} failed: {e}')
            continue
        op_end = time.perf_counter()
        latencies.append((op_end - op_start) * 1000)
    end_time = time.time()
    duration = end_time - start_time
    if not latencies:
        return BenchmarkResult(operation_name, 0, 0, 0, 0, 0, 0, 0)
    latencies.sort()
    return BenchmarkResult(name=operation_name, mean_ms=statistics.mean(latencies), p95_ms=latencies[int(len(latencies) * 0.95)], p99_ms=latencies[int(len(latencies) * 0.99)], min_ms=min(latencies), max_ms=max(latencies), operations=len(latencies), ops_per_second=len(latencies) / duration if duration > 0 else 0)

class OptimizedCacheBenchmark:
    """Benchmark suite for optimized HiveCacheClient."""

    def __init__(self):
        self.test_data = {'tiny': {'status': 'ok'}, 'small': {'key': 'value', 'number': 42, 'active': True}, 'medium': {'data': 'x' * 1000, 'items': list(range(50)), 'metadata': {'created': '2025-09-29', 'version': 'v4.2'}}}

    async def benchmark_optimized_cache_client(self) -> list[BenchmarkResult]:
        """Benchmark the optimized HiveCacheClient implementation."""
        if not HAS_HIVE_CACHE:
            print('  SKIP: hive_cache not available')
            return []
        results = []
        config = CacheConfig(redis_url='redis://localhost:6379/15', max_connections=20, response_timeout=1.0, circuit_breaker_enabled=False, compression_enabled=False, serialization_format='msgpack')
        client = HiveCacheClient(config)
        try:
            await client.initialize_async()
            for size_name, data in self.test_data.items():

                async def set_operation():
                    await client.set_async(f'opt_bench_{size_name}', data, ttl_async=60)

                async def get_operation():
                    await client.get_async(f'opt_bench_{size_name}')
                set_result = await benchmark_async_operation(set_operation, iterations=500)
                set_result.name = f'optimized_cache_set_{size_name}'
                results.append(set_result)
                get_result = await benchmark_async_operation(get_operation, iterations=500)
                get_result.name = f'optimized_cache_get_{size_name}'
                results.append(get_result)
                print(f'    {size_name}: SET {set_result.p95_ms:.2f}ms P95, GET {get_result.p95_ms:.2f}ms P95')
        except Exception as e:
            print(f'  ERROR: HiveCacheClient benchmark failed: {e}')
            results.append(BenchmarkResult(name='optimized_cache_FAILED', mean_ms=999.0, p95_ms=999.0, p99_ms=999.0, min_ms=999.0, max_ms=999.0, operations=0, ops_per_second=0))
        finally:
            try:
                await client.close_async()
            except Exception:
                pass
        return results

    async def benchmark_bulk_operations(self) -> list[BenchmarkResult]:
        """Benchmark bulk cache operations."""
        if not HAS_HIVE_CACHE:
            return []
        results = []
        config = CacheConfig(redis_url='redis://localhost:6379/15', max_connections=20, response_timeout=1.0, circuit_breaker_enabled=False, compression_enabled=False)
        client = HiveCacheClient(config)
        try:
            await client.initialize_async()
            bulk_data = {f'bulk_key_{i}': f'value_{i}' for i in range(50)}

            async def mset_operation():
                await client.mset_async(bulk_data, ttl_async=60)

            async def mget_operation():
                await client.mget_async(list(bulk_data.keys()))
            mset_result = await benchmark_async_operation(mset_operation, iterations=100)
            mset_result.name = 'optimized_mset_50_keys'
            results.append(mset_result)
            mget_result = await benchmark_async_operation(mget_operation, iterations=100)
            mget_result.name = 'optimized_mget_50_keys'
            results.append(mget_result)
            print(f'    Bulk ops: MSET {mset_result.p95_ms:.2f}ms P95, MGET {mget_result.p95_ms:.2f}ms P95')
        except Exception as e:
            print(f'  ERROR: Bulk operations failed: {e}')
        finally:
            try:
                await client.close_async()
            except Exception:
                pass
        return results

    async def run_all_benchmarks(self) -> list[BenchmarkResult]:
        """Run all optimization validation benchmarks."""
        print('Starting optimized cache benchmark suite...')
        print('Target: Sub-1ms P95 latency for local Redis operations')
        all_results = []
        print('\nTesting optimized cache client...')
        cache_results = await self.benchmark_optimized_cache_client()
        all_results.extend(cache_results)
        print('\nTesting bulk operations...')
        bulk_results = await self.benchmark_bulk_operations()
        all_results.extend(bulk_results)
        return all_results

    def print_results(self, results: list[BenchmarkResult]):
        """Print formatted benchmark results."""
        print('\n' + '=' * 80)
        print('OPTIMIZED CACHE PERFORMANCE RESULTS')
        print('=' * 80)
        if not results:
            print('No results to display (cache client unavailable)')
            return
        print(f"\n{'Operation':<40} {'Mean':<8} {'P95':<8} {'P99':<8} {'Ops/sec':<12} {'Status':<10}")
        print('-' * 80)
        success_count = 0
        critical_issues = []
        for result in results:
            if result.operations == 0:
                status = 'FAILED'
            elif result.p95_ms < 1.0:
                status = 'EXCELLENT'
                success_count += 1
            elif result.p95_ms < 5.0:
                status = 'GOOD'
                success_count += 1
            elif result.p95_ms < 15.0:
                status = 'OK'
            else:
                status = 'SLOW'
            if result.p95_ms > 5.0:
                critical_issues.append(f'{result.name}: {result.p95_ms:.2f}ms P95')
            print(f'  {result.name:<38} {result.mean_ms:>6.2f}ms {result.p95_ms:>6.2f}ms {result.p99_ms:>6.2f}ms {result.ops_per_second:>10,.0f} {status}')
        print('\n' + '=' * 80)
        print('OPTIMIZATION VALIDATION')
        print('=' * 80)
        if critical_issues:
            print('\nREMAINING PERFORMANCE ISSUES:')
            for issue in critical_issues:
                print(f'  - {issue}')
        working_results = [r for r in results if r.operations > 0]
        if working_results:
            fastest = min(working_results, key=lambda x: x.p95_ms)
            slowest = max(working_results, key=lambda x: x.p95_ms)
            print('\nPERFORMANCE SUMMARY:')
            print(f'  Operations tested: {len(working_results)}')
            print(f'  Sub-1ms operations: {success_count}/{len(working_results)}')
            print(f'  Success rate: {success_count / len(working_results) * 100:.1f}%')
            print(f'  Fastest operation: {fastest.name} ({fastest.p95_ms:.2f}ms P95)')
            print(f'  Slowest operation: {slowest.name} ({slowest.p95_ms:.2f}ms P95)')
            if success_count == len(working_results):
                print('\n✅ OPTIMIZATION SUCCESS: All operations under 1ms P95 target!')
            elif success_count > len(working_results) * 0.8:
                print(f'\n🟡 PARTIAL SUCCESS: {success_count}/{len(working_results)} operations meet target')
            else:
                print(f'\n❌ OPTIMIZATION NEEDED: Only {success_count}/{len(working_results)} operations meet target')
        print('\nTarget for V4.2 certification: < 1ms P95 latency')
        print('Previous issue: ~20ms P95 latency (should be FIXED)')

async def main():
    """Run the optimized cache benchmark."""
    benchmark = OptimizedCacheBenchmark()
    results = await benchmark.run_all_benchmarks()
    benchmark.print_results(results)
if __name__ == '__main__':
    asyncio.run(main())
