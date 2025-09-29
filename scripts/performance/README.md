# Performance Baseline System

Automated performance regression detection for CI/CD integration.

## Overview

The performance baseline system monitors platform-wide performance metrics and automatically detects regressions during CI/CD runs. It uses the `hive-performance` package to collect comprehensive metrics including:

- Response times (avg, p95, p99)
- Throughput (operations per second)
- Error rates
- Resource efficiency (CPU, memory)
- Async task performance
- System health metrics

## Components

### `ci_performance_baseline.py`

Main script for CI/CD integration with two modes:

**Create Mode** - Establish a new baseline:
```bash
python scripts/performance/ci_performance_baseline.py --mode create
```

**Check Mode** - Verify performance against baseline:
```bash
python scripts/performance/ci_performance_baseline.py --mode check --threshold 0.10
```

### Baseline File

Performance baseline stored at: `performance_baseline.json`

Contains:
- Overall performance score (0-100)
- Performance grade (A-F)
- Key metrics (response time, throughput, error rate)
- System health (CPU, memory utilization)
- Critical issues count

## CI/CD Integration

The system integrates with the main CI workflow (`.github/workflows/ci.yml`) at the **Performance Regression Testing** quality gate.

### Workflow Steps

1. Run EcoSystemiser-specific benchmarks
2. Run platform-wide performance baseline check
3. Compare against stored baseline
4. Fail build if >10% regression detected

### Regression Detection

Regressions are detected when:

- **Response Time**: >10% slower than baseline
- **Throughput**: >10% lower than baseline
- **Error Rate**: >10% increase from baseline
- **Overall Score**: >10 point drop from baseline
- **Critical Issues**: Any new critical issues

### Customizing Thresholds

Adjust regression threshold:
```bash
python scripts/performance/ci_performance_baseline.py --mode check --threshold 0.15  # 15% threshold
```

## Usage Examples

### Creating Initial Baseline

After making optimizations or on a known-good commit:

```bash
# Create baseline
cd /path/to/hive
python scripts/performance/ci_performance_baseline.py --mode create

# Output:
# === Performance Baseline Created ===
# Overall Score: 85.0/100 (Grade: B)
# Avg Response Time: 0.125s
# Throughput: 45.20 ops/s
# Error Rate: 0.50%
# Critical Issues: 0
```

### Checking for Regressions

During CI/CD or manual testing:

```bash
# Check against baseline
python scripts/performance/ci_performance_baseline.py --mode check

# Success output:
# ✅ PASSED - No performance regressions detected
#    Response Time: 0.125s → 0.130s
#    Throughput: 45.20 → 44.80 ops/s
#    Error Rate: 0.50% → 0.48%

# Failure output:
# ❌ FAILED - Performance regressions detected (threshold: 10%):
#    • Response Time: 0.125s → 0.180s (44.0% SLOWER)
#    • Overall Score: 85.0 → 72.0 (13.0 point DROP)
```

### Manual Performance Analysis

For detailed performance analysis outside CI:

```python
from hive_performance import AsyncProfiler, MetricsCollector, PerformanceAnalyzer, SystemMonitor
from datetime import timedelta

# Initialize components
metrics_collector = MetricsCollector(max_history_size=1000)
system_monitor = SystemMonitor(collection_interval=1.0)
async_profiler = AsyncProfiler()

analyzer = PerformanceAnalyzer(
    metrics_collector=metrics_collector,
    system_monitor=system_monitor,
    async_profiler=async_profiler
)

# Start monitoring
await system_monitor.start_monitoring()
await async_profiler.start_profiling()

# Run your workload here...
await my_application_workload()

# Analyze
report = await analyzer.analyze_performance(
    analysis_period=timedelta(hours=1),
    include_predictions=True
)

# Export results
print(analyzer.export_report(report, format="text"))
```

## Performance Optimization Workflow

1. **Identify bottlenecks** - Run analysis to find performance issues
2. **Implement optimizations** - Make code changes (caching, algorithms, etc.)
3. **Create new baseline** - After validating improvements
4. **CI monitors automatically** - Future commits checked against baseline
5. **Iterate** - Continuous performance improvement cycle

## Integration with hive-performance

The baseline system leverages:

- `MetricsCollector` - Operation-level performance tracking
- `SystemMonitor` - System resource monitoring
- `AsyncProfiler` - Async task performance profiling
- `PerformanceAnalyzer` - Multi-dimensional analysis and scoring

For advanced usage, see: `packages/hive-performance/README.md`

## Troubleshooting

### No baseline found

```
⚠️ No baseline found - run with --mode create first
```

**Solution**: Create initial baseline:
```bash
python scripts/performance/ci_performance_baseline.py --mode create
```

### False positive regressions

If legitimate changes cause performance shifts:

1. Review the regression details
2. If acceptable, create new baseline after merge
3. Consider adjusting threshold for specific scenarios

### Baseline out of date

Baselines should be updated:
- After major performance optimizations
- After significant architectural changes
- Quarterly as part of performance review

**Update command**:
```bash
python scripts/performance/ci_performance_baseline.py --mode create
```