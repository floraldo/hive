# MonitoringErrorReporter Migration Guide

Upgrade from basic error reporting to enhanced monitoring with metrics and alerting.

## Why Upgrade?

**Basic `BaseErrorReporter`** provides:
- Simple error logging
- Basic error counting
- Error history tracking

**Enhanced `MonitoringErrorReporter`** adds:
- Real-time error metrics (rates, trends)
- Component failure rate tracking
- Alert integration for critical conditions
- Performance impact analysis
- Health scoring and status
- Export capabilities (JSON, CSV)

## Quick Migration

### Before - Basic Error Reporter

```python
from hive_errors import BaseErrorReporter

reporter = BaseErrorReporter()

try:
    risky_operation()
except Exception as e:
    reporter.report_error(e)
```

### After - Monitoring Error Reporter

```python
from hive_errors import MonitoringErrorReporter

# Initialize with alerting
reporter = MonitoringErrorReporter(
    enable_alerts=True,
    alert_thresholds={
        "error_rate_per_minute": 10,
        "component_failure_threshold": 0.2,  # 20%
        "consecutive_failures": 5
    }
)

try:
    risky_operation()
except Exception as e:
    reporter.report_error(
        error=e,
        context={"user_id": "123", "request_id": "abc"},
        additional_info={"operation": "data_sync"}
    )

# Track successes too for failure rate calculation
reporter.record_success("data_sync", response_time=0.25)
```

## Key Features

### 1. Component Health Tracking

Track success/failure rates per component:

```python
from hive_errors import MonitoringErrorReporter

reporter = MonitoringErrorReporter()

# Track errors
try:
    database.query(sql)
except Exception as e:
    reporter.report_error(e, context={"component": "database"})

# Track successes
reporter.record_success("database", response_time=0.15)

# Get component health
health = reporter.get_component_health("database")
print(f"Health Score: {health['health_score']:.2f}")  # 0.0-1.0
print(f"Failure Rate: {health['failure_rate']:.1%}")
print(f"Status: {health['status']}")  # "healthy", "degraded", "critical"
print(f"Consecutive Failures: {health['consecutive_failures']}")
```

### 2. Real-Time Alerts

Set up automatic alerting:

```python
reporter = MonitoringErrorReporter(
    enable_alerts=True,
    alert_thresholds={
        "error_rate_per_minute": 10,      # Alert if >10 errors/min
        "critical_error_rate": 5,         # Alert if >5 critical/min
        "component_failure_threshold": 0.2,  # Alert if >20% failure rate
        "consecutive_failures": 5          # Alert after 5 consecutive failures
    }
)

# Register alert callback
def on_alert(alerts, error_record):
    for alert in alerts:
        print(f"ALERT: {alert['message']} (severity: {alert['severity']})")
        # Send to Slack, PagerDuty, etc.

reporter._alert_callbacks.append(on_alert)

# Errors now trigger alerts if thresholds exceeded
for i in range(15):  # Generates high_error_rate alert
    try:
        failing_operation()
    except Exception as e:
        reporter.report_error(e)
```

### 3. Error Trends Analysis

Analyze error patterns over time:

```python
from datetime import timedelta

# Get last hour of error trends
trends = reporter.get_error_trends(time_window=timedelta(hours=1))

print(f"Total Errors: {trends['total_errors']}")
print(f"Avg Errors/Hour: {trends['average_errors_per_hour']:.1f}")

# Errors by component
for component, count in trends['errors_by_component'].items():
    print(f"  {component}: {count}")

# Errors by type
for error_type, count in trends['errors_by_type'].items():
    print(f"  {error_type}: {count}")
```

### 4. Performance Impact Tracking

Correlate errors with performance:

```python
# Record operations with timing
start = time.time()
try:
    result = api_call()
    elapsed = time.time() - start
    reporter.record_success("api", response_time=elapsed)
except Exception as e:
    elapsed = time.time() - start
    reporter.report_error(e, context={"component": "api"})

# Analyze performance impact
impact = reporter.get_performance_impact("api")
print(f"Avg Response Time: {impact['avg_response_time']:.2f}s")
print(f"Response Time Range: {impact['min_response_time']:.2f}s - {impact['max_response_time']:.2f}s")
print(f"Trend: {impact['response_time_trend']}")  # "improving" or "stable"
```

### 5. Comprehensive Health Reports

Generate full system health reports:

```python
report = reporter.generate_health_report()

# Overall statistics
stats = report['overall_statistics']
print(f"Total Errors: {stats['total_errors']}")

# Component health
for component, health in report['component_health'].items():
    print(f"{component}: {health['status']} (score: {health['health_score']:.2f})")

# Active alerts
for alert in report['alert_summary']['active_alerts']:
    print(f"Alert: {alert['type']} - {alert['severity']}")

# Trends
trends = report['trends']
print(f"Errors in last hour: {trends['total_errors']}")
```

### 6. Data Export

Export error data for analysis:

```python
# Export as JSON
json_export = reporter.export_error_data(
    time_window=timedelta(days=1),
    format="json"
)
with open("errors.json", "w") as f:
    f.write(json_export)

# Export as CSV
csv_export = reporter.export_error_data(
    time_window=timedelta(days=1),
    format="csv"
)
with open("errors.csv", "w") as f:
    f.write(csv_export)
```

## Migration Strategy

### Phase 1: Add Monitoring Layer

Keep existing error handling, add monitoring:

```python
# Existing code
from hive_errors import BaseErrorReporter
base_reporter = BaseErrorReporter()

# New monitoring layer
from hive_errors import MonitoringErrorReporter
monitoring_reporter = MonitoringErrorReporter()

try:
    operation()
except Exception as e:
    # Report to both during migration
    base_reporter.report_error(e)
    monitoring_reporter.report_error(e, context={"component": "my_component"})
```

### Phase 2: Add Success Tracking

Start recording successful operations:

```python
try:
    result = operation()
    # NEW: Track success for failure rate calculation
    monitoring_reporter.record_success("my_component", response_time=0.15)
except Exception as e:
    monitoring_reporter.report_error(e, context={"component": "my_component"})
```

### Phase 3: Enable Alerts

Configure and enable alerting:

```python
reporter = MonitoringErrorReporter(enable_alerts=True)

# Register alert handlers
def alert_to_slack(alerts, error_record):
    for alert in alerts:
        slack_client.post_message(
            channel="#alerts",
            text=f"🚨 {alert['severity'].upper()}: {alert['message']}"
        )

reporter._alert_callbacks.append(alert_to_slack)
```

### Phase 4: Dashboard Integration

Use health reports for dashboards:

```python
# Periodic health report generation
async def update_dashboard():
    while True:
        report = reporter.generate_health_report()

        # Update metrics dashboard
        dashboard.update_metrics({
            "total_errors": report['overall_statistics']['total_errors'],
            "component_health": report['component_health'],
            "active_alerts": len(report['alert_summary']['active_alerts'])
        })

        await asyncio.sleep(60)  # Update every minute
```

### Phase 5: Remove Base Reporter

Once fully migrated and validated:

```python
# OLD: from hive_errors import BaseErrorReporter
# NEW: from hive_errors import MonitoringErrorReporter

reporter = MonitoringErrorReporter(
    enable_alerts=True,
    max_history=10000
)
```

## Alert Threshold Tuning

### Error Rate Thresholds

Based on your system's normal behavior:

```python
# Low-traffic system
alert_thresholds = {
    "error_rate_per_minute": 5,      # Alert at 5 errors/min
    "critical_error_rate": 2,        # Alert at 2 critical/min
}

# Medium-traffic system
alert_thresholds = {
    "error_rate_per_minute": 20,     # Alert at 20 errors/min
    "critical_error_rate": 5,        # Alert at 5 critical/min
}

# High-traffic system
alert_thresholds = {
    "error_rate_per_minute": 100,    # Alert at 100 errors/min
    "critical_error_rate": 20,       # Alert at 20 critical/min
}
```

### Component Failure Thresholds

Based on component criticality:

```python
# Critical components (databases, APIs)
alert_thresholds = {
    "component_failure_threshold": 0.05,  # Alert at 5% failure rate
    "consecutive_failures": 3             # Alert after 3 failures
}

# Standard components
alert_thresholds = {
    "component_failure_threshold": 0.20,  # Alert at 20% failure rate
    "consecutive_failures": 5             # Alert after 5 failures
}

# Non-critical components
alert_thresholds = {
    "component_failure_threshold": 0.50,  # Alert at 50% failure rate
    "consecutive_failures": 10            # Alert after 10 failures
}
```

## Async Error Reporting

For async operations:

```python
async def async_operation():
    reporter = MonitoringErrorReporter()

    try:
        result = await async_api_call()
        reporter.record_success("async_api", response_time=0.25)
        return result
    except Exception as e:
        error_id = await reporter.report_error_async(
            error=e,
            context={"component": "async_api"},
            additional_info={"operation": "data_fetch"}
        )
        logger.error(f"Error ID: {error_id}")
        raise
```

## Best Practices

1. **Always specify component**: Enables component-level health tracking
```python
reporter.report_error(e, context={"component": "database"})
```

2. **Track both success and failure**: Needed for accurate failure rates
```python
try:
    result = operation()
    reporter.record_success("my_component", response_time=elapsed)
except Exception as e:
    reporter.report_error(e, context={"component": "my_component"})
```

3. **Use meaningful component names**: Makes dashboards easier to understand
```python
# Good: reporter.record_success("user_auth_service")
# Bad:  reporter.record_success("service1")
```

4. **Set appropriate alert thresholds**: Based on traffic and criticality
```python
# Tune based on observed baselines
reporter = MonitoringErrorReporter(
    alert_thresholds={
        "error_rate_per_minute": baseline_rate * 3,  # 3x normal
        "component_failure_threshold": 0.10  # 10% failure
    }
)
```

5. **Export data regularly**: For long-term analysis
```python
# Daily export for archival
daily_export = reporter.export_error_data(
    time_window=timedelta(days=1),
    format="json"
)
archive_to_s3(daily_export, f"errors_{date.today()}.json")
```

6. **Clear old data**: Prevent memory growth
```python
# Weekly cleanup
reporter.clear_old_data(retention_period=timedelta(days=7))
```

## Real-World Example

Complete example with all features:

```python
from hive_errors import MonitoringErrorReporter
from datetime import timedelta
import time

# Initialize with custom configuration
reporter = MonitoringErrorReporter(
    enable_alerts=True,
    alert_thresholds={
        "error_rate_per_minute": 15,
        "component_failure_threshold": 0.15,
        "consecutive_failures": 4
    },
    max_history=5000
)

# Register alert handler
def handle_alert(alerts, error_record):
    for alert in alerts:
        if alert['severity'] == 'critical':
            send_page(alert['message'])
        else:
            log_warning(alert['message'])

reporter._alert_callbacks.append(handle_alert)

# Application loop
def process_batch():
    component = "batch_processor"
    start = time.time()

    try:
        # Process records
        results = batch_operation()

        # Track success
        elapsed = time.time() - start
        reporter.record_success(component, response_time=elapsed)

        return results

    except Exception as e:
        # Report error with context
        reporter.report_error(
            error=e,
            context={"component": component},
            additional_info={
                "batch_size": len(records),
                "operation": "batch_process"
            }
        )
        raise

# Periodic health monitoring
def monitor_health():
    report = reporter.generate_health_report()

    # Check component health
    health = reporter.get_component_health("batch_processor")
    if health['status'] in ['degraded', 'critical']:
        logger.warning(
            f"Component {health['component']} is {health['status']}: "
            f"{health['consecutive_failures']} consecutive failures"
        )

    # Check trends
    trends = reporter.get_error_trends(time_window=timedelta(hours=1))
    if trends['total_errors'] > 50:
        logger.warning(f"High error volume: {trends['total_errors']} in last hour")

    return report

# Cleanup old data (run daily)
def daily_maintenance():
    reporter.clear_old_data(retention_period=timedelta(days=7))
```