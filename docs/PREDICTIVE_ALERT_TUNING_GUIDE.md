# Predictive Alert System Tuning Guide

**PROJECT VANGUARD Phase A - Validation & Monitoring**

This guide provides systematic instructions for tuning the predictive alert system to achieve target performance metrics.

## Performance Targets

- **False Positive Rate**: <10%
- **Precision**: ≥90%
- **Recall**: ≥70%
- **F1 Score**: ≥0.80

## Tuning Parameters

### Location: `packages/hive-errors/src/hive_errors/predictive_alerts.py`

The following parameters control alert sensitivity and accuracy:

### 1. Confidence Threshold

**Parameter**: `confidence_threshold` in `AlertConfig`

**Purpose**: Minimum confidence score required to generate an alert

**Default**: 0.75 (75%)

**Tuning Guide**:
- **If False Positive Rate > 10%**: INCREASE threshold
  - Try 0.80, then 0.85, then 0.90
  - Higher threshold = fewer alerts, higher quality
- **If False Negative Rate > 30%**: DECREASE threshold
  - Try 0.70, then 0.65
  - Lower threshold = more alerts, catches more issues
- **Sweet Spot**: Usually between 0.75-0.85

**Example**:
```python
AlertConfig(
    service_name="my_service",
    metric_type=MetricType.ERROR_RATE,
    threshold=5.0,
    confidence_threshold=0.80  # Increased from 0.75
)
```

### 2. Z-Score Threshold (Anomaly Detection)

**Parameter**: `z_score_threshold` in `TrendAnalyzer.detect_anomaly()`

**Purpose**: Statistical threshold for detecting outliers

**Default**: 2.0 (2 standard deviations)

**Tuning Guide**:
- **If Too Many Anomaly Alerts**: INCREASE threshold
  - Try 2.5, then 3.0
  - Higher = only extreme outliers trigger alerts
- **If Missing Actual Anomalies**: DECREASE threshold
  - Try 1.5
  - Lower = more sensitive to deviations
- **Statistical Meaning**:
  - 2.0 = ~95% confidence (2σ)
  - 2.5 = ~98.8% confidence
  - 3.0 = ~99.7% confidence (3σ)

**Code Location**: Line ~85-95 in `predictive_alerts.py`

### 3. EMA Smoothing Factor

**Parameter**: `alpha` in `TrendAnalyzer.calculate_ema()`

**Purpose**: Controls responsiveness vs. noise reduction

**Default**: 0.3

**Tuning Guide**:
- **If Alerts Too Noisy/Jumpy**: DECREASE alpha
  - Try 0.2, then 0.1
  - Lower = smoother trend, less reactive
- **If Alerts Too Slow to React**: INCREASE alpha
  - Try 0.4, then 0.5
  - Higher = faster response, more noise
- **Rule of Thumb**:
  - 0.1-0.2: Heavy smoothing (daily/weekly trends)
  - 0.3-0.4: Moderate smoothing (hourly trends)
  - 0.5+: Light smoothing (minute-level trends)

**Code Location**: Line ~50-60 in `predictive_alerts.py`

### 4. Degradation Window

**Parameter**: `degradation_window_minutes` in `AlertConfig`

**Purpose**: How long to look back for degradation pattern

**Default**: 30 minutes

**Tuning Guide**:
- **For Slow-Changing Metrics** (CPU, memory): 60-120 minutes
- **For Fast-Changing Metrics** (error rate, latency): 15-30 minutes
- **For Critical Services**: Shorter window (15-20 min) for faster alerts
- **For Non-Critical Services**: Longer window (60+ min) to avoid noise

**Example**:
```python
# Critical service - fast alerts
AlertConfig(
    service_name="payment_api",
    metric_type=MetricType.ERROR_RATE,
    degradation_window_minutes=15  # Reduced from 30
)

# Background job - avoid noise
AlertConfig(
    service_name="report_generator",
    metric_type=MetricType.CPU_UTILIZATION,
    degradation_window_minutes=120  # Increased from 30
)
```

### 5. Consecutive Increases Required

**Parameter**: Hard-coded in `TrendAnalyzer.is_degrading()`

**Purpose**: Number of consecutive increases to trigger degradation alert

**Default**: 3

**Tuning Guide**:
- **If Too Many False Positives**: INCREASE to 4 or 5
- **If Missing Real Degradations**: DECREASE to 2
- **Trade-off**: Higher = more confident but slower to alert

**Code Location**: Line ~110-120 in `predictive_alerts.py`

## Tuning Workflow

### Step 1: Baseline Collection (Week 1)

1. Deploy system with default parameters
2. Run for 1 week minimum
3. Collect validation data:
   ```bash
   python scripts/monitoring/alert_validation_tracker.py --report
   ```

### Step 2: Analyze Performance (Week 2)

1. Review validation report:
   ```bash
   python scripts/monitoring/alert_validation_tracker.py --report --output baseline_report.json
   ```

2. Identify primary issue:
   - **FP Rate > 10%**: Focus on reducing false positives
   - **FN Rate > 30%**: Focus on catching more issues
   - **Both high**: Start with FP reduction, then balance

### Step 3: Apply Targeted Tuning (Week 3+)

#### Scenario A: Reduce False Positives

**Priority Order**:
1. Increase `confidence_threshold` to 0.80
2. Increase `z_score_threshold` to 2.5
3. Increase `consecutive_increases` to 4
4. Increase `degradation_window_minutes` to 45

**Apply changes**, run for 3-5 days, then re-evaluate.

#### Scenario B: Reduce False Negatives

**Priority Order**:
1. Decrease `confidence_threshold` to 0.70
2. Decrease `degradation_window_minutes` to 20
3. Decrease `consecutive_increases` to 2
4. Decrease `z_score_threshold` to 1.5

**Apply changes**, run for 3-5 days, then re-evaluate.

#### Scenario C: Balance Precision and Recall

Use **F1 Score** optimization:
1. Start with moderate thresholds
2. Adjust `confidence_threshold` ±0.05 based on F1 trend
3. Fine-tune `z_score_threshold` ±0.25
4. Test for 1 week to confirm stability

### Step 4: Service-Specific Tuning

Different services have different optimal parameters:

```python
# Example: High-traffic critical service
AlertConfig(
    service_name="auth_service",
    metric_type=MetricType.ERROR_RATE,
    threshold=1.0,  # 1% error rate (strict)
    confidence_threshold=0.85,  # High confidence
    degradation_window_minutes=15  # Fast response
)

# Example: Background processing service
AlertConfig(
    service_name="data_pipeline",
    metric_type=MetricType.CPU_UTILIZATION,
    threshold=90.0,  # 90% CPU (relaxed)
    confidence_threshold=0.75,  # Standard confidence
    degradation_window_minutes=60  # Avoid noise
)

# Example: External API integration
AlertConfig(
    service_name="third_party_api",
    metric_type=MetricType.LATENCY_P95,
    threshold=2000.0,  # 2 seconds
    confidence_threshold=0.80,
    degradation_window_minutes=30
)
```

## Validation Process

After each tuning iteration:

1. **Collect Data** (3-5 days minimum):
   ```bash
   python scripts/monitoring/predictive_analysis_runner.py --continuous --interval 15
   ```

2. **Validate Alerts**:
   - For each alert, determine: True Positive or False Positive
   - Record in validation tracker:
     ```python
     tracker.validate_alert(
         alert_id="alert_12345",
         outcome="true_positive",  # or "false_positive"
         notes="Actual outage occurred 45 minutes after alert"
     )
     ```

3. **Generate Report**:
   ```bash
   python scripts/monitoring/alert_validation_tracker.py --report
   ```

4. **Analyze Metrics**:
   - Check if FP rate is decreasing
   - Check if Precision is increasing
   - Check if Recall remains acceptable
   - Review F1 score for overall balance

5. **Iterate**:
   - If targets not met, apply next tuning adjustment
   - If targets met, continue monitoring for 2 weeks to confirm stability

## Advanced Tuning Techniques

### 1. Time-of-Day Sensitivity

Some metrics have daily patterns. Consider:

```python
# Peak hours: stricter thresholds
if 9 <= hour <= 17:  # Business hours
    confidence_threshold = 0.85
else:  # Off-hours
    confidence_threshold = 0.75
```

### 2. Metric-Specific Thresholds

Different metrics need different sensitivities:

- **Error Rate**: Most sensitive (confidence_threshold=0.85)
- **CPU/Memory**: Moderate (confidence_threshold=0.80)
- **Latency**: Relaxed (confidence_threshold=0.75)

### 3. Service Criticality Tiers

Tier 1 (Critical): High confidence, fast response
Tier 2 (Important): Moderate confidence, standard response
Tier 3 (Background): Lower confidence, delayed response

## Monitoring Tuning Effectiveness

Track these metrics over time:

1. **False Positive Rate Trend**:
   - Goal: Steady decrease to <10%
   - Red flag: Increasing trend

2. **Alert Volume**:
   - Too high (>50/day): System is too sensitive
   - Too low (<5/week): System might miss issues

3. **Alert-to-Incident Ratio**:
   - Healthy: 1.2-1.5 alerts per incident
   - Unhealthy: >3.0 alerts per incident (too noisy)

4. **Lead Time**:
   - Measure time between alert and actual incident
   - Goal: 1-4 hours average lead time
   - <30 min: Alerts too late
   - >6 hours: Potentially too early (false alarms)

## Troubleshooting

### Problem: Constant False Positives for One Service

**Diagnosis**: Service has natural variance that triggers alerts

**Solutions**:
1. Increase `degradation_window_minutes` for that service
2. Increase `z_score_threshold` for that service
3. Use service-specific `confidence_threshold`

### Problem: Missing Actual Outages

**Diagnosis**: System not sensitive enough

**Solutions**:
1. Decrease `confidence_threshold`
2. Decrease `consecutive_increases` requirement
3. Shorten `degradation_window_minutes`

### Problem: Alerts Too Early (6+ hours before issue)

**Diagnosis**: Trend detection too aggressive

**Solutions**:
1. Decrease EMA alpha (smooth more)
2. Increase `consecutive_increases` requirement
3. Use longer `degradation_window_minutes`

### Problem: Alerts Too Late (<30 min before issue)

**Diagnosis**: Trend detection not responsive enough

**Solutions**:
1. Increase EMA alpha (react faster)
2. Decrease `consecutive_increases` requirement
3. Use shorter `degradation_window_minutes`

## Reference Implementation

See `scripts/monitoring/tune_predictive_alerts.py` (to be created) for:
- Automated parameter search
- Grid search optimization
- Bayesian optimization for parameter tuning

## Success Criteria

The system is considered well-tuned when:

1. **False Positive Rate < 10%** (sustained for 2+ weeks)
2. **Precision ≥ 90%** (sustained for 2+ weeks)
3. **Recall ≥ 70%** (sustained for 2+ weeks)
4. **F1 Score ≥ 0.80** (sustained for 2+ weeks)
5. **Average Lead Time**: 1-4 hours
6. **Alert Volume**: Manageable (<30/day)
7. **Team Confidence**: On-call engineers trust the alerts

## Graduation to Phase B

Once the system achieves success criteria for 2 consecutive weeks:

1. Issue `DeprecationWarning` for legacy monitoring methods
2. Begin Phase B: Active Deprecation
3. Document final parameter configuration
4. Create service-specific configuration templates

---

**For questions or assistance with tuning, consult:**
- PROJECT VANGUARD documentation
- Alert validation reports
- Historical performance data in `data/alert_validation.json`