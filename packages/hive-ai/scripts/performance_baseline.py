#!/usr/bin/env python3
"""
Performance baseline establishment for hive-ai package.

Measures key performance metrics across all components to establish
baseline for optimization tracking and regression detection.
"""
from __future__ import annotations


import asyncio
import json
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List

# Import hive-ai components for benchmarking
from hive_ai.core.config import AIConfig, ModelConfig, VectorConfig
from hive_ai.core.security import InputValidator, RateLimiter, SecretManager
from hive_ai.models.client import ModelClient
from hive_ai.models.registry import ModelRegistry
from hive_ai.vector.embedding import EmbeddingManager
from hive_ai.vector.store import VectorStore
from hive_logging import get_logger

logger = get_logger(__name__)


@dataclass
class PerformanceMetric:
    """Single performance measurement."""

    component: str
    operation: str
    duration_ms: float
    memory_mb: float | None = None
    cpu_percent: float | None = None
    success: bool = True
    error: str | None = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class PerformanceBenchmark:
    """Performance benchmark suite for hive-ai package."""

    def __init__(self):
        self.metrics: List[PerformanceMetric] = []
        self.ai_config = AIConfig()
        self.vector_config = VectorConfig(
            provider="chroma", collection_name="benchmark_test", dimension=384, connection_string=None  # Local testing
        )

    async def run_all_benchmarks_async(self) -> Dict[str, Any]:
        """Run complete performance benchmark suite."""
        logger.info("Starting hive-ai performance benchmark suite")
        start_time = time.time()

        benchmark_suites = [
            ("security_benchmarks", self.run_security_benchmarks_async),
            ("config_benchmarks", self.run_config_benchmarks_async),
            ("embedding_benchmarks", self.run_embedding_benchmarks_async),
            ("vector_benchmarks", self.run_vector_benchmarks_async),
            ("model_benchmarks", self.run_model_benchmarks_async),
        ]

        for suite_name, benchmark_func in benchmark_suites:
            try:
                logger.info(f"Running {suite_name}")
                await benchmark_func()
                logger.info(f"Completed {suite_name}")
            except Exception as e:
                logger.error(f"Failed {suite_name}: {e}")
                self.metrics.append(
                    PerformanceMetric(
                        component=suite_name, operation="suite_execution", duration_ms=0, success=False, error=str(e)
                    )
                )

        total_duration = time.time() - start_time
        logger.info(f"Benchmark suite completed in {total_duration:.2f}s")

        return self.generate_performance_report()

    async def run_security_benchmarks_async(self) -> None:
        """Benchmark security component performance."""
        # Input validation benchmarks
        validator = InputValidator()

        test_prompts = [
            "Simple test prompt",
            "A" * 1000,  # Medium length
            "A" * 10000,  # Large prompt
            "javascript:alert('test')",  # Injection attempt
            "<script>console.log('test')</script>",  # XSS attempt
        ]

        for i, prompt in enumerate(test_prompts):
            duration = await self._time_operation_async(
                lambda: validator.validate_prompt(prompt), f"input_validation_prompt_{i}"
            )

            self.metrics.append(
                PerformanceMetric(
                    component="security",
                    operation=f"validate_prompt_size_{len(prompt)}",
                    duration_ms=duration,
                    metadata={"prompt_length": len(prompt)}
                )
            )

        # Secret management benchmarks
        secret_mgr = SecretManager()
        test_secrets = ["sk-1234567890abcdef", "api_key_very_long_secret_string"]

        for secret in test_secrets:
            duration = await self._time_operation_async(lambda: secret_mgr.mask_secret(secret), "secret_masking")

            self.metrics.append(
                PerformanceMetric(
                    component="security",
                    operation="mask_secret",
                    duration_ms=duration,
                    metadata={"secret_length": len(secret)}
                )
            )

        # Rate limiter benchmarks
        rate_limiter = RateLimiter(max_requests=100, window_seconds=60)

        # Test rate limiting performance
        duration = await self._time_operation_async(
            lambda: [rate_limiter.is_allowed(f"user_{i}") for i in range(50)], "rate_limit_check_batch"
        )

        self.metrics.append(
            PerformanceMetric(
                component="security", operation="rate_limit_batch_50", duration_ms=duration, metadata={"batch_size": 50}
            )
        )

    async def run_config_benchmarks_async(self) -> None:
        """Benchmark configuration system performance."""
        # Config creation and validation
        duration = await self._time_operation_async(lambda: AIConfig(), "config_creation")

        self.metrics.append(PerformanceMetric(component="config", operation="ai_config_creation", duration_ms=duration))

        # Model config validation
        model_configs = [
            ModelConfig(
                name=f"test_model_{i}",
                provider="test",
                model_type="completion",
                max_tokens=4096,
                temperature=0.7,
                cost_per_token=0.001
            )
            for i in range(10)
        ]

        duration = await self._time_operation_async(
            lambda: [config.model_dump() for config in model_configs], "model_config_serialization"
        )

        self.metrics.append(
            PerformanceMetric(
                component="config",
                operation="model_config_batch_serialize",
                duration_ms=duration,
                metadata={"config_count": len(model_configs)}
            )
        )

    async def run_embedding_benchmarks_async(self) -> None:
        """Benchmark embedding generation performance."""
        try:
            embedding_manager = EmbeddingManager(self.ai_config)

            test_texts = [
                "Short text",
                "Medium length text that contains more words and complexity",
                "Long text " * 100,  # Very long text
                "Technical documentation with complex terminology and detailed explanations",
            ]

            # Test individual embedding generation (simulated)
            for i, text in enumerate(test_texts):
                duration = await self._time_operation_async(
                    lambda: embedding_manager._simulate_embedding_async(text), f"embedding_generation_{i}"
                )

                self.metrics.append(
                    PerformanceMetric(
                        component="embedding",
                        operation=f"generate_single_length_{len(text)}",
                        duration_ms=duration,
                        metadata={"text_length": len(text)}
                    )
                )

            # Test batch embedding generation
            duration = await self._time_operation_async(
                lambda: embedding_manager.generate_batch_embeddings_async(test_texts, use_cache=False),
                "batch_embedding_generation",
            )

            self.metrics.append(
                PerformanceMetric(
                    component="embedding",
                    operation="generate_batch",
                    duration_ms=duration,
                    metadata={"batch_size": len(test_texts)}
                )
            )

            # Test similarity calculation
            vec1 = await embedding_manager._simulate_embedding_async("Test text 1")
            vec2 = await embedding_manager._simulate_embedding_async("Test text 2")

            duration = await self._time_operation_async(
                lambda: embedding_manager._calculate_cosine_similarity(vec1, vec2), "similarity_calculation"
            )

            self.metrics.append(
                PerformanceMetric(
                    component="embedding",
                    operation="cosine_similarity",
                    duration_ms=duration,
                    metadata={"vector_dimension": len(vec1)}
                )
            )

        except Exception as e:
            logger.warning(f"Embedding benchmarks failed: {e}")
            self.metrics.append(
                PerformanceMetric(
                    component="embedding", operation="benchmark_suite", duration_ms=0, success=False, error=str(e)
                )
            )

    async def run_vector_benchmarks_async(self) -> None:
        """Benchmark vector store performance."""
        try:
            # Note: This would require actual ChromaDB for full testing
            # For now, we'll benchmark the wrapper logic

            # Test vector store initialization
            duration = await self._time_operation_async(lambda: VectorStore(self.vector_config), "vector_store_init")

            self.metrics.append(
                PerformanceMetric(component="vector_store", operation="initialization", duration_ms=duration)
            )

            # Test configuration validation
            test_configs = [
                VectorConfig(provider="chroma", collection_name=f"test_{i}", dimension=384) for i in range(10)
            ]

            duration = await self._time_operation_async(
                lambda: [config.model_dump() for config in test_configs], "vector_config_validation"
            )

            self.metrics.append(
                PerformanceMetric(
                    component="vector_store",
                    operation="config_batch_validation",
                    duration_ms=duration,
                    metadata={"config_count": len(test_configs)}
                )
            )

        except Exception as e:
            logger.warning(f"Vector store benchmarks failed: {e}")
            self.metrics.append(
                PerformanceMetric(
                    component="vector_store", operation="benchmark_suite", duration_ms=0, success=False, error=str(e)
                )
            )

    async def run_model_benchmarks_async(self) -> None:
        """Benchmark model system performance."""
        try:
            # Test registry initialization
            duration = await self._time_operation_async(
                lambda: ModelRegistry(self.ai_config), "registry_initialization"
            )

            self.metrics.append(
                PerformanceMetric(component="model_registry", operation="initialization", duration_ms=duration)
            )

            registry = ModelRegistry(self.ai_config)

            # Test model registration
            test_models = [
                ModelConfig(
                    name=f"benchmark_model_{i}",
                    provider="test",
                    model_type="completion",
                    max_tokens=4096,
                    cost_per_token=0.001
                )
                for i in range(20)
            ]

            duration = await self._time_operation_async(
                lambda: [registry._register_model(model) for model in test_models], "model_registration_batch"
            )

            self.metrics.append(
                PerformanceMetric(
                    component="model_registry",
                    operation="register_batch_20",
                    duration_ms=duration,
                    metadata={"model_count": len(test_models)}
                )
            )

            # Test model lookup performance
            duration = await self._time_operation_async(
                lambda: [registry.list_available_models() for _ in range(100)], "model_lookup_batch"
            )

            self.metrics.append(
                PerformanceMetric(
                    component="model_registry",
                    operation="lookup_batch_100",
                    duration_ms=duration,
                    metadata={"lookup_count": 100}
                )
            )

        except Exception as e:
            logger.warning(f"Model benchmarks failed: {e}")
            self.metrics.append(
                PerformanceMetric(
                    component="model_system", operation="benchmark_suite", duration_ms=0, success=False, error=str(e)
                )
            )

    async def _time_operation_async(self, operation: callable, operation_name: str) -> float:
        """Time an async or sync operation."""
        start_time = time.perf_counter()

        try:
            if asyncio.iscoroutinefunction(operation):
                await operation()
            else:
                result = operation()
                if asyncio.iscoroutine(result):
                    await result
        except Exception as e:
            logger.warning(f"Operation {operation_name} failed: {e}")
            raise

        end_time = time.perf_counter()
        return (end_time - start_time) * 1000  # Convert to milliseconds

    def generate_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report."""
        if not self.metrics:
            return {"error": "No metrics collected"}

        # Group metrics by component
        component_metrics = {}
        for metric in self.metrics:
            if metric.component not in component_metrics:
                component_metrics[metric.component] = []
            component_metrics[metric.component].append(metric)

        # Calculate statistics for each component
        component_stats = {}
        for component, metrics in component_metrics.items():
            successful_metrics = [m for m in metrics if m.success]
            durations = [m.duration_ms for m in successful_metrics]

            if durations:
                component_stats[component] = {
                    "operation_count": len(metrics),
                    "success_count": len(successful_metrics),
                    "success_rate": len(successful_metrics) / len(metrics),
                    "avg_duration_ms": statistics.mean(durations),
                    "median_duration_ms": statistics.median(durations),
                    "min_duration_ms": min(durations),
                    "max_duration_ms": max(durations),
                    "total_duration_ms": sum(durations),
                    "operations": [
                        {
                            "operation": m.operation,
                            "duration_ms": m.duration_ms,
                            "success": m.success,
                            "metadata": m.metadata
                        }
                        for m in metrics
                    ]
                }
            else:
                component_stats[component] = {
                    "operation_count": len(metrics),
                    "success_count": 0,
                    "success_rate": 0.0,
                    "error": "No successful operations"
                }

        # Overall statistics
        all_successful = [m for m in self.metrics if m.success]
        all_durations = [m.duration_ms for m in all_successful]

        overall_stats = {
            "total_operations": len(self.metrics),
            "successful_operations": len(all_successful),
            "overall_success_rate": len(all_successful) / len(self.metrics) if self.metrics else 0,
            "total_benchmark_duration_ms": sum(all_durations) if all_durations else 0,
            "avg_operation_duration_ms": statistics.mean(all_durations) if all_durations else 0
        }

        # Performance insights
        insights = self._generate_performance_insights(component_stats, overall_stats)

        return {
            "timestamp": time.time(),
            "benchmark_version": "1.0.0",
            "overall_statistics": overall_stats,
            "component_statistics": component_stats,
            "performance_insights": insights,
            "recommendations": self._generate_recommendations(component_stats)
        }

    def _generate_performance_insights(
        self, component_stats: Dict[str, Any], overall_stats: Dict[str, Any]
    ) -> List[str]:
        """Generate performance insights from benchmark data."""
        insights = []

        # Success rate insights
        if overall_stats["overall_success_rate"] < 0.95:
            insights.append(f"Overall success rate ({overall_stats['overall_success_rate']:.1%}) below 95% threshold")

        # Component performance insights
        for component, stats in component_stats.items():
            if "avg_duration_ms" in stats:
                avg_duration = stats["avg_duration_ms"]

                if avg_duration > 1000:
                    insights.append(f"{component} operations averaging {avg_duration:.1f}ms (>1s threshold)")
                elif avg_duration < 10:
                    insights.append(f"{component} operations very fast: {avg_duration:.1f}ms average")

                # Check for high variance
                if "max_duration_ms" in stats and "min_duration_ms" in stats:
                    variance_ratio = stats["max_duration_ms"] / stats["min_duration_ms"]
                    if variance_ratio > 10:
                        insights.append(f"{component} high variance: {variance_ratio:.1f}x between min/max")

        return insights

    def _generate_recommendations(self, component_stats: Dict[str, Any]) -> List[str]:
        """Generate optimization recommendations."""
        recommendations = []

        for component, stats in component_stats.items():
            if "avg_duration_ms" not in stats:
                continue

            avg_duration = stats["avg_duration_ms"]

            # Performance-based recommendations
            if component == "security" and avg_duration > 100:
                recommendations.append("Consider caching validation results for security components")

            if component == "embedding" and avg_duration > 2000:
                recommendations.append("Implement embedding caching and batching optimizations")

            if component == "vector_store" and avg_duration > 500:
                recommendations.append("Optimize vector store operations with connection pooling")

            if component == "model_registry" and avg_duration > 50:
                recommendations.append("Cache model registry lookups for better performance")

        # Success rate recommendations
        for component, stats in component_stats.items():
            if stats["success_rate"] < 0.9:
                recommendations.append(
                    f"Investigate {component} reliability issues (success rate: {stats['success_rate']:.1%})"
                )

        return recommendations

    def save_report(self, report: Dict[str, Any], output_path: Path | None = None) -> Path:
        """Save performance report to file."""
        if output_path is None:
            output_path = Path(__file__).parent / "performance_baseline_report.json"

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)

        logger.info(f"Performance report saved to {output_path}")
        return output_path


async def main():
    """Run performance benchmark suite."""
    benchmark = PerformanceBenchmark()

    try:
        report = await benchmark.run_all_benchmarks_async()
        output_path = benchmark.save_report(report)

        # Print summary
        overall = report["overall_statistics"]
        logger.info(f"\n=== HIVE-AI PERFORMANCE BASELINE ===")
        logger.info(f"Total Operations: {overall['total_operations']}")
        logger.info(f"Success Rate: {overall['overall_success_rate']:.1%}")
        logger.info(f"Average Duration: {overall['avg_operation_duration_ms']:.2f}ms")
        logger.info(f"Total Time: {overall['total_benchmark_duration_ms']:.2f}ms")

        if report["performance_insights"]:
            logger.info(f"\nKey Insights:")
            for insight in report["performance_insights"]:
                logger.info(f"  • {insight}")

        if report["recommendations"]:
            logger.info(f"\nRecommendations:")
            for rec in report["recommendations"]:
                logger.info(f"  • {rec}")

        logger.info(f"\nDetailed report: {output_path}")

        return report

    except Exception as e:
        logger.error(f"Benchmark suite failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
