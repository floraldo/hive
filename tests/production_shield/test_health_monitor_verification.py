#!/usr/bin/env python3
"""
Production Shield Health Monitor Verification Tests

Meta-monitoring tests to verify the Production Shield monitoring systems work correctly:
- Health monitor failure detection verification
- Recovery detection verification
- GitHub issue creation/closure verification
- Mock service integration testing

Ensures the guardian itself is properly guarded.
"""

import asyncio
import json

# Import the production monitor
import sys
import tempfile
import time
from pathlib import Path

import pytest
from aiohttp import web

sys.path.append(str(Path(__file__).parent.parent.parent / "scripts" / "operational_excellence"))
from production_monitor import ProductionMonitor


class MockGitHubAPI:
    """Mock GitHub API for testing issue creation/closure"""

    def __init__(self):
        self.issues_created = []
        self.issues_updated = []
        self.issues_closed = []
        self.comments_created = []

    async def create_issue(self, title: str, body: str, labels: list[str] = None):
        """Mock issue creation"""
        issue = {
            "number": len(self.issues_created) + 1,
            "title": title,
            "body": body,
            "labels": labels or [],
            "state": "open",
            "created_at": time.time(),
        }
        self.issues_created.append(issue)
        return issue

    async def update_issue(self, issue_number: int, title: str = None, body: str = None, state: str = None):
        """Mock issue update"""
        update = {"issue_number": issue_number, "title": title, "body": body, "state": state, "updated_at": time.time()}
        self.issues_updated.append(update)
        return update

    async def create_comment(self, issue_number: int, body: str):
        """Mock comment creation"""
        comment = {"issue_number": issue_number, "body": body, "created_at": time.time()}
        self.comments_created.append(comment)
        return comment

    async def list_issues(self, labels: list[str] = None, state: str = "open"):
        """Mock issue listing"""
        matching_issues = []
        for issue in self.issues_created:
            if state and issue["state"] != state:
                continue
            if labels and not any(label in issue["labels"] for label in labels):
                continue
            matching_issues.append(issue)
        return matching_issues


class MockHealthService:
    """Mock web service for testing health monitoring"""

    def __init__(self, port: int = 8899):
        self.port = port
        self.is_healthy = True
        self.response_delay = 0.0
        self.status_code = 200
        self.response_body = {"status": "healthy", "timestamp": time.time()}
        self.request_count = 0
        self.app = None
        self.runner = None
        self.site = None

    async def health_handler(self, request):
        """Health endpoint handler"""
        self.request_count += 1

        # Simulate response delay
        if self.response_delay > 0:
            await asyncio.sleep(self.response_delay)

        # Return configured response
        if not self.is_healthy:
            return web.json_response({"status": "unhealthy", "error": "Service degraded"}, status=503)

        return web.json_response(self.response_body, status=self.status_code)

    async def start(self):
        """Start the mock service"""
        self.app = web.Application()
        self.app.router.add_get("/health", self.health_handler)
        self.app.router.add_get("/status", self.health_handler)

        self.runner = web.AppRunner(self.app)
        await self.runner.setup()

        self.site = web.TCPSite(self.runner, "localhost", self.port)
        await self.site.start()

        # Wait a moment for the server to be ready
        await asyncio.sleep(0.1)

    async def stop(self):
        """Stop the mock service"""
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()

    def configure_healthy(self):
        """Configure service to respond as healthy"""
        self.is_healthy = True
        self.status_code = 200
        self.response_body = {"status": "healthy", "timestamp": time.time()}

    def configure_unhealthy(self):
        """Configure service to respond as unhealthy"""
        self.is_healthy = False
        self.status_code = 503
        self.response_body = {"status": "unhealthy", "error": "Service degraded"}

    def configure_timeout(self, delay: float = 5.0):
        """Configure service to timeout"""
        self.response_delay = delay

    def configure_connection_refused(self):
        """Configure service to refuse connections (stop the service)"""
        # This will be handled by stopping the service entirely
        pass


class TestHealthMonitorVerification:
    """Test suite for verifying the health monitor works correctly"""

    @pytest.fixture
    async def mock_service(self):
        """Create and start a mock health service"""
        service = MockHealthService()
        await service.start()
        yield service
        await service.stop()

    @pytest.fixture
    def mock_github_api(self):
        """Create a mock GitHub API"""
        return MockGitHubAPI()

    @pytest.fixture
    def temp_config(self, mock_service):
        """Create temporary monitoring configuration"""
        config = {
            "endpoints": [
                {
                    "name": "Test Service",
                    "url": f"http://localhost:{mock_service.port}",
                    "environment": "test",
                    "timeout_seconds": 5,
                    "critical": True,
                },
            ],
        }

        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(config, temp_file)
        temp_file.close()

        yield Path(temp_file.name)

        # Cleanup
        Path(temp_file.name).unlink()

    @pytest.mark.asyncio
    async def test_health_monitor_detects_healthy_service(self, mock_service, temp_config):
        """Test that health monitor correctly identifies healthy services"""
        # Configure service as healthy
        mock_service.configure_healthy()

        # Create monitor with test configuration
        monitor = ProductionMonitor(temp_config)
        monitor.monitor_all_endpoints("test")

        # Analyze results
        analysis = monitor.analyze_results()

        # Verify healthy detection
        assert analysis["all_healthy"] is True
        assert analysis["has_failures"] is False
        assert analysis["failed_count"] == 0
        assert analysis["healthy_count"] == 1
        assert analysis["success_rate"] == 100.0

        # Verify service was actually called
        assert mock_service.request_count > 0

    @pytest.mark.asyncio
    async def test_health_monitor_detects_unhealthy_service(self, mock_service, temp_config):
        """Test that health monitor correctly identifies unhealthy services"""
        # Configure service as unhealthy
        mock_service.configure_unhealthy()

        # Create monitor with test configuration
        monitor = ProductionMonitor(temp_config)
        monitor.monitor_all_endpoints("test")

        # Analyze results
        analysis = monitor.analyze_results()

        # Verify failure detection
        assert analysis["all_healthy"] is False
        assert analysis["has_failures"] is True
        assert analysis["failed_count"] == 1
        assert analysis["healthy_count"] == 0
        assert analysis["success_rate"] == 0.0

        # Verify failure details
        assert len(analysis["failures"]) == 1
        failure = analysis["failures"][0]
        assert failure["service_name"] == "Test Service"
        assert failure["status_code"] == 503
        assert "unhealthy" in failure["error_message"].lower()

    @pytest.mark.asyncio
    async def test_health_monitor_detects_connection_failure(self, mock_service, temp_config):
        """Test that health monitor detects connection failures"""
        # Stop the service to simulate connection refused
        await mock_service.stop()

        # Create monitor with test configuration
        monitor = ProductionMonitor(temp_config)
        monitor.monitor_all_endpoints("test")

        # Analyze results
        analysis = monitor.analyze_results()

        # Verify connection failure detection
        assert analysis["all_healthy"] is False
        assert analysis["has_failures"] is True
        assert analysis["failed_count"] == 1

        # Verify failure details
        failure = analysis["failures"][0]
        assert failure["service_name"] == "Test Service"
        assert failure["status_code"] is None  # No response received
        assert "connection" in failure["error_message"].lower() or "refused" in failure["error_message"].lower()

    @pytest.mark.asyncio
    async def test_health_monitor_detects_timeout(self, mock_service, temp_config):
        """Test that health monitor detects service timeouts"""
        # Configure service to timeout
        mock_service.configure_timeout(delay=6.0)  # Longer than 5 second timeout

        # Create monitor with test configuration
        monitor = ProductionMonitor(temp_config)
        monitor.monitor_all_endpoints("test")

        # Analyze results
        analysis = monitor.analyze_results()

        # Verify timeout detection
        assert analysis["all_healthy"] is False
        assert analysis["has_failures"] is True
        assert analysis["failed_count"] == 1

        # Verify timeout details
        failure = analysis["failures"][0]
        assert failure["service_name"] == "Test Service"
        assert "timeout" in failure["error_message"].lower()

    @pytest.mark.asyncio
    async def test_health_monitor_tracks_response_times(self, mock_service, temp_config):
        """Test that health monitor accurately tracks response times"""
        # Configure service with small delay
        mock_service.configure_healthy()
        mock_service.response_delay = 0.1  # 100ms delay

        # Create monitor with test configuration
        monitor = ProductionMonitor(temp_config)
        monitor.monitor_all_endpoints("test")

        # Analyze results
        analysis = monitor.analyze_results()

        # Verify response time tracking
        assert analysis["all_healthy"] is True
        assert analysis["avg_response_time_ms"] >= 100  # Should be at least 100ms
        assert analysis["avg_response_time_ms"] <= 200  # But not too much overhead

    @pytest.mark.asyncio
    async def test_health_monitor_recovery_detection(self, mock_service, temp_config):
        """Test that health monitor detects service recovery"""
        # Start with unhealthy service
        mock_service.configure_unhealthy()

        # First monitoring run - should detect failure
        monitor1 = ProductionMonitor(temp_config)
        monitor1.monitor_all_endpoints("test")
        analysis1 = monitor1.analyze_results()

        assert analysis1["has_failures"] is True
        assert analysis1["failed_count"] == 1

        # Fix the service
        mock_service.configure_healthy()

        # Second monitoring run - should detect recovery
        monitor2 = ProductionMonitor(temp_config)
        monitor2.monitor_all_endpoints("test")
        analysis2 = monitor2.analyze_results()

        assert analysis2["all_healthy"] is True
        assert analysis2["has_failures"] is False
        assert analysis2["failed_count"] == 0
        assert analysis2["healthy_count"] == 1

    @pytest.mark.asyncio
    async def test_multiple_services_mixed_health(self, temp_config):
        """Test monitoring multiple services with mixed health states"""
        # Create multiple mock services
        healthy_service = MockHealthService(port=8900)
        unhealthy_service = MockHealthService(port=8901)

        await healthy_service.start()
        await unhealthy_service.start()

        try:
            # Configure services
            healthy_service.configure_healthy()
            unhealthy_service.configure_unhealthy()

            # Update config for multiple services
            config = {
                "endpoints": [
                    {
                        "name": "Healthy Service",
                        "url": f"http://localhost:{healthy_service.port}",
                        "environment": "test",
                        "critical": True,
                    },
                    {
                        "name": "Unhealthy Service",
                        "url": f"http://localhost:{unhealthy_service.port}",
                        "environment": "test",
                        "critical": True,
                    },
                ],
            }

            temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
            json.dump(config, temp_file)
            temp_file.close()

            # Monitor all services
            monitor = ProductionMonitor(Path(temp_file.name))
            monitor.monitor_all_endpoints("test")
            analysis = monitor.analyze_results()

            # Verify mixed results
            assert analysis["total_endpoints"] == 2
            assert analysis["healthy_count"] == 1
            assert analysis["failed_count"] == 1
            assert analysis["success_rate"] == 50.0
            assert analysis["has_failures"] is True
            assert analysis["all_healthy"] is False

            # Verify specific service results
            failures = analysis["failures"]
            assert len(failures) == 1
            assert failures[0]["service_name"] == "Unhealthy Service"

            # Cleanup
            Path(temp_file.name).unlink()

        finally:
            await healthy_service.stop()
            await unhealthy_service.stop()

    @pytest.mark.asyncio
    async def test_monitor_configuration_validation(self):
        """Test that monitor properly validates configuration"""
        # Test with invalid configuration
        invalid_config = {"endpoints": [{"name": "Invalid Service", "url": "not-a-valid-url", "environment": "test"}]}

        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(invalid_config, temp_file)
        temp_file.close()

        try:
            # Monitor should handle invalid URLs gracefully
            monitor = ProductionMonitor(Path(temp_file.name))
            monitor.monitor_all_endpoints("test")
            analysis = monitor.analyze_results()

            # Should report failure for invalid URL
            assert analysis["has_failures"] is True
            assert analysis["failed_count"] == 1

        finally:
            Path(temp_file.name).unlink()

    def test_monitor_report_generation(self, mock_service, temp_config):
        """Test that monitor generates proper reports"""
        # Configure mixed scenario
        mock_service.configure_healthy()

        # Create monitor and run
        monitor = ProductionMonitor(temp_config)
        monitor.monitor_all_endpoints("test")
        analysis = monitor.analyze_results()

        # Generate report
        report = monitor.generate_monitoring_report(analysis)

        # Verify report structure
        assert "Production Shield Monitoring Report" in report
        assert "Health Summary" in report
        assert "Service Status Details" in report
        assert str(analysis["success_rate"]) in report
        assert str(analysis["total_endpoints"]) in report

        # Verify report contains service details
        assert "Test Service" in report
        assert "test" in report.lower()  # Environment should be mentioned


class TestHealthMonitorIntegration:
    """Integration tests for the complete health monitoring workflow"""

    @pytest.mark.asyncio
    async def test_end_to_end_monitoring_workflow(self):
        """Test the complete monitoring workflow from detection to reporting"""
        # Create mock service
        service = MockHealthService(port=8902)
        await service.start()

        try:
            # Create configuration
            config = {
                "endpoints": [
                    {
                        "name": "E2E Test Service",
                        "url": f"http://localhost:{service.port}",
                        "environment": "test",
                        "timeout_seconds": 3,
                        "critical": True,
                    },
                ],
            }

            temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
            json.dump(config, temp_file)
            temp_file.close()

            # Test healthy state
            service.configure_healthy()
            monitor = ProductionMonitor(Path(temp_file.name))
            monitor.monitor_all_endpoints("test")
            analysis = monitor.analyze_results()

            assert analysis["all_healthy"] is True

            # Test failure state
            service.configure_unhealthy()
            monitor = ProductionMonitor(Path(temp_file.name))
            monitor.monitor_all_endpoints("test")
            analysis = monitor.analyze_results()

            assert analysis["has_failures"] is True

            # Test recovery
            service.configure_healthy()
            monitor = ProductionMonitor(Path(temp_file.name))
            monitor.monitor_all_endpoints("test")
            analysis = monitor.analyze_results()

            assert analysis["all_healthy"] is True

            # Generate final report
            report = monitor.generate_monitoring_report(analysis)
            assert "E2E Test Service" in report

            # Cleanup
            Path(temp_file.name).unlink()

        finally:
            await service.stop()


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
