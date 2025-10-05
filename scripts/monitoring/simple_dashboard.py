#!/usr/bin/env python3
"""Simple web-based metrics viewer - No Docker required!

Lightweight alternative to Grafana for viewing AI apps metrics.
Just run this script and open http://localhost:5000
"""

from typing import Any

try:
    import requests
    from flask import Flask, jsonify, render_template_string
except ImportError:
    print("Installing required packages...")
    import subprocess
    subprocess.check_call(["pip", "install", "flask", "requests"])
    import requests
    from flask import Flask, jsonify, render_template_string

app = Flask(__name__)

# AI Apps metrics endpoints
METRICS_ENDPOINTS = {
    "ai-reviewer": "http://localhost:8001/metrics",
    "ai-planner": "http://localhost:8002/metrics",
    "ai-deployer": "http://localhost:8003/metrics",
}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Hive AI Apps - Metrics Viewer</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            padding: 20px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        h1 {
            color: white;
            margin-bottom: 10px;
            font-size: 2.5em;
        }
        .subtitle {
            color: rgba(255,255,255,0.9);
            margin-bottom: 30px;
            font-size: 1.1em;
        }
        .dashboard {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .card {
            background: white;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 15px 40px rgba(0,0,0,0.4);
        }
        .card-title {
            font-size: 1.3em;
            font-weight: 600;
            margin-bottom: 16px;
            color: #667eea;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .metric {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid #eee;
        }
        .metric:last-child {
            border-bottom: none;
        }
        .metric-label {
            font-weight: 500;
            color: #555;
        }
        .metric-value {
            font-size: 1.4em;
            font-weight: 700;
            color: #667eea;
        }
        .status-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 600;
        }
        .status-online {
            background: #10b981;
            color: white;
        }
        .status-offline {
            background: #ef4444;
            color: white;
        }
        .refresh-info {
            text-align: center;
            color: rgba(255,255,255,0.8);
            margin-top: 20px;
            font-size: 0.9em;
        }
        .icon {
            width: 24px;
            height: 24px;
        }
        .error-message {
            background: #fee;
            border: 1px solid #fcc;
            border-radius: 8px;
            padding: 16px;
            margin: 20px 0;
            color: #c00;
        }
        .setup-instructions {
            background: white;
            border-radius: 12px;
            padding: 24px;
            margin-top: 20px;
        }
        .setup-instructions h2 {
            color: #667eea;
            margin-bottom: 16px;
        }
        .setup-instructions pre {
            background: #f5f5f5;
            padding: 12px;
            border-radius: 6px;
            overflow-x: auto;
            margin: 10px 0;
        }
        .setup-instructions code {
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
        }
    </style>
    <script>
        // Auto-refresh every 5 seconds
        setInterval(() => {
            fetch('/api/metrics')
                .then(res => res.json())
                .then(data => updateDashboard(data))
                .catch(err => console.error('Refresh failed:', err));
        }, 5000);

        function updateDashboard(data) {
            document.getElementById('last-update').textContent = new Date().toLocaleTimeString();

            // Update each app's metrics
            for (const [app, metrics] of Object.entries(data)) {
                const statusEl = document.getElementById(`${app}-status`);
                const metricsEl = document.getElementById(`${app}-metrics`);

                if (metrics.online) {
                    statusEl.className = 'status-badge status-online';
                    statusEl.textContent = 'ONLINE';

                    let html = '';
                    for (const [key, value] of Object.entries(metrics.data || {})) {
                        html += `
                            <div class="metric">
                                <span class="metric-label">${key}</span>
                                <span class="metric-value">${value}</span>
                            </div>
                        `;
                    }
                    metricsEl.innerHTML = html || '<div class="metric-label">No metrics available yet</div>';
                } else {
                    statusEl.className = 'status-badge status-offline';
                    statusEl.textContent = 'OFFLINE';
                    metricsEl.innerHTML = `<div class="error-message">App not running or metrics not exposed</div>`;
                }
            }
        }

        // Initial load
        window.addEventListener('DOMContentLoaded', () => {
            fetch('/api/metrics')
                .then(res => res.json())
                .then(data => updateDashboard(data));
        });
    </script>
</head>
<body>
    <div class="container">
        <h1>🚀 Hive AI Apps - Metrics Viewer</h1>
        <p class="subtitle">Real-time performance monitoring for ai-reviewer, ai-planner, and ai-deployer</p>

        <div class="dashboard">
            <div class="card">
                <div class="card-title">
                    <svg class="icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                    </svg>
                    AI Reviewer
                    <span id="ai-reviewer-status" class="status-badge status-offline">CHECKING...</span>
                </div>
                <div id="ai-reviewer-metrics">
                    <div class="metric-label">Loading...</div>
                </div>
            </div>

            <div class="card">
                <div class="card-title">
                    <svg class="icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path>
                    </svg>
                    AI Planner
                    <span id="ai-planner-status" class="status-badge status-offline">CHECKING...</span>
                </div>
                <div id="ai-planner-metrics">
                    <div class="metric-label">Loading...</div>
                </div>
            </div>

            <div class="card">
                <div class="card-title">
                    <svg class="icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path>
                    </svg>
                    AI Deployer
                    <span id="ai-deployer-status" class="status-badge status-offline">CHECKING...</span>
                </div>
                <div id="ai-deployer-metrics">
                    <div class="metric-label">Loading...</div>
                </div>
            </div>
        </div>

        <div class="refresh-info">
            ⟳ Auto-refreshing every 5 seconds | Last update: <span id="last-update">Never</span>
        </div>

        <div class="setup-instructions">
            <h2>📋 Quick Setup</h2>
            <p>To see metrics, expose them in your AI apps:</p>
            <pre><code>from hive_performance import start_metrics_server

# In ai-reviewer
start_metrics_server(port=8001)

# In ai-planner
start_metrics_server(port=8002)

# In ai-deployer
start_metrics_server(port=8003)</code></pre>

            <p style="margin-top: 16px;"><strong>Or test with sample data:</strong></p>
            <pre><code>python scripts/monitoring/generate_test_metrics.py</code></pre>
        </div>
    </div>
</body>
</html>
"""


@app.route("/")
def index():
    """Serve the dashboard HTML."""
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/metrics")
def get_metrics():
    """Fetch metrics from all AI apps."""
    metrics = {}

    for app_name, endpoint in METRICS_ENDPOINTS.items():
        try:
            response = requests.get(endpoint, timeout=2)
            if response.status_code == 200:
                # Parse Prometheus metrics
                parsed = parse_prometheus_metrics(response.text)
                metrics[app_name] = {
                    "online": True,
                    "data": parsed,
                }
            else:
                metrics[app_name] = {"online": False}
        except requests.RequestException:
            metrics[app_name] = {"online": False}

    return jsonify(metrics)


def parse_prometheus_metrics(text: str) -> dict[str, Any]:
    """Parse Prometheus text format into key metrics."""
    metrics = {}

    for line in text.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        try:
            # Simple parsing for key metrics
            if 'adapter_claude' in line and 'duration' in line:
                if 'sum' in line:
                    parts = line.split()
                    value = float(parts[-1])
                    metrics['Claude Total Time (s)'] = f"{value:.2f}"

            elif 'calls_total' in line and 'success' in line:
                parts = line.split()
                value = float(parts[-1])
                if 'deployment' in line:
                    metrics['Deployments'] = int(value)
                elif 'planning' in line:
                    metrics['Plans Generated'] = int(value)
                elif 'review' in line:
                    metrics['Reviews Complete'] = int(value)

            elif 'error' in line and '_total' in line:
                parts = line.split()
                value = float(parts[-1])
                if value > 0:
                    metrics['Errors'] = int(value)

        except (ValueError, IndexError):
            continue

    if not metrics:
        metrics['Status'] = 'No data yet - run some tasks!'

    return metrics


if __name__ == "__main__":
    print("=" * 60)
    print("Hive AI Apps - Simple Metrics Viewer")
    print("=" * 60)
    print()
    print("Dashboard: http://localhost:5000")
    print()
    print("Monitoring endpoints:")
    print("   - ai-reviewer:  http://localhost:8001/metrics")
    print("   - ai-planner:   http://localhost:8002/metrics")
    print("   - ai-deployer:  http://localhost:8003/metrics")
    print()
    print("Tip: Start your AI apps with metrics enabled to see data")
    print()
    print("Press Ctrl+C to stop")
    print("=" * 60)
    print()

    app.run(host="0.0.0.0", port=5000, debug=False)
