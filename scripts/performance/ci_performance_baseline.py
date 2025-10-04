"""CI/CD Performance Baseline Integration

Runs performance analysis and checks for regressions against stored baselines.
Designed to run on every merge to main branch.
"""

import asyncio
import json
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

from hive_logging import get_logger
from hive_performance import AsyncProfiler, MetricsCollector, PerformanceAnalyzer, SystemMonitor

logger = get_logger(__name__)

# Performance regression thresholds
REGRESSION_THRESHOLD = 0.10  # 10% regression allowed
BASELINE_FILE = Path(__file__).parent.parent.parent / "performance_baseline.json"


async def collect_baseline_metrics() -> dict[str, Any]:
    """Collect current performance metrics as baseline."""
    # Initialize performance monitoring components
    metrics_collector = MetricsCollector(max_history_size=1000)
    system_monitor = SystemMonitor(collection_interval=1.0)
    async_profiler = AsyncProfiler()

    analyzer = PerformanceAnalyzer(
        metrics_collector=metrics_collector,
        system_monitor=system_monitor,
        async_profiler=async_profiler,
    )

    logger.info("Starting system monitoring...")
    await system_monitor.start_monitoring()
    await async_profiler.start_profiling()

    # Run for short period to collect metrics
    logger.info("Collecting baseline metrics (30 seconds)...")
    await asyncio.sleep(30)

    # Analyze performance
    report = await analyzer.analyze_performance(analysis_period=timedelta(seconds=30), include_predictions=False)

    await async_profiler.stop_profiling()
    await system_monitor.stop_monitoring()

    # Extract key metrics
    baseline = {
        "overall_score": report.overall_score,
        "performance_grade": report.performance_grade,
        "avg_response_time": report.avg_response_time,
        "throughput": report.throughput,
        "error_rate": report.error_rate,
        "resource_efficiency": report.resource_efficiency,
        "system_health": {
            "avg_cpu_percent": report.system_health.get("avg_cpu_percent", 0.0),
            "peak_cpu_percent": report.system_health.get("peak_cpu_percent", 0.0),
            "avg_memory_percent": report.system_health.get("avg_memory_percent", 0.0),
            "peak_memory_percent": report.system_health.get("peak_memory_percent", 0.0),
        },
        "critical_issues_count": len(report.critical_issues),
        "insights_count": len(report.insights),
    }

    return baseline


def save_baseline(baseline: dict[str, Any]) -> None:
    """Save baseline metrics to file."""
    BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(BASELINE_FILE, "w") as f:
        json.dump(baseline, f, indent=2)

    logger.info(f"Baseline saved to {BASELINE_FILE}")


def load_baseline() -> dict[str, Any] | None:
    """Load baseline metrics from file."""
    if not BASELINE_FILE.exists():
        logger.warning(f"No baseline file found at {BASELINE_FILE}")
        return None

    with open(BASELINE_FILE) as f:
        baseline = json.load(f)

    logger.info(f"Baseline loaded from {BASELINE_FILE}")
    return baseline


