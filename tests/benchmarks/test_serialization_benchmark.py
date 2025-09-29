"""
Serialization performance benchmark to identify JSON vs msgpack vs orjson performance.

This benchmark focuses on the serialization component that could be causing
cache latency issues in the V4.2 performance certification.
"""

import json
import statistics
import time
from dataclasses import dataclass

import msgpack

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
    ops_per_second: float


def benchmark_sync_operation(operation_func, iterations: int = 10000) -> BenchmarkResult:
    """Benchmark a synchronous operation."""
    operation_name = operation_func.__name__
    latencies = []

    # Warmup
    for _ in range(100):
        try:
            operation_func()
        except Exception:
            pass

    # Actual benchmark
    start_time = time.time()

    for _ in range(iterations):
        op_start = time.perf_counter()
        try:
            operation_func()
        except Exception as e:
            print(f"Operation {operation_name} failed: {e}")
            continue
        op_end = time.perf_counter()
        latencies.append((op_end - op_start) * 1000)  # Convert to milliseconds

    end_time = time.time()
    duration = end_time - start_time

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
        ops_per_second=len(latencies) / duration if duration > 0 else 0,
    )


class SerializationBenchmark:
    """Comprehensive serialization benchmark suite."""

    def __init__(self):
        self.test_data = {
            "tiny": {"status": "ok"},
            "small": {"key": "value", "number": 42, "bool": True},
            "medium": {"data": "x" * 1000, "items": list(range(100)), "nested": {"key": "value", "array": [1, 2, 3]}},
            "large": {
                "payload": "x" * 10000,
                "array": list(range(1000)),
                "complex": {"users": [{"id": i, "name": f"user{i}", "active": i % 2 == 0} for i in range(100)]},
            },
        }

    def benchmark_serializers(self) -> list[BenchmarkResult]:
        """Benchmark different serialization libraries."""
        results = []

        for size_name, data in self.test_data.items():
            print(f"  Testing {size_name} data ({len(str(data))} chars)...")

            # JSON serialization
            def json_serialize():
                return json.dumps(data)

            def json_deserialize():
                serialized = json.dumps(data)
                return json.loads(serialized)

            # msgpack serialization
            def msgpack_serialize():
                return msgpack.packb(data, use_bin_type=True)

            def msgpack_deserialize():
                serialized = msgpack.packb(data, use_bin_type=True)
                return msgpack.unpackb(serialized, raw=False)

            # Benchmark each method
            for operation in [json_serialize, json_deserialize, msgpack_serialize, msgpack_deserialize]:
                result = benchmark_sync_operation(operation, iterations=5000)
                result.name = f"{operation.__name__}_{size_name}"
                results.append(result)

            # orjson if available
            if HAS_ORJSON:

                def orjson_serialize():
                    return orjson.dumps(data)

                def orjson_deserialize():
                    serialized = orjson.dumps(data)
                    return orjson.loads(serialized)

                for operation in [orjson_serialize, orjson_deserialize]:
                    result = benchmark_sync_operation(operation, iterations=5000)
                    result.name = f"{operation.__name__}_{size_name}"
                    results.append(result)

        return results

    def benchmark_cache_simulation(self) -> list[BenchmarkResult]:
        """Simulate complete cache operations (serialize + hypothetical network + deserialize)."""
        results = []

        for size_name, data in self.test_data.items():
            print(f"  Simulating cache operations for {size_name} data...")

            # Simulate complete cache SET operation
            def simulate_json_cache_set():
                # Serialize
                serialized = json.dumps(data)
                # Simulate network latency (Redis local should be ~0.1ms)
                time.sleep(0.0001)  # 0.1ms
                return len(serialized)

            def simulate_msgpack_cache_set():
                serialized = msgpack.packb(data, use_bin_type=True)
                time.sleep(0.0001)
                return len(serialized)

            def simulate_json_cache_get():
                serialized = json.dumps(data)
                time.sleep(0.0001)
                return json.loads(serialized)

            def simulate_msgpack_cache_get():
                serialized = msgpack.packb(data, use_bin_type=True)
                time.sleep(0.0001)
                return msgpack.unpackb(serialized, raw=False)

            for operation in [
                simulate_json_cache_set,
                simulate_msgpack_cache_set,
                simulate_json_cache_get,
                simulate_msgpack_cache_get,
            ]:
                result = benchmark_sync_operation(operation, iterations=1000)
                result.name = f"{operation.__name__}_{size_name}"
                results.append(result)

            if HAS_ORJSON:

                def simulate_orjson_cache_set():
                    serialized = orjson.dumps(data)
                    time.sleep(0.0001)
                    return len(serialized)

                def simulate_orjson_cache_get():
                    serialized = orjson.dumps(data)
                    time.sleep(0.0001)
                    return orjson.loads(serialized)

                for operation in [simulate_orjson_cache_set, simulate_orjson_cache_get]:
                    result = benchmark_sync_operation(operation, iterations=1000)
                    result.name = f"{operation.__name__}_{size_name}"
                    results.append(result)

        return results

    def run_all_benchmarks(self) -> dict[str, list[BenchmarkResult]]:
        """Run all serialization benchmarks."""
        print("Starting serialization performance benchmark...")

        benchmarks = {"serialization": self.benchmark_serializers, "cache_simulation": self.benchmark_cache_simulation}

        results = {}

        for name, benchmark_func in benchmarks.items():
            print(f"\nRunning {name} benchmark...")
            try:
                results[name] = benchmark_func()
                print(f"  OK {name} completed ({len(results[name])} tests)")
            except Exception as e:
                print(f"  FAIL {name} failed: {e}")
                results[name] = []

        return results

    def print_results(self, all_results: dict[str, list[BenchmarkResult]]):
        """Print formatted benchmark results."""
        print("\n" + "=" * 90)
        print("SERIALIZATION PERFORMANCE BENCHMARK RESULTS")
        print("=" * 90)

        # Print summary table
        print(f"\n{'Operation':<50} {'Mean':<8} {'P95':<8} {'P99':<8} {'Ops/sec':<12} {'Status':<10}")
        print("-" * 90)

        critical_issues = []
        recommendations = []

        for category, results in all_results.items():
            if not results:
                continue

            print(f"\n{category.upper()}:")

            # Group by data size for comparison
            size_groups = {}
            for result in results:
                parts = result.name.split("_")
                if len(parts) >= 2:
                    size = parts[-1]  # last part should be the size
                    if size not in size_groups:
                        size_groups[size] = []
                    size_groups[size].append(result)

            for size, size_results in size_groups.items():
                print(f"\n  {size.upper()} DATA:")
                for result in size_results:
                    status = (
                        "FAST"
                        if result.p95_ms < 0.1
                        else "OK"
                        if result.p95_ms < 1.0
                        else "SLOW"
                        if result.p95_ms < 5.0
                        else "CRITICAL"
                    )

                    if result.p95_ms > 1.0:
                        critical_issues.append(f"{result.name}: {result.p95_ms:.3f}ms P95")

                    print(
                        f"    {result.name:<46} {result.mean_ms:>6.3f}ms {result.p95_ms:>6.3f}ms {result.p99_ms:>6.3f}ms {result.ops_per_second:>10,.0f} {status}"
                    )

        # Analysis and recommendations
        print("\n" + "=" * 90)
        print("PERFORMANCE ANALYSIS & RECOMMENDATIONS")
        print("=" * 90)

        if critical_issues:
            print("\nSERIALIZATION BOTTLENECKS DETECTED:")
            for issue in critical_issues:
                print(f"  - {issue}")

        # Performance comparison
        all_results_flat = [r for results in all_results.values() for r in results if r.operations > 0]
        if all_results_flat:
            # Find fastest and slowest by operation type
            serialize_ops = [r for r in all_results_flat if "serialize" in r.name]
            deserialize_ops = [r for r in all_results_flat if "deserialize" in r.name]

            if serialize_ops:
                fastest_serialize = min(serialize_ops, key=lambda x: x.p95_ms)
                slowest_serialize = max(serialize_ops, key=lambda x: x.p95_ms)

                print("\nSERIALIZATION COMPARISON:")
                print(
                    f"  Fastest: {fastest_serialize.name} ({fastest_serialize.p95_ms:.3f}ms P95, {fastest_serialize.ops_per_second:,.0f} ops/sec)"
                )
                print(
                    f"  Slowest: {slowest_serialize.name} ({slowest_serialize.p95_ms:.3f}ms P95, {slowest_serialize.ops_per_second:,.0f} ops/sec)"
                )
                print(f"  Speed difference: {slowest_serialize.p95_ms / fastest_serialize.p95_ms:.1f}x slower")

            if deserialize_ops:
                fastest_deserialize = min(deserialize_ops, key=lambda x: x.p95_ms)
                slowest_deserialize = max(deserialize_ops, key=lambda x: x.p95_ms)

                print("\nDESERIALIZATION COMPARISON:")
                print(
                    f"  Fastest: {fastest_deserialize.name} ({fastest_deserialize.p95_ms:.3f}ms P95, {fastest_deserialize.ops_per_second:,.0f} ops/sec)"
                )
                print(
                    f"  Slowest: {slowest_deserialize.name} ({slowest_deserialize.p95_ms:.3f}ms P95, {slowest_deserialize.ops_per_second:,.0f} ops/sec)"
                )
                print(f"  Speed difference: {slowest_deserialize.p95_ms / fastest_deserialize.p95_ms:.1f}x slower")

        # Generate recommendations
        print("\nOPTIMIZATION RECOMMENDATIONS:")

        json_ops = [r for r in all_results_flat if "json" in r.name.lower()]
        msgpack_ops = [r for r in all_results_flat if "msgpack" in r.name.lower()]
        orjson_ops = [r for r in all_results_flat if "orjson" in r.name.lower()]

        if orjson_ops and json_ops:
            json_avg = sum(r.p95_ms for r in json_ops) / len(json_ops)
            orjson_avg = sum(r.p95_ms for r in orjson_ops) / len(orjson_ops)
            improvement = json_avg / orjson_avg
            print(f"  - Switch from JSON to orjson: {improvement:.1f}x faster serialization")

        if msgpack_ops and json_ops:
            json_avg = sum(r.p95_ms for r in json_ops) / len(json_ops)
            msgpack_avg = sum(r.p95_ms for r in msgpack_ops) / len(msgpack_ops)
            if msgpack_avg < json_avg:
                improvement = json_avg / msgpack_avg
                print(f"  - Switch from JSON to msgpack: {improvement:.1f}x faster serialization")

        print("  - Target: Complete cache operation < 1ms P95 latency")
        print("  - Current cache issue: ~20ms P95 (mostly NOT from serialization)")


def main():
    """Run the serialization benchmark."""
    benchmark = SerializationBenchmark()
    results = benchmark.run_all_benchmarks()
    benchmark.print_results(results)


if __name__ == "__main__":
    main()
