#!/usr/bin/env python3
"""Production Shield Monitor

Proactive monitoring system for production and staging environments:
- Health endpoint monitoring with intelligent alerting
- Response time tracking and performance analysis
- Automated incident detection and reporting
- Service availability metrics and trends

Part of the Production Shield Initiative for end-to-end operational excellence.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from pydantic import BaseModel, HttpUrl, ValidationError


class ServiceEndpoint(BaseModel):
    """Configuration for a monitored service endpoint"""

    name: str
    url: HttpUrl
    environment: str  # production, staging, development
    timeout_seconds: int = 30
    expected_status: int = 200
    health_check_path: str = "/health"
    status_check_path: str = "/status"
    critical: bool = True  # Whether failures should trigger incidents


class MonitoringResult(BaseModel):
    """Result of monitoring a single endpoint"""

    service_name: str
    endpoint: str
    environment: str
    status_code: int | None = None
    response_time_ms: float | None = None
    is_healthy: bool = False
    error_message: str | None = None
    timestamp: str
    response_body: str | None = None


class ProductionMonitor:
    def __init__(self, config_path: Path | None = None):
        self.config_path = config_path or Path("production_monitoring_config.json")
        self.endpoints: list[ServiceEndpoint] = []
        self.results: list[MonitoringResult] = []
        self.load_configuration()

    def load_configuration(self) -> None:
        """Load monitoring configuration from environment and config files"""
        # Load from environment variables (for GitHub Actions)
        production_endpoints = os.getenv("PRODUCTION_ENDPOINTS")
        staging_endpoints = os.getenv("STAGING_ENDPOINTS")

        if production_endpoints:
            try:
                prod_config = json.loads(production_endpoints)
                for endpoint_config in prod_config:
                    endpoint_config["environment"] = "production"
                    self.endpoints.append(ServiceEndpoint(**endpoint_config))
            except (json.JSONDecodeError, ValidationError) as e:
                print(f"Error loading production endpoints: {e}")

        if staging_endpoints:
            try:
                staging_config = json.loads(staging_endpoints)
                for endpoint_config in staging_config:
                    endpoint_config["environment"] = "staging"
                    self.endpoints.append(ServiceEndpoint(**endpoint_config))
            except (json.JSONDecodeError, ValidationError) as e:
                print(f"Error loading staging endpoints: {e}")

        # Load from local config file if available
        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    config_data = json.load(f)

                for endpoint_config in config_data.get("endpoints", []):
                    self.endpoints.append(ServiceEndpoint(**endpoint_config))
            except (json.JSONDecodeError, ValidationError) as e:
                print(f"Error loading config file: {e}")

        # Default configuration for development/testing
        if not self.endpoints:
            self.load_default_configuration()

    def load_default_configuration(self) -> None:
        """Load default configuration for testing

        Note: Only loads localhost endpoints if ALLOW_DEFAULT_CONFIG env var is set.
        This prevents false failures in CI environments where services aren't running.
        """
        allow_defaults = os.getenv("ALLOW_DEFAULT_CONFIG", "false").lower() == "true"

        if not allow_defaults:
            print("No endpoints configured and ALLOW_DEFAULT_CONFIG not set to 'true'.")
            print("Skipping default localhost configuration to prevent false failures.")
            print("\nTo enable monitoring:")
            print("  1. Set PRODUCTION_ENDPOINTS or STAGING_ENDPOINTS environment variables, OR")
            print("  2. Create production_monitoring_config.json, OR")
            print("  3. Set ALLOW_DEFAULT_CONFIG=true for local development")
            return

        default_endpoints = [
            {
                "name": "Hive Orchestrator API",
                "url": "http://localhost:8000",
                "environment": "development",
                "health_check_path": "/health",
                "status_check_path": "/status",
                "critical": True,
            },
            {
                "name": "EcoSystemiser API",
                "url": "http://localhost:8001",
                "environment": "development",
                "health_check_path": "/health",
                "status_check_path": "/api/health",
                "critical": True,
            },
            {
                "name": "Event Dashboard",
                "url": "http://localhost:8002",
                "environment": "development",
                "health_check_path": "/health",
                "critical": False,
            },
        ]

        for endpoint_config in default_endpoints:
            try:
                self.endpoints.append(ServiceEndpoint(**endpoint_config))
            except ValidationError as e:
                print(f"Error in default config: {e}")

    def check_endpoint_health(self, endpoint: ServiceEndpoint) -> MonitoringResult:
        """Check the health of a single endpoint"""
        timestamp = datetime.now().isoformat()

        # Try health check endpoint first
        health_url = f"{endpoint.url.rstrip('/')}{endpoint.health_check_path}"

        result = MonitoringResult(
            service_name=endpoint.name,
            endpoint=health_url,
            environment=endpoint.environment,
            timestamp=timestamp,
        )

        try:
            start_time = time.time()
            response = requests.get(
                health_url,
                timeout=endpoint.timeout_seconds,
                headers={"User-Agent": "ProductionShield/1.0"},
            )
            end_time = time.time()

            result.status_code = response.status_code
            result.response_time_ms = (end_time - start_time) * 1000
            result.response_body = response.text[:500]  # First 500 chars

            # Check if response indicates healthy status
            if response.status_code == endpoint.expected_status:
                # Additional health checks based on response content
                response_text = response.text.lower()

                # Common health check patterns
                if any(pattern in response_text for pattern in ["healthy", "ok", "up", "running"]):
                    result.is_healthy = True
                elif any(pattern in response_text for pattern in ["unhealthy", "down", "error", "failed"]):
                    result.is_healthy = False
                    result.error_message = f"Service reports unhealthy status: {response.text[:100]}"
                else:
                    # If no explicit health indicators, assume healthy if status is correct
                    result.is_healthy = True
            else:
                result.is_healthy = False
                result.error_message = f"HTTP {response.status_code}: {response.reason}"

        except requests.exceptions.Timeout:
            result.error_message = f"Timeout after {endpoint.timeout_seconds} seconds"
            result.is_healthy = False

        except requests.exceptions.ConnectionError:
            result.error_message = "Connection failed - service may be down"
            result.is_healthy = False

        except requests.exceptions.RequestException as e:
            result.error_message = f"Request failed: {e!s}"
            result.is_healthy = False

        except Exception as e:
            result.error_message = f"Unexpected error: {e!s}"
            result.is_healthy = False

        return result

    def monitor_all_endpoints(self, environment_filter: str = "all") -> None:
        """Monitor all configured endpoints"""
        print(f"🛡️ Production Shield Monitoring - {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print("=" * 80)

        endpoints_to_monitor = self.endpoints

        if environment_filter != "all":
            endpoints_to_monitor = [ep for ep in self.endpoints if ep.environment == environment_filter]

        if not endpoints_to_monitor:
            print(f"⚠️  No endpoints configured for environment: {environment_filter}")
            print("Monitoring skipped - this is expected in CI environments without services running.")
            return

        print(f"Monitoring {len(endpoints_to_monitor)} endpoints in {environment_filter} environment(s)")
        print()

        for endpoint in endpoints_to_monitor:
            print(f"Checking {endpoint.name} ({endpoint.environment})...")
            result = self.check_endpoint_health(endpoint)
            self.results.append(result)

            # Print immediate status
            status_emoji = "✅" if result.is_healthy else "❌"
            response_time = f"{result.response_time_ms:.0f}ms" if result.response_time_ms else "N/A"

            print(f"  {status_emoji} {endpoint.name}: {result.status_code or 'FAIL'} ({response_time})")

            if not result.is_healthy and result.error_message:
                print(f"     Error: {result.error_message}")

            print()

    def analyze_results(self) -> dict:
        """Analyze monitoring results and generate summary"""
        total_endpoints = len(self.results)
        healthy_count = sum(1 for r in self.results if r.is_healthy)
        failed_count = total_endpoints - healthy_count
        success_rate = (healthy_count / total_endpoints * 100) if total_endpoints > 0 else 0

        failures = [r for r in self.results if not r.is_healthy]
        critical_failures = [r for r in failures if self._is_critical_service(r.service_name)]

        # Calculate average response time for healthy services
        healthy_response_times = [
            r.response_time_ms for r in self.results if r.is_healthy and r.response_time_ms is not None
        ]
        avg_response_time = sum(healthy_response_times) / len(healthy_response_times) if healthy_response_times else 0

        analysis = {
            "timestamp": datetime.now().isoformat(),
            "total_endpoints": total_endpoints,
            "healthy_count": healthy_count,
            "failed_count": failed_count,
            "success_rate": round(success_rate, 2),
            "avg_response_time_ms": round(avg_response_time, 2),
            "failures": [
                {
                    "service_name": f.service_name,
                    "endpoint": f.endpoint,
                    "environment": f.environment,
                    "status_code": f.status_code,
                    "response_time_ms": f.response_time_ms,
                    "error_message": f.error_message,
                    "timestamp": f.timestamp,
                    "is_critical": self._is_critical_service(f.service_name),
                }
                for f in failures
            ],
            "critical_failures": len(critical_failures),
            "has_failures": failed_count > 0,
            "all_healthy": failed_count == 0,
        }

        return analysis

    def _is_critical_service(self, service_name: str) -> bool:
        """Check if a service is marked as critical"""
        for endpoint in self.endpoints:
            if endpoint.name == service_name:
                return endpoint.critical
        return True  # Default to critical if not found

    def generate_monitoring_report(self, analysis: dict) -> str:
        """Generate detailed monitoring report"""
        report_lines = []

        # Header
        report_lines.extend(
            [
                "# 🛡️ Production Shield Monitoring Report",
                "",
                f"**Monitoring Time**: {analysis['timestamp']}",
                "**Environment**: All monitored environments",
                "",
                "## 📊 Health Summary",
                "",
                f"- **Total Services**: {analysis['total_endpoints']}",
                f"- **Healthy Services**: {analysis['healthy_count']}",
                f"- **Failed Services**: {analysis['failed_count']}",
                f"- **Success Rate**: {analysis['success_rate']}%",
                f"- **Average Response Time**: {analysis['avg_response_time_ms']}ms",
                "",
            ],
        )

        # Service Status Details
        if self.results:
            report_lines.extend(["## 🔍 Service Status Details", ""])

            # Group by environment
            by_environment = {}
            for result in self.results:
                env = result.environment
                if env not in by_environment:
                    by_environment[env] = []
                by_environment[env].append(result)

            for env, results in by_environment.items():
                report_lines.append(f"### {env.title()} Environment")
                report_lines.append("")

                for result in results:
                    status_emoji = "✅" if result.is_healthy else "❌"
                    response_time = f"{result.response_time_ms:.0f}ms" if result.response_time_ms else "N/A"
                    status_code = result.status_code or "FAIL"

                    report_lines.append(f"{status_emoji} **{result.service_name}**: {status_code} ({response_time})")

                    if not result.is_healthy and result.error_message:
                        report_lines.append(f"   *Error*: {result.error_message}")

                report_lines.append("")

        # Failures Section
        if analysis["failures"]:
            report_lines.extend(["## 🚨 Failure Analysis", ""])

            critical_failures = [f for f in analysis["failures"] if f["is_critical"]]
            non_critical_failures = [f for f in analysis["failures"] if not f["is_critical"]]

            if critical_failures:
                report_lines.extend(["### 🔴 Critical Service Failures", ""])

                for failure in critical_failures:
                    report_lines.extend(
                        [
                            f"**{failure['service_name']}** ({failure['environment']})",
                            f"- Endpoint: `{failure['endpoint']}`",
                            f"- Status: {failure['status_code'] or 'Connection Failed'}",
                            f"- Error: {failure['error_message']}",
                            f"- Time: {failure['timestamp']}",
                            "",
                        ],
                    )

            if non_critical_failures:
                report_lines.extend(["### 🟡 Non-Critical Service Failures", ""])

                for failure in non_critical_failures:
                    report_lines.extend(
                        [
                            f"**{failure['service_name']}** ({failure['environment']})",
                            f"- Error: {failure['error_message']}",
                            "",
                        ],
                    )

        # Recommendations
        if analysis["failures"]:
            report_lines.extend(["## 🎯 Recommended Actions", ""])

            if analysis["critical_failures"] > 0:
                report_lines.extend(
                    [
                        "### Immediate Actions (Critical)",
                        "1. **Investigate critical service failures** immediately",
                        "2. **Check infrastructure status** (servers, databases, load balancers)",
                        "3. **Review application logs** for error patterns",
                        "4. **Verify network connectivity** and DNS resolution",
                        "",
                    ],
                )

            report_lines.extend(
                [
                    "### Follow-up Actions",
                    "1. **Monitor trends** - are failures increasing?",
                    "2. **Review deployment history** - recent changes?",
                    "3. **Check resource utilization** - CPU, memory, disk",
                    "4. **Update monitoring configuration** if needed",
                    "",
                ],
            )
        else:
            report_lines.extend(
                [
                    "## ✅ All Systems Healthy",
                    "",
                    "All monitored services are responding normally. Continue monitoring for trends and performance.",
                    "",
                ],
            )

        # Next Steps
        report_lines.extend(
            [
                "---",
                "",
                "*This report is generated automatically every 5 minutes by Production Shield Monitoring.*",
                "*For immediate alerts, check GitHub issues with the 'incident' label.*",
            ],
        )

        return "\n".join(report_lines)

    def save_results(self, analysis: dict) -> None:
        """Save monitoring results for GitHub Actions"""
        # Save JSON results for GitHub Actions
        results_path = Path("production_monitoring_results.json")
        with open(results_path, "w") as f:
            json.dump(analysis, f, indent=2)

        # Save detailed report
        report = self.generate_monitoring_report(analysis)
        report_path = Path("production_monitoring_report.md")
        with open(report_path, "w") as f:
            f.write(report)

        # Set GitHub Actions outputs
        if os.getenv("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(f"has_failures={'true' if analysis['has_failures'] else 'false'}\n")
                f.write(f"all_healthy={'true' if analysis['all_healthy'] else 'false'}\n")
                f.write(f"critical_failures={analysis['critical_failures']}\n")
                f.write(f"success_rate={analysis['success_rate']}\n")

        print(f"Results saved to: {results_path}")
        print(f"Report saved to: {report_path}")


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description="Production Shield Monitor")
    parser.add_argument(
        "--environment",
        choices=["all", "production", "staging", "development"],
        default="all",
        help="Environment to monitor",
    )
    parser.add_argument("--config", type=Path, help="Path to monitoring configuration file")
    parser.add_argument(
        "--create-incidents",
        action="store_true",
        help="Create GitHub issues for incidents (requires GITHUB_TOKEN)",
    )
    parser.add_argument(
        "--output-format",
        choices=["console", "json", "markdown"],
        default="console",
        help="Output format",
    )

    args = parser.parse_args()

    try:
        monitor = ProductionMonitor(args.config)
        monitor.monitor_all_endpoints(args.environment)

        # Exit cleanly if no endpoints were configured (e.g., in CI without services)
        if not monitor.results:
            print("\n✅ Monitoring skipped - no endpoints configured")
            return 0

        analysis = monitor.analyze_results()

        if args.output_format == "json":
            print(json.dumps(analysis, indent=2))
        elif args.output_format == "markdown":
            report = monitor.generate_monitoring_report(analysis)
            print(report)
        else:
            # Console output (default)
            print("\n" + "=" * 80)
            print("📊 MONITORING SUMMARY")
            print("=" * 80)
            print(f"Success Rate: {analysis['success_rate']}%")
            print(f"Healthy: {analysis['healthy_count']}/{analysis['total_endpoints']}")
            print(f"Average Response Time: {analysis['avg_response_time_ms']}ms")

            if analysis["failures"]:
                print(f"\n❌ {len(analysis['failures'])} service(s) failed:")
                for failure in analysis["failures"]:
                    print(f"  - {failure['service_name']}: {failure['error_message']}")
            else:
                print("\n✅ All services healthy!")

        # Save results for GitHub Actions integration
        monitor.save_results(analysis)

        # Exit with error code if critical services are down
        if analysis["critical_failures"] > 0:
            print(f"\n🚨 {analysis['critical_failures']} critical service(s) are down!")
            return 1

        return 0

    except Exception as e:
        print(f"Monitoring failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
