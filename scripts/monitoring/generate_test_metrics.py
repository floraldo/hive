#!/usr/bin/env python3
"""Generate test metrics servers for dashboard demo.

Creates simple HTTP servers that return Prometheus-format metrics
to populate the dashboard with realistic test data.
"""

import http.server
import random
import socketserver
import sys
import threading
import time


def generate_metrics(app_name: str) -> str:
    """Generate Prometheus format metrics for an AI app."""
    timestamp = int(time.time() * 1000)

    # Base metrics that all apps share
    metrics = [
        "# HELP http_requests_total Total HTTP requests",
        "# TYPE http_requests_total counter",
        f'http_requests_total{{app="{app_name}",status="success"}} {random.randint(100, 500)}',
        f'http_requests_total{{app="{app_name}",status="error"}} {random.randint(0, 10)}',
        "",
        "# HELP http_request_duration_seconds HTTP request latencies in seconds",
        "# TYPE http_request_duration_seconds summary",
        f'http_request_duration_seconds{{app="{app_name}",quantile="0.5"}} {random.uniform(0.1, 0.5):.3f}',
        f'http_request_duration_seconds{{app="{app_name}",quantile="0.95"}} {random.uniform(0.5, 2.0):.3f}',
        f'http_request_duration_seconds_sum{{app="{app_name}"}} {random.uniform(50, 200):.2f}',
        f'http_request_duration_seconds_count{{app="{app_name}"}} {random.randint(100, 500)}',
        "",
    ]

    # App-specific metrics
    if app_name == "ai-reviewer":
        metrics.extend([
            "# HELP reviews_completed_total Total reviews completed",
            "# TYPE reviews_completed_total counter",
            f'reviews_completed_total{{app="{app_name}",decision="approved"}} {random.randint(50, 150)}',
            f'reviews_completed_total{{app="{app_name}",decision="rejected"}} {random.randint(5, 20)}',
            "",
            "# HELP adapter_claude_request_duration_seconds Claude API request duration",
            "# TYPE adapter_claude_request_duration_seconds summary",
            f'adapter_claude_request_duration_seconds_sum{{app="{app_name}"}} {random.uniform(20, 80):.2f}',
            f'adapter_claude_request_duration_seconds_count{{app="{app_name}"}} {random.randint(50, 150)}',
            "",
            "# HELP review_latency_seconds Review processing time",
            "# TYPE review_latency_seconds histogram",
            f'review_latency_seconds_sum{{app="{app_name}"}} {random.uniform(100, 300):.2f}',
            f'review_latency_seconds_count{{app="{app_name}"}} {random.randint(50, 150)}',
        ])

    elif app_name == "ai-planner":
        metrics.extend([
            "# HELP plans_generated_total Total plans generated",
            "# TYPE plans_generated_total counter",
            f'plans_generated_total{{app="{app_name}",status="success"}} {random.randint(30, 100)}',
            "",
            "# HELP adapter_claude_request_duration_seconds Claude API request duration",
            "# TYPE adapter_claude_request_duration_seconds summary",
            f'adapter_claude_request_duration_seconds_sum{{app="{app_name}"}} {random.uniform(15, 60):.2f}',
            f'adapter_claude_request_duration_seconds_count{{app="{app_name}"}} {random.randint(30, 100)}',
            "",
            "# HELP plan_generation_latency_seconds Plan generation time",
            "# TYPE plan_generation_latency_seconds histogram",
            f'plan_generation_latency_seconds_sum{{app="{app_name}"}} {random.uniform(50, 200):.2f}',
            f'plan_generation_latency_seconds_count{{app="{app_name}"}} {random.randint(30, 100)}',
        ])

    elif app_name == "ai-deployer":
        metrics.extend([
            "# HELP deployments_total Total deployments",
            "# TYPE deployments_total counter",
            f'deployments_total{{app="{app_name}",strategy="blue_green",status="success"}} {random.randint(20, 60)}',
            f'deployments_total{{app="{app_name}",strategy="rolling",status="success"}} {random.randint(10, 40)}',
            f'deployments_total{{app="{app_name}",strategy="blue_green",status="failed"}} {random.randint(0, 5)}',
            "",
            "# HELP deployment_latency_seconds Deployment duration",
            "# TYPE deployment_latency_seconds histogram",
            f'deployment_latency_seconds_sum{{app="{app_name}"}} {random.uniform(100, 400):.2f}',
            f'deployment_latency_seconds_count{{app="{app_name}"}} {random.randint(30, 100)}',
            "",
            "# HELP rollbacks_total Total deployment rollbacks",
            "# TYPE rollbacks_total counter",
            f'rollbacks_total{{app="{app_name}"}} {random.randint(0, 5)}',
        ])

    return "\n".join(metrics)


class MetricsHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler that serves Prometheus metrics."""

    app_name = "unknown"

    def do_GET(self):
        """Handle GET request."""
        if self.path == "/metrics":
            self.send_response(200)
            self.send_header("Content-type", "text/plain; version=0.0.4")
            self.end_headers()
            metrics = generate_metrics(self.app_name)
            self.wfile.write(metrics.encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress request logging."""
        pass


def start_metrics_server(port: int, app_name: str):
    """Start a metrics server on the given port."""

    # Create handler class with app name
    handler_class = type(
        'MetricsHandler',
        (MetricsHandler,),
        {'app_name': app_name}
    )

    try:
        with socketserver.TCPServer(("", port), handler_class) as httpd:
            print(f"[{app_name}] Metrics server started on http://localhost:{port}/metrics")
            httpd.serve_forever()
    except OSError as e:
        print(f"[{app_name}] Failed to start on port {port}: {e}")


def main():
    """Start all three metrics servers."""
    print("=" * 60)
    print("AI Apps Test Metrics Servers")
    print("=" * 60)
    print()
    print("Starting mock metrics servers for dashboard testing...")
    print()
    print("Endpoints:")
    print("  - AI Reviewer:  http://localhost:8001/metrics")
    print("  - AI Planner:   http://localhost:8002/metrics")
    print("  - AI Deployer:  http://localhost:8003/metrics")
    print()
    print("Dashboard:        http://localhost:5000")
    print()
    print("Press Ctrl+C to stop")
    print("=" * 60)
    print()

    # Start each server in its own thread
    servers = [
        ("ai-reviewer", 8001),
        ("ai-planner", 8002),
        ("ai-deployer", 8003),
    ]

    threads = []
    for app_name, port in servers:
        thread = threading.Thread(
            target=start_metrics_server,
            args=(port, app_name),
            daemon=True
        )
        thread.start()
        threads.append(thread)
        time.sleep(0.5)  # Small delay between starts

    print()
    print("All servers running! Generating random metrics...")
    print("Open http://localhost:5000 to view the dashboard")
    print()

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nShutting down servers...")
        sys.exit(0)


if __name__ == "__main__":
    main()