def compare_against_baseline(current: dict[str, Any], baseline: dict[str, Any]) -> tuple[bool, list[str]]:
    """Compare current metrics against baseline.

    Returns:
        (passed, regressions) where passed is True if no critical regressions detected

    """
    regressions = []
    passed = True

    # Check response time regression
    if baseline.get("avg_response_time", 0) > 0:
        current_rt = current.get("avg_response_time", 0)
        baseline_rt = baseline["avg_response_time"]
        regression_pct = (current_rt - baseline_rt) / baseline_rt

        if regression_pct > REGRESSION_THRESHOLD:
            regressions.append(
                f"Response Time: {baseline_rt:.3f}s → {current_rt:.3f}s ({regression_pct * 100:.1f}% SLOWER)",
            )
            passed = False

    # Check throughput regression (inverse - lower is worse)
    if baseline.get("throughput", 0) > 0:
        current_tp = current.get("throughput", 0)
        baseline_tp = baseline["throughput"]
        regression_pct = (baseline_tp - current_tp) / baseline_tp

        if regression_pct > REGRESSION_THRESHOLD:
            regressions.append(
                f"Throughput: {baseline_tp:.2f} ops/s → {current_tp:.2f} ops/s ({regression_pct * 100:.1f}% SLOWER)",
            )
            passed = False

    # Check error rate increase
    baseline_err = baseline.get("error_rate", 0)
    current_err = current.get("error_rate", 0)

    if current_err > baseline_err * (1 + REGRESSION_THRESHOLD):
        regressions.append(f"Error Rate: {baseline_err:.2%} → {current_err:.2%} (INCREASED)")
        passed = False

    # Check overall score drop
    current_score = current.get("overall_score", 0)
    baseline_score = baseline.get("overall_score", 0)
    score_drop = baseline_score - current_score

    if score_drop > 10:  # More than 10 point drop
        regressions.append(f"Overall Score: {baseline_score:.1f} → {current_score:.1f} ({score_drop:.1f} point DROP)")
        passed = False

    # Check for new critical issues
    current_critical = current.get("critical_issues_count", 0)
    baseline_critical = baseline.get("critical_issues_count", 0)

    if current_critical > baseline_critical:
        regressions.append(f"Critical Issues: {baseline_critical} → {current_critical} (NEW CRITICAL ISSUES)")
        passed = False

    return passed, regressions


async def main():
    """Main CI performance baseline workflow."""
    import argparse

    parser = argparse.ArgumentParser(description="CI/CD Performance Baseline Integration")
    parser.add_argument(
        "--mode",
        choices=["create", "check"],
        default="check",
        help="create: Create new baseline | check: Check against existing baseline",
    )
    parser.add_argument("--threshold", type=float, default=0.10, help="Regression threshold (default: 0.10 = 10%%)")

    args = parser.parse_args()

    global REGRESSION_THRESHOLD
    REGRESSION_THRESHOLD = args.threshold

    if args.mode == "create":
        logger.info("Creating new performance baseline...")
        baseline = await collect_baseline_metrics()
        save_baseline(baseline)

        print("\n=== Performance Baseline Created ===")
        print(f"Overall Score: {baseline['overall_score']:.1f}/100 (Grade: {baseline['performance_grade']})")
        print(f"Avg Response Time: {baseline['avg_response_time']:.3f}s")
        print(f"Throughput: {baseline['throughput']:.2f} ops/s")
        print(f"Error Rate: {baseline['error_rate']:.2%}")
        print(f"Critical Issues: {baseline['critical_issues_count']}")
        print(f"\nBaseline saved to: {BASELINE_FILE}")
        return 0

    if args.mode == "check":
        logger.info("Checking performance against baseline...")

        # Load existing baseline
        baseline = load_baseline()
        if not baseline:
            print("⚠️ No baseline found - run with --mode create first")
            print("Skipping performance regression check")
            return 0

        # Collect current metrics
        current = await collect_baseline_metrics()

        # Compare
        passed, regressions = compare_against_baseline(current, baseline)

        print("\n=== Performance Regression Check ===")
        print(f"Baseline: Score {baseline['overall_score']:.1f}/100")
        print(f"Current:  Score {current['overall_score']:.1f}/100")
        print()

        if passed:
            print("✅ PASSED - No performance regressions detected")
            print(
                f"   Response Time: {baseline.get('avg_response_time', 0):.3f}s → {current.get('avg_response_time', 0):.3f}s",
            )
            print(f"   Throughput: {baseline.get('throughput', 0):.2f} → {current.get('throughput', 0):.2f} ops/s")
            print(f"   Error Rate: {baseline.get('error_rate', 0):.2%} → {current.get('error_rate', 0):.2%}")
            return 0
        print(f"❌ FAILED - Performance regressions detected (threshold: {REGRESSION_THRESHOLD * 100:.0f}%):")
        for regression in regressions:
            print(f"   • {regression}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
