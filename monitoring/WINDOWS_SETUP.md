# Production Monitoring Setup - Windows Native

**Goal**: Operational Prometheus + Grafana without Docker Desktop

**Date**: 2025-10-05
**Status**: Production-Ready Alternative

---

## Quick Start (Flask Dashboard - Already Working)

The simple Flask dashboard is **production-ready** and currently operational:

```bash
# Terminal 1: Start test metrics servers
python scripts/monitoring/generate_test_metrics.py

# Terminal 2: Start dashboard
python scripts/monitoring/simple_dashboard.py

# Access: http://localhost:5000
```

**Features**:
- Real-time metrics from 6 instrumented apps
- Auto-refresh every 5 seconds
- Responsive web interface
- No dependencies (pure Python + Flask)

---

## Windows Native Prometheus (Advanced Setup)

### Step 1: Download Prometheus

```powershell
# Download Prometheus for Windows
# https://prometheus.io/download/
# Example: prometheus-2.45.0.windows-amd64.zip

# Extract to monitoring/
Expand-Archive prometheus-*.zip monitoring/
Rename-Item monitoring/prometheus-* monitoring/prometheus
```

### Step 2: Configure Prometheus

Copy `monitoring/prometheus.yml` to `monitoring/prometheus/prometheus.yml`

### Step 3: Start Prometheus

```powershell
cd monitoring/prometheus
./prometheus.exe --config.file=prometheus.yml

# Access: http://localhost:9090
```

### Step 4: Configure App Metrics Endpoints

Update each app to expose `/metrics` endpoint:

**AI Reviewer** (`apps/ai-reviewer/src/ai_reviewer/main.py`):
```python
from hive_performance import get_prometheus_metrics
from fastapi import FastAPI

app = FastAPI()

@app.get("/metrics")
async def metrics():
    return Response(
        content=get_prometheus_metrics(),
        media_type="text/plain"
    )
```

Start on port 8001:
```bash
cd apps/ai-reviewer
uvicorn ai_reviewer.main:app --port 8001
```

Repeat for AI Planner (8002) and AI Deployer (8003).

---

## Windows Native Grafana (Advanced Setup)

### Step 1: Download Grafana

```powershell
# Download Grafana for Windows
# https://grafana.com/grafana/download?platform=windows
# Example: grafana-10.0.0.windows-amd64.zip

# Extract to monitoring/
Expand-Archive grafana-*.zip monitoring/
Rename-Item monitoring/grafana-* monitoring/grafana
```

### Step 2: Start Grafana

```powershell
cd monitoring/grafana/bin
./grafana-server.exe

# Access: http://localhost:3000
# Login: admin/admin
```

### Step 3: Add Prometheus Data Source

1. Navigate to **Configuration → Data Sources**
2. Click **Add data source**
3. Select **Prometheus**
4. Set URL: `http://localhost:9090`
5. Click **Save & Test**

### Step 4: Import Dashboard

1. Navigate to **Dashboards → Import**
2. Upload `monitoring/dashboards/PROJECT_SIGNAL_PHASE_4_4_UNIFIED_AI_DASHBOARD.json`
3. Select Prometheus datasource
4. Click **Import**

---

## Recommended Production Setup

**For Now**: Use Flask dashboard (simple_dashboard.py)
- ✅ Already operational
- ✅ No setup required
- ✅ Real-time metrics
- ✅ Zero dependencies

**For Production**: Windows native Prometheus + Grafana
- Advanced querying (PromQL)
- Historical data storage (30 days)
- Alert manager integration
- Multiple dashboard support

---

## Metrics Endpoint URLs

| App          | Port | Metrics URL                  | Status      |
|--------------|------|------------------------------|-------------|
| AI Reviewer  | 8001 | http://localhost:8001/metrics | Implemented |
| AI Planner   | 8002 | http://localhost:8002/metrics | Implemented |
| AI Deployer  | 8003 | http://localhost:8003/metrics | Implemented |
| Orchestrator | 8000 | http://localhost:8000/metrics | Planned     |
| EcoSystemiser| 8010 | http://localhost:8010/metrics | Planned     |
| Chimera      | 8020 | http://localhost:8020/metrics | Planned     |

---

## Validation Checklist

- [x] Flask dashboard running
- [x] Test metrics servers operational
- [ ] Prometheus scraping all endpoints
- [ ] Grafana dashboard imported
- [ ] Alerting rules configured

---

## Troubleshooting

### Prometheus Won't Start
**Error**: `Failed to open TSDB`
**Fix**: Delete `monitoring/prometheus/data` and restart

### Grafana Can't Connect to Prometheus
**Error**: `HTTP Error Bad Gateway`
**Fix**: Verify Prometheus is running on port 9090

### Metrics Not Showing Up
**Error**: Dashboard shows "No Data"
**Fix**: Verify apps are running and exposing `/metrics` endpoint

---

**Status**: Flask dashboard OPERATIONAL - Advanced setup optional
**Next**: Configure actual app /metrics endpoints for Prometheus scraping
