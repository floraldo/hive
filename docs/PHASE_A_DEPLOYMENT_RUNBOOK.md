# PROJECT VANGUARD - Phase A Deployment Runbook

**Date**: 2025-09-29
**Phase**: Phase A Validation & Monitoring
**Objective**: Deploy predictive monitoring system and establish accuracy baseline
**Target**: <10% False Positive Rate sustained for 2 consecutive weeks

---

## Table of Contents

1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Production Deployment](#production-deployment)
3. [Alert Routing Configuration](#alert-routing-configuration)
4. [Validation Workflow](#validation-workflow)
5. [Weekly Reporting Schedule](#weekly-reporting-schedule)
6. [Troubleshooting](#troubleshooting)
7. [Success Criteria](#success-criteria)

---

## Pre-Deployment Checklist

### Infrastructure Verification

- [ ] All Phase 2.1 components deployed:
  - `packages/hive-errors/src/hive_errors/predictive_alerts.py`
  - `packages/hive-errors/src/hive_errors/alert_manager.py`
  - `scripts/monitoring/predictive_analysis_runner.py`
  - `scripts/monitoring/alert_validation_tracker.py`

- [ ] Monitoring integration verified:
  - MonitoringErrorReporter with `get_error_rate_history()`
  - HealthMonitor with `get_metric_history()`
  - CircuitBreaker with `get_failure_history()`

- [ ] CI/CD workflow ready:
  - `.github/workflows/predictive-monitoring.yml` deployed
  - Workflow schedule configured (15-minute intervals)

- [ ] Dependencies installed:
```bash
# Verify all hive packages available
pip list | grep hive-

# Expected packages:
# hive-errors
# hive-logging
# hive-async
# hive-db
# hive-performance
```

- [ ] Data directories created:
```bash
mkdir -p data/alerts
mkdir -p data/validation
mkdir -p data/reports
```

- [ ] Permissions configured:
  - GitHub Actions has write access to data/ directories
  - Alert routing services (Slack, PagerDuty) API keys configured

---

## Production Deployment

### Step 1: Enable Monitoring Components

**1.1 Initialize MonitoringErrorReporter with History Tracking**

Update production error handling to enable history collection:

```python
# In your main application initialization
from hive_errors.monitoring_error_reporter import MonitoringErrorReporter

error_reporter = MonitoringErrorReporter(
    enable_alerts=True,
    max_history=10000,  # Track last 10K errors for analysis
    alert_threshold=10   # Alert after 10 errors in window
)

# Register globally for use by PredictiveAnalysisRunner
import hive_errors
hive_errors._global_error_reporter = error_reporter
```

**1.2 Initialize HealthMonitor with Metric History**

Enable health monitoring with historical data:

```python
# In your health monitoring setup
from hive_ai.observability.health import HealthMonitor

health_monitor = HealthMonitor(
    check_interval_seconds=60,
    history_retention_hours=72,  # 3 days of history
    enable_predictive_analysis=True
)

# Start monitoring
await health_monitor.start()

# Register for predictive analysis
import hive_ai.observability
hive_ai.observability._global_health_monitor = health_monitor
```

**1.3 Enable CircuitBreaker Failure Tracking**

Update circuit breakers to track failure history:

```python
# For each service using CircuitBreaker
from hive_async.resilience import AsyncCircuitBreaker

circuit_breaker = AsyncCircuitBreaker(
    failure_threshold=5,
    timeout_seconds=60,
    name="service_name_here",  # Important for tracking
    enable_history=True
)
```

### Step 2: Initialize Predictive Alert System

**2.1 Configure Alert Manager**

Create production alert configuration:

```python
# scripts/production/setup_alert_manager.py
from hive_errors.alert_manager import PredictiveAlertManager, AlertConfig

alert_config = AlertConfig(
    # GitHub Integration
    github_enabled=True,
    github_token=os.getenv("GITHUB_TOKEN"),
    github_repo="your-org/hive",

    # Slack Integration (optional)
    slack_enabled=True,
    slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL"),

    # PagerDuty Integration (optional)
    pagerduty_enabled=False,  # Enable after Phase A validation

    # Alert Thresholds
    confidence_threshold=0.70,  # Initial conservative threshold
    alert_retention_days=90,
    deduplication_window_minutes=60
)

alert_manager = PredictiveAlertManager(config=alert_config)
```

**2.2 Start Predictive Analysis Runner**

Deploy continuous monitoring:

```python
# scripts/production/start_predictive_monitoring.py
from scripts.monitoring.predictive_analysis_runner import PredictiveAnalysisRunner
from hive_errors.alert_manager import PredictiveAlertManager
import hive_errors
import hive_ai.observability

# Get global monitoring components
error_reporter = hive_errors._global_error_reporter
health_monitor = hive_ai.observability._global_health_monitor

# Initialize runner
runner = PredictiveAnalysisRunner(
    alert_manager=alert_manager,
    error_reporter=error_reporter,
    health_monitor=health_monitor
)

# Start continuous monitoring (runs every 15 minutes)
await runner.run_continuous_async(interval_minutes=15)
```

### Step 3: Enable GitHub Workflow

**3.1 Configure Workflow Secrets**

Set required GitHub secrets:

```bash
# In GitHub repository settings → Secrets and variables → Actions
GITHUB_TOKEN          # Already available by default
SLACK_WEBHOOK_URL     # Optional: for Slack notifications
PAGERDUTY_API_KEY     # Optional: for PagerDuty integration
```

**3.2 Enable Workflow**

The workflow `.github/workflows/predictive-monitoring.yml` will automatically:
- Run every 15 minutes via cron schedule
- Execute `PredictiveAnalysisRunner`
- Generate alerts for detected trends
- Create GitHub issues for high-severity alerts

**3.3 Manual Trigger (Optional)**

Test workflow manually:

```bash
# Via GitHub UI: Actions → Predictive Monitoring → Run workflow
# Or via gh CLI:
gh workflow run predictive-monitoring.yml
```

---

## Alert Routing Configuration

### GitHub Issues (Primary Channel)

**Alert Format**:
```
Title: 🚨 [CRITICAL] Predictive Alert: connection_pool_exhaustion for postgres_service

Body:
## Predictive Alert

**Service**: postgres_service
**Metric**: connection_pool_usage
**Severity**: CRITICAL
**Confidence**: 87%
**Current Value**: 82.5%
**Predicted Breach**: 2025-09-29T14:30:00Z (2.5 hours)

### Trend Analysis
- Linear trend: increasing at 5.2% per hour
- EMA trend: 4.8% sustained increase
- Anomaly score: 3.2σ above baseline

### Recommended Actions
1. Review connection pool configuration
2. Check for connection leaks in application code
3. Consider temporary pool size increase
4. Investigate long-running queries

### Data Points
[Chart/graph visualization of trend]

---
🤖 Generated by PROJECT VANGUARD Phase 2.1
```

**Labels Applied**:
- `predictive-alert`
- `severity-critical` / `severity-high` / `severity-medium` / `severity-low`
- `service-{service_name}`
- `metric-{metric_type}`

### Slack Integration (Optional)

**Webhook Configuration**:

```python
# In alert_config
slack_enabled=True
slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL")
slack_channels={
    "CRITICAL": "#alerts-critical",
    "HIGH": "#alerts-high",
    "MEDIUM": "#alerts-monitoring",
    "LOW": "#alerts-monitoring"
}
```

**Message Format**:
```
🚨 CRITICAL Predictive Alert

Service: postgres_service
Metric: connection_pool_usage
Confidence: 87%
Breach in: 2.5 hours

View details: [GitHub Issue Link]
```

### PagerDuty Integration (Phase B)

**Note**: PagerDuty integration should be **disabled during Phase A** to avoid alert fatigue during tuning period.

Enable after achieving <10% false positive rate:

```python
pagerduty_enabled=True
pagerduty_api_key=os.getenv("PAGERDUTY_API_KEY")
pagerduty_service_id=os.getenv("PAGERDUTY_SERVICE_ID")
```

---

## Validation Workflow

### Daily Alert Review

**Time Commitment**: 15-30 minutes per day

**Process**:

1. **Check New Alerts**
```bash
# View alerts generated in last 24 hours
gh issue list --label "predictive-alert" --state open --created ">=2025-09-29"
```

2. **Classify Each Alert**

For each alert, determine outcome:

- **True Positive (TP)**: Alert correctly predicted an issue
  - System metrics actually degraded or breached threshold
  - Issue prevented by proactive intervention
  - Would have caused incident without alert

- **False Positive (FP)**: Alert was incorrect
  - Metrics stabilized naturally without intervention
  - Temporary spike that self-resolved
  - Alert threshold too sensitive

- **Unknown**: Not enough time has passed to determine outcome
  - Wait until predicted breach time + 1 hour
  - Re-evaluate with full data

3. **Record Validation**

```bash
# Use AlertValidationTracker CLI
python scripts/monitoring/alert_validation_tracker.py record-alert \
    --alert-id "alert_20250929_143022_postgres" \
    --service "postgres_service" \
    --metric "connection_pool_usage" \
    --breach-time "2025-09-29T14:30:00Z" \
    --confidence 0.87 \
    --severity "CRITICAL"

# After outcome is known (TP or FP)
python scripts/monitoring/alert_validation_tracker.py validate-alert \
    --alert-id "alert_20250929_143022_postgres" \
    --outcome "true_positive" \
    --notes "Pool exhaustion prevented by temporary scaling"
```

4. **Update GitHub Issue**

Add validation comment:

```markdown
## Validation Result: ✅ TRUE POSITIVE

**Validated By**: [Your Name]
**Validation Date**: 2025-09-29
**Outcome**: Alert was correct - connection pool exhaustion prevented

**Actions Taken**:
- Scaled connection pool from 20 to 30 connections
- Investigated long-running query causing leak
- Fixed application code in PR #1234

**Impact**:
- Incident prevented
- No user-facing downtime
- Alert lead time: 2.5 hours

---
Phase A Validation
```

### False Negative Detection

**Weekly Task**: Check for incidents that occurred WITHOUT prior alerts

```bash
# Review incident reports
gh issue list --label "incident" --created ">=2025-09-22"

# Cross-reference with alert history
python scripts/monitoring/alert_validation_tracker.py check-false-negatives \
    --incident-date "2025-09-29" \
    --service "postgres_service"
```

**Record False Negatives**:

```bash
python scripts/monitoring/alert_validation_tracker.py record-false-negative \
    --incident-id "INC-2025-09-29-001" \
    --service "postgres_service" \
    --metric "connection_pool_usage" \
    --breach-time "2025-09-29T16:45:00Z" \
    --notes "No alert generated; threshold may be too high"
```

---

## Weekly Reporting Schedule

### End-of-Week Report

**Schedule**: Every Friday at 5 PM
**Duration**: 30-45 minutes

**Generate Report**:

```bash
# Generate comprehensive validation report
python scripts/monitoring/alert_validation_tracker.py generate-report \
    --start-date "2025-09-23" \
    --end-date "2025-09-29" \
    --output "data/reports/validation_week_1.json"
```

**Report Contents**:

```json
{
  "period": {
    "start": "2025-09-23",
    "end": "2025-09-29"
  },
  "metrics": {
    "total_alerts": 24,
    "validated_alerts": 22,
    "pending_validation": 2,
    "true_positives": 18,
    "false_positives": 4,
    "false_negatives": 1,
    "accuracy": 0.863,
    "precision": 0.818,
    "recall": 0.947,
    "f1_score": 0.878
  },
  "by_severity": {
    "CRITICAL": {"tp": 5, "fp": 0, "precision": 1.0},
    "HIGH": {"tp": 8, "fp": 2, "precision": 0.8},
    "MEDIUM": {"tp": 5, "fp": 2, "precision": 0.714}
  },
  "by_service": {
    "postgres_service": {"tp": 6, "fp": 1, "precision": 0.857},
    "redis_service": {"tp": 4, "fp": 1, "precision": 0.8},
    "api_gateway": {"tp": 8, "fp": 2, "precision": 0.8}
  },
  "tuning_recommendations": [
    "Increase confidence_threshold from 0.70 to 0.75 (reduce FP by ~40%)",
    "Decrease z_score_threshold for postgres_service from 2.5 to 2.0 (improve recall)",
    "Increase degradation_window for redis_service from 30min to 45min (reduce FP)"
  ]
}
```

**Review Checklist**:

- [ ] Review accuracy metrics (target: >90%)
- [ ] Review precision (target: >90%)
- [ ] Review recall (target: >70%)
- [ ] Review F1 score (target: >0.80)
- [ ] Identify high false positive services
- [ ] Review tuning recommendations
- [ ] Plan parameter adjustments for next week

### Apply Tuning Recommendations

**Parameter Tuning Process**:

1. **Review Recommendations**

```bash
python scripts/monitoring/alert_validation_tracker.py get-recommendations
```

2. **Update Configuration**

Edit `packages/hive-errors/src/hive_errors/predictive_alerts.py`:

```python
# Example: Adjust confidence threshold
class AlertConfig:
    confidence_threshold: float = 0.75  # Was 0.70, increased to reduce FP

# Example: Service-specific z-score thresholds
service_z_score_overrides = {
    "postgres_service": 2.0,  # Was 2.5, decreased to improve recall
    "redis_service": 2.8,     # Was 2.5, increased to reduce FP
}
```

3. **Deploy Updated Configuration**

```bash
# Commit changes
git add packages/hive-errors/src/hive_errors/predictive_alerts.py
git commit -m "tune: Adjust alert thresholds based on Week 1 validation

- Increase global confidence threshold: 0.70 → 0.75 (reduce FP ~40%)
- Decrease postgres z-score: 2.5 → 2.0 (improve recall)
- Increase redis z-score: 2.5 → 2.8 (reduce FP)

Expected impact:
- False positive rate: 16.7% → ~10%
- Precision: 81.8% → ~90%
- Recall maintained: 94.7%

Based on Week 1 validation data (24 alerts, 4 FP, 1 FN)"

git push
```

4. **Monitor Impact**

Track metrics for next week to validate tuning effectiveness.

---

## Troubleshooting

### No Alerts Generated

**Symptom**: Workflow runs successfully but no alerts created

**Diagnosis**:

```bash
# Check workflow logs
gh run list --workflow=predictive-monitoring.yml --limit 5

# View specific run
gh run view [run-id] --log

# Check if monitoring components are initialized
python -c "
from scripts.monitoring.predictive_analysis_runner import PredictiveAnalysisRunner
import hive_errors
import hive_ai.observability

print('Error Reporter:', hasattr(hive_errors, '_global_error_reporter'))
print('Health Monitor:', hasattr(hive_ai.observability, '_global_health_monitor'))
"
```

**Solutions**:

1. **Verify monitoring components are initialized** (see Step 1 of deployment)
2. **Check data availability**:
```python
# Test data retrieval
error_reporter.get_error_rate_history(hours=24)
health_monitor.get_metric_history("service_name", "response_time", hours=24)
```
3. **Lower confidence threshold temporarily** for testing:
```python
confidence_threshold: float = 0.50  # Temporary for debugging
```

### Too Many False Positives

**Symptom**: False positive rate >20%

**Diagnosis**:

```bash
# Analyze FP patterns
python scripts/monitoring/alert_validation_tracker.py analyze-false-positives
```

**Solutions**:

1. **Increase confidence threshold**:
```python
confidence_threshold: float = 0.80  # From 0.70
```

2. **Increase z-score threshold**:
```python
z_score_threshold: float = 3.0  # From 2.5
```

3. **Increase degradation window**:
```python
degradation_window_minutes: int = 45  # From 30
```

4. **Service-specific tuning**:
```python
# For volatile services
service_specific_config = {
    "redis_service": {
        "confidence_threshold": 0.85,
        "z_score_threshold": 3.5,
        "degradation_window_minutes": 60
    }
}
```

### Missing True Incidents (False Negatives)

**Symptom**: Incidents occurring without prior alerts

**Diagnosis**:

```bash
# Check false negative rate
python scripts/monitoring/alert_validation_tracker.py check-false-negatives --last-week
```

**Solutions**:

1. **Decrease confidence threshold**:
```python
confidence_threshold: float = 0.65  # From 0.70
```

2. **Decrease z-score threshold**:
```python
z_score_threshold: float = 2.0  # From 2.5
```

3. **Decrease degradation window**:
```python
degradation_window_minutes: int = 15  # From 30
```

4. **Check monitoring coverage**:
```python
# Ensure all critical services have monitoring
services_monitored = runner.get_monitored_services()
services_in_production = ["postgres", "redis", "api_gateway", ...]

missing_services = set(services_in_production) - set(services_monitored)
print(f"Missing monitoring: {missing_services}")
```

### Workflow Failures

**Symptom**: GitHub Actions workflow fails

**Diagnosis**:

```bash
# View failure logs
gh run list --workflow=predictive-monitoring.yml --status failure
gh run view [run-id] --log
```

**Common Causes**:

1. **Missing dependencies**:
```yaml
# Verify workflow dependencies in .github/workflows/predictive-monitoring.yml
- name: Install dependencies
  run: |
    pip install -e packages/hive-logging
    pip install -e packages/hive-errors
    pip install -e packages/hive-async
```

2. **Data directory permissions**:
```bash
# Ensure workflow can write to data/
chmod -R 777 data/  # Or configure GitHub Actions permissions
```

3. **API rate limits**:
```python
# Add rate limiting in alert_manager.py
rate_limiter = AlertRateLimiter(max_alerts_per_hour=20)
```

---

## Success Criteria

### Phase A Completion Checklist

**Week 1-2: Baseline Establishment**

- [ ] Predictive monitoring running continuously (15-min intervals)
- [ ] At least 20 alerts generated and validated
- [ ] Alert validation workflow established
- [ ] Initial tuning parameters applied
- [ ] Weekly report #1 generated

**Week 3-4: Target Achievement**

- [ ] False positive rate: <10% (target: <10%)
- [ ] Precision: ≥90% (target: ≥90%)
- [ ] Recall: ≥70% (target: ≥70%)
- [ ] F1 Score: ≥0.80 (target: ≥0.80)
- [ ] Zero false negatives for CRITICAL alerts
- [ ] Metrics sustained for 2 consecutive weeks

**Graduation to Phase B Criteria**:

All of the following must be true:

1. **Accuracy Metrics** (2 consecutive weeks):
   - False positive rate <10%
   - Precision ≥90%
   - Recall ≥70%
   - F1 Score ≥0.80

2. **Operational Confidence**:
   - No incidents caused by false alerts
   - Team trust in alert system established
   - Clear runbook and processes documented

3. **Coverage Validation**:
   - All critical services monitored
   - No critical false negatives
   - Alert lead time averages ≥2 hours

4. **Documentation Complete**:
   - Tuning parameters finalized and documented
   - Service-specific configurations defined
   - Validation data archived for audit

**Upon Meeting Criteria**:

Proceed to **Phase B: Active Deprecation**:
1. Issue `DeprecationWarning` for legacy monitoring methods
2. Document final parameter configuration
3. Create service-specific templates
4. Begin grace period for legacy method migration
5. Plan transition to Phase C (full autonomy)

---

## Quick Reference Commands

### Daily Operations

```bash
# Check recent alerts
gh issue list --label "predictive-alert" --state open --limit 10

# Validate alert
python scripts/monitoring/alert_validation_tracker.py validate-alert \
    --alert-id <id> --outcome true_positive

# Check validation statistics
python scripts/monitoring/alert_validation_tracker.py stats

# Trigger manual analysis
gh workflow run predictive-monitoring.yml
```

### Weekly Operations

```bash
# Generate weekly report
python scripts/monitoring/alert_validation_tracker.py generate-report \
    --start-date <YYYY-MM-DD> --end-date <YYYY-MM-DD>

# Get tuning recommendations
python scripts/monitoring/alert_validation_tracker.py get-recommendations

# Check for false negatives
python scripts/monitoring/alert_validation_tracker.py check-false-negatives --last-week
```

### Troubleshooting

```bash
# View workflow logs
gh run list --workflow=predictive-monitoring.yml --limit 5
gh run view [run-id] --log

# Test monitoring components
python scripts/monitoring/test_monitoring_integration.py

# Analyze false positive patterns
python scripts/monitoring/alert_validation_tracker.py analyze-false-positives
```

---

## Contact and Escalation

### Phase A Point of Contact

**Primary**: Agent 3 (Autonomous Platform Intelligence)
**Backup**: Development team lead
**Escalation**: For critical system issues or >3 consecutive FN for CRITICAL alerts

### Weekly Sync

**Schedule**: Every Friday after report generation
**Attendees**: Agent 3, Development team, Operations team
**Agenda**:
- Review week's metrics
- Discuss tuning adjustments
- Plan next week's priorities
- Address blockers

---

**Document Version**: 1.0
**Last Updated**: 2025-09-29
**Next Review**: 2025-10-06 (after Week 1 validation)