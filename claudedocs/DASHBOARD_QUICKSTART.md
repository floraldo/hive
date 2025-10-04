# Unified AI Apps Dashboard - Quickstart Guide

**Goal**: Get the dashboard running in <10 minutes to see your AI apps metrics in action!

---

## Prerequisites

You need:
1. **Docker** installed (easiest method)
2. **OR** Prometheus + Grafana installed locally

---

## Option 1: Docker Compose (Recommended - Fastest)

### Step 1: Create Docker Compose File

Create `docker-compose.monitoring.yml`:

```yaml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    container_name: hive-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/usr/share/prometheus/console_libraries'
      - '--web.console.templates=/usr/share/prometheus/consoles'

  grafana:
    image: grafana/grafana:latest
    container_name: hive-grafana
    ports:
      - "3000:3000"
    volumes:
      - grafana-data:/var/lib/grafana
      - ./monitoring/dashboards:/etc/grafana/provisioning/dashboards
      - ./monitoring/datasources:/etc/grafana/provisioning/datasources
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_USERS_ALLOW_SIGN_UP=false
    depends_on:
      - prometheus

volumes:
  prometheus-data:
  grafana-data:
```

### Step 2: Create Prometheus Config

Create `monitoring/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  # AI Reviewer - adjust port if different
  - job_name: 'ai-reviewer'
    static_configs:
      - targets: ['host.docker.internal:8001']
        labels:
          app: 'ai-reviewer'
          component: 'ai'

  # AI Planner - adjust port if different
  - job_name: 'ai-planner'
    static_configs:
      - targets: ['host.docker.internal:8002']
        labels:
          app: 'ai-planner'
          component: 'ai'

  # AI Deployer - adjust port if different
  - job_name: 'ai-deployer'
    static_configs:
      - targets: ['host.docker.internal:8003']
        labels:
          app: 'ai-deployer'
          component: 'ai'
```

**Note**: On Windows/Mac, `host.docker.internal` allows Docker to reach your host machine. On Linux, use your local IP (e.g., `192.168.1.100`).

### Step 3: Configure Grafana Auto-Provisioning

Create `monitoring/datasources/prometheus.yml`:

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
```

Create `monitoring/dashboards/dashboard-provider.yml`:

```yaml
apiVersion: 1

providers:
  - name: 'Hive AI Apps'
    orgId: 1
    folder: 'AI Performance'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /etc/grafana/provisioning/dashboards
```

### Step 4: Copy Dashboard JSON

```bash
# Create monitoring directory structure
mkdir -p monitoring/dashboards monitoring/datasources

# Copy dashboard JSON
cp claudedocs/PROJECT_SIGNAL_PHASE_4_4_UNIFIED_AI_DASHBOARD.json monitoring/dashboards/
```

### Step 5: Start Stack

```bash
# Start Prometheus + Grafana
docker-compose -f docker-compose.monitoring.yml up -d

# Check logs
docker-compose -f docker-compose.monitoring.yml logs -f
```

### Step 6: Access Dashboard

1. Open Grafana: http://localhost:3000
2. Login: `admin` / `admin` (change password when prompted)
3. Navigate: **Dashboards → AI Performance → Hive AI Apps - Unified Performance Dashboard**

---

## Option 2: Manual Setup (Windows Native)

### Step 1: Install Prometheus

Download from https://prometheus.io/download/

```bash
# Extract to C:\prometheus
cd C:\prometheus

# Create prometheus.yml (use config from above)
notepad prometheus.yml

# Start Prometheus
.\prometheus.exe --config.file=prometheus.yml
```

Prometheus UI: http://localhost:9090

### Step 2: Install Grafana

Download from https://grafana.com/grafana/download?platform=windows

```bash
# Extract to C:\grafana
cd C:\grafana\bin

# Start Grafana
.\grafana-server.exe
```

Grafana UI: http://localhost:3000

### Step 3: Import Dashboard

1. Open Grafana: http://localhost:3000
2. Login: `admin` / `admin`
3. **+ → Import**
4. Upload `PROJECT_SIGNAL_PHASE_4_4_UNIFIED_AI_DASHBOARD.json`
5. Select **Prometheus** datasource
6. Click **Import**

---

## Exposing Metrics from AI Apps

Your AI apps need to expose metrics endpoints. Here's how:

### Option A: Using hive-performance (Already Instrumented!)

Your apps are already instrumented! You just need to expose the metrics:

**In each AI app** (`ai-reviewer`, `ai-planner`, `ai-deployer`):

```python
# Add to your main app file (e.g., agent.py, app.py)
from hive_performance import start_metrics_server

# At app startup, expose metrics on different ports
if __name__ == "__main__":
    # AI Reviewer - port 8001
    # AI Planner - port 8002
    # AI Deployer - port 8003
    start_metrics_server(port=8001)  # Adjust per app

    # Your existing app logic
    agent.run()
```

**Quick Test**: Check metrics are exposed:
```bash
curl http://localhost:8001/metrics | grep adapter_claude_ai
curl http://localhost:8002/metrics | grep adapter_claude_planning
curl http://localhost:8003/metrics | grep deployment_execution
```

### Option B: Generate Test Data (For Demo)

If apps aren't running, generate test data with this script:

```python
# scripts/generate_test_metrics.py
from prometheus_client import start_http_server, Counter, Histogram
import time
import random

# Create test metrics matching your dashboard
claude_latency = Histogram('adapter_claude_ai_duration_seconds', 'Claude latency')
deployment_calls = Counter('deployment_execution_calls_total', 'Deployments', ['status'])

# Start metrics server
start_http_server(8001)

# Generate random data
print("Generating test metrics on http://localhost:8001/metrics")
while True:
    # Simulate Claude calls
    claude_latency.observe(random.uniform(0.5, 3.0))

    # Simulate deployments
    if random.random() > 0.8:
        deployment_calls.labels(status='success').inc()
    else:
        deployment_calls.labels(status='failure').inc()

    time.sleep(1)
```

Run it:
```bash
python scripts/generate_test_metrics.py
```

---

## Verification Checklist

### 1. Check Prometheus is Scraping

Visit http://localhost:9090/targets

You should see:
- ✅ `ai-reviewer (1/1 up)`
- ✅ `ai-planner (1/1 up)`
- ✅ `ai-deployer (1/1 up)`

**Troubleshooting**: If targets are DOWN:
- Check AI apps are running
- Verify ports (8001, 8002, 8003)
- Test metrics: `curl http://localhost:8001/metrics`

### 2. Check Metrics Exist

In Prometheus (http://localhost:9090), query:

```promql
# Should return data
adapter_claude_ai_duration_seconds_bucket
deployment_execution_calls_total
planning_process_task_duration_seconds_bucket
```

**Troubleshooting**: If no data:
- Metrics endpoints not exposed
- Apps not instrumented
- Wrong metric names

### 3. Check Dashboard

In Grafana (http://localhost:3000):

1. Open dashboard
2. Check **Row 1, Panel 1** shows data
3. If "No Data", check time range (top right)
4. Set to **Last 1 hour**

---

## Quick Demo Flow

### Scenario: See AI Pipeline in Action

1. **Start Monitoring Stack**:
   ```bash
   docker-compose -f docker-compose.monitoring.yml up -d
   ```

2. **Run AI Apps** (or use test data generator):
   ```bash
   # Terminal 1: AI Reviewer
   cd apps/ai-reviewer
   python -m ai_reviewer.agent

   # Terminal 2: AI Planner
   cd apps/ai-planner
   python -m ai_planner.agent

   # Terminal 3: AI Deployer
   cd apps/ai-deployer
   python -m ai_deployer.agent
   ```

3. **Trigger AI Workflow** (create tasks):
   ```python
   # Quick test script
   from hive_orchestration import get_client

   client = get_client()

   # Create review task → triggers ai-reviewer
   review_task = client.create_task(
       title="Review PR #123",
       task_type="review_pending",
       priority=50
   )

   # Creates plan task → triggers ai-planner
   plan_task = client.create_task(
       title="Plan deployment",
       task_type="planning_pending",
       priority=50
   )

   # Creates deployment task → triggers ai-deployer
   deploy_task = client.create_task(
       title="Deploy to prod",
       task_type="deployment_pending",
       priority=50
   )
   ```

4. **Watch Dashboard** (http://localhost:3000):
   - **Row 1**: See pipeline success rate update
   - **Row 2**: Claude AI latency increase
   - **Row 3**: Agent loops processing tasks
   - **Row 5**: Deployment execution

---

## Common Issues & Fixes

### Issue: "No Data" in Grafana

**Cause**: Prometheus not scraping or apps not exposing metrics

**Fix**:
```bash
# 1. Check Prometheus targets
curl http://localhost:9090/api/v1/targets | jq

# 2. Check metrics endpoints
curl http://localhost:8001/metrics
curl http://localhost:8002/metrics
curl http://localhost:8003/metrics

# 3. Verify Grafana datasource
# In Grafana: Configuration → Data Sources → Prometheus → Save & Test
```

### Issue: "Connection Refused" to AI Apps

**Cause**: Apps not running or wrong ports

**Fix**:
```bash
# Check what's running on expected ports
netstat -ano | findstr "8001 8002 8003"

# Start apps with correct ports
# Each app should expose metrics on its designated port
```

### Issue: Dashboard Shows Old/Stale Data

**Cause**: Time range or refresh settings

**Fix**:
1. Top right: Set time range to **Last 15 minutes**
2. Click refresh icon (or set auto-refresh to 30s)
3. Check app is generating new metrics

---

## Next Steps

### For Development
1. Keep monitoring stack running: `docker-compose up -d`
2. Run your AI apps with metrics enabled
3. Create tasks to see pipeline in action
4. Watch metrics update in real-time

### For Production
1. Configure persistent storage for Prometheus data
2. Set up alerting (see `PROJECT_SIGNAL_PHASE_4_4_COMPLETE.md`)
3. Add authentication to Grafana
4. Configure backup for Grafana dashboards

---

## Quick Commands Reference

```bash
# Start monitoring
docker-compose -f docker-compose.monitoring.yml up -d

# Stop monitoring
docker-compose -f docker-compose.monitoring.yml down

# View logs
docker-compose -f docker-compose.monitoring.yml logs -f

# Restart Grafana
docker-compose -f docker-compose.monitoring.yml restart grafana

# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Test metrics endpoint
curl http://localhost:8001/metrics | grep adapter

# Access UIs
# Prometheus: http://localhost:9090
# Grafana:    http://localhost:3000 (admin/admin)
```

---

**Questions?** Check:
- Full docs: `PROJECT_SIGNAL_PHASE_4_4_COMPLETE.md`
- Troubleshooting: Section in completion doc
- Prometheus docs: https://prometheus.io/docs
- Grafana docs: https://grafana.com/docs

**GKJ!** (Got it, keep jamming! 🎸)
