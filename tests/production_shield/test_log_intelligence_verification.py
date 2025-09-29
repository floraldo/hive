#!/usr/bin/env python3
"""
Production Shield Log Intelligence Verification Tests

Meta-monitoring tests to verify the Log Intelligence system works correctly:
- Synthetic log generation and analysis verification
- Error pattern detection verification
- Trend analysis accuracy verification
- TODO comment extraction verification

Ensures the log analysis guardian is properly validated.
"""

import json

# Import the log intelligence analyzer
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).parent.parent.parent / "scripts" / "operational_excellence"))
from log_intelligence import LogIntelligenceAnalyzer


class SyntheticLogGenerator:
    """Generates synthetic log files with known patterns for testing"""

    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def generate_healthy_logs(self, filename: str = "healthy.log", entry_count: int = 100):
        """Generate logs with mostly healthy entries"""
        log_file = self.log_dir / filename

        with open(log_file, "w") as f:
            base_time = datetime.now() - timedelta(hours=1)

            for i in range(entry_count):
                timestamp = base_time + timedelta(seconds=i * 30)
                timestamp_str = timestamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

                if i % 20 == 0:  # 5% warnings
                    f.write(f"{timestamp_str} [WARNING] Minor issue detected in component {i % 5}\n")
                elif i % 50 == 0:  # 2% errors
                    f.write(f"{timestamp_str} [ERROR] Recoverable error in process {i % 3}\n")
                else:  # 93% info
                    f.write(f"{timestamp_str} [INFO] Processing request {i} successfully\n")

        return log_file

    def generate_error_spike_logs(self, filename: str = "error_spike.log", spike_hour: int = 0):
        """Generate logs with an error spike in a specific hour"""
        log_file = self.log_dir / filename

        with open(log_file, "w") as f:
            base_time = datetime.now() - timedelta(hours=2)

            for hour in range(2):
                for minute in range(60):
                    timestamp = base_time + timedelta(hours=hour, minutes=minute)
                    timestamp_str = timestamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

                    if hour == spike_hour:
                        # Error spike hour - 30% errors
                        if minute % 3 == 0:
                            f.write(f"{timestamp_str} [ERROR] Database connection timeout in service-{minute % 5}\n")
                        elif minute % 5 == 0:
                            f.write(f"{timestamp_str} [WARNING] High memory usage detected\n")
                        else:
                            f.write(f"{timestamp_str} [INFO] Normal operation\n")
                    else:
                        # Normal hour - 5% errors
                        if minute % 20 == 0:
                            f.write(f"{timestamp_str} [ERROR] Minor error in component-{minute % 3}\n")
                        else:
                            f.write(f"{timestamp_str} [INFO] Normal operation\n")

        return log_file

    def generate_critical_pattern_logs(self, filename: str = "critical.log"):
        """Generate logs with critical patterns that should trigger alerts"""
        log_file = self.log_dir / filename

        critical_patterns = [
            "Database connection refused - unable to connect to primary",
            "Out of memory error - heap exhausted, terminating process",
            "Disk full - no space left on device /var/log",
            "Authentication failed for user admin - suspicious activity detected",
            "SSL certificate expired for domain api.example.com",
            "Request timeout exceeded - client waited 30 seconds",
            "HTTP 500 internal server error in payment processing",
            "Deadlock detected in transaction processing",
            "Circuit breaker open for external service integration",
            "Rate limit exceeded - blocking requests from IP 192.168.1.100",
        ]

        with open(log_file, "w") as f:
            base_time = datetime.now() - timedelta(minutes=30)

            for i, pattern in enumerate(critical_patterns):
                timestamp = base_time + timedelta(minutes=i * 3)
                timestamp_str = timestamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                f.write(f"{timestamp_str} [ERROR] {pattern}\n")

                # Add some normal logs between critical ones
                for j in range(2):
                    normal_time = timestamp + timedelta(seconds=30 + j * 30)
                    normal_timestamp = normal_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                    f.write(f"{normal_timestamp} [INFO] Normal operation continuing\n")

        return log_file

    def generate_performance_issue_logs(self, filename: str = "performance.log"):
        """Generate logs with performance-related issues"""
        log_file = self.log_dir / filename

        performance_patterns = [
            "Slow query detected - SELECT took 15 seconds to complete",
            "Response time 8500 ms for endpoint /api/users",
            "Garbage collection took 2000 ms - heap pressure detected",
            "Thread pool exhausted - 200 threads in use",
            "Connection pool exhausted - max 50 connections reached",
        ]

        with open(log_file, "w") as f:
            base_time = datetime.now() - timedelta(minutes=20)

            for i, pattern in enumerate(performance_patterns):
                timestamp = base_time + timedelta(minutes=i * 4)
                timestamp_str = timestamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                f.write(f"{timestamp_str} [WARNING] {pattern}\n")

        return log_file

    def generate_security_alert_logs(self, filename: str = "security.log"):
        """Generate logs with security-related alerts"""
        log_file = self.log_dir / filename

        security_patterns = [
            "Failed login attempt for user admin from IP 192.168.1.50",
            "Suspicious activity detected - multiple failed API calls",
            "SQL injection attempt blocked in user input validation",
            "Brute force attack detected - 50 failed attempts in 5 minutes",
            "Unauthorized API access attempt from unknown client",
        ]

        with open(log_file, "w") as f:
            base_time = datetime.now() - timedelta(minutes=15)

            for i, pattern in enumerate(security_patterns):
                timestamp = base_time + timedelta(minutes=i * 3)
                timestamp_str = timestamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                f.write(f"{timestamp_str} [ERROR] {pattern}\n")

        return log_file

    def generate_todo_comment_code(self, filename: str = "service.py"):
        """Generate Python code with TODO comments for testing"""
        code_file = self.log_dir / filename

        code_content = '''#!/usr/bin/env python3
"""
Sample service with TODO comments for testing
"""

import asyncio
from typing import Dict, List

class SampleService:
    """Sample service implementation"""

    def __init__(self):
        # TODO: Implement proper configuration loading
        self.config = {}

    async def process_request(self, request: Dict) -> Dict:
        """Process incoming request"""
        # FIXME: Add proper input validation here
        if not request:
            return {"error": "Invalid request"}

        # TODO: Implement caching mechanism for better performance
        result = await self._handle_request(request)

        # HACK: Temporary workaround for legacy API compatibility
        if "legacy" in request:
            result = self._convert_to_legacy_format(result)

        return result

    async def _handle_request(self, request: Dict) -> Dict:
        """Handle the actual request processing"""
        # XXX: This method needs refactoring - too complex
        await asyncio.sleep(0.1)  # Simulate processing
        return {"status": "processed", "data": request.get("data", {})}

    def _convert_to_legacy_format(self, data: Dict) -> Dict:
        """Convert response to legacy format"""
        # BUG: This conversion loses precision for floating point numbers
        return {"legacy_data": str(data)}

# TODO: Add comprehensive unit tests for this service
# FIXME: Memory leak in connection pooling needs investigation
'''

        with open(code_file, "w") as f:
            f.write(code_content)

        return code_file


class TestLogIntelligenceVerification:
    """Test suite for verifying log intelligence analysis accuracy"""

    @pytest.fixture
    def temp_log_dir(self):
        """Create temporary directory for test logs"""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir

        # Cleanup
        import shutil

        shutil.rmtree(temp_dir)

    @pytest.fixture
    def log_generator(self, temp_log_dir):
        """Create synthetic log generator"""
        return SyntheticLogGenerator(temp_log_dir)

    def test_healthy_log_analysis(self, log_generator, temp_log_dir):
        """Test analysis of healthy logs produces expected results"""
        # Generate healthy logs
        log_file = log_generator.generate_healthy_logs(entry_count=100)

        # Analyze logs
        analyzer = LogIntelligenceAnalyzer([temp_log_dir])
        analyzer.analyze_logs(hours_back=2, max_files=10)

        # Verify analysis results
        results = analyzer.analysis_results

        assert results["total_entries"] == 100
        assert results["error_count"] == 2  # 2% error rate
        assert results["warning_count"] == 5  # 5% warning rate

        # Should have no critical patterns in healthy logs
        assert len(results["critical_patterns"]) == 0
        assert len(results["security_alerts"]) == 0

        # Should have minimal performance issues
        assert len(results["performance_issues"]) == 0

    def test_error_spike_detection(self, log_generator, temp_log_dir):
        """Test detection of error rate spikes"""
        # Generate logs with error spike in hour 1
        log_file = log_generator.generate_error_spike_logs(spike_hour=1)

        # Analyze logs
        analyzer = LogIntelligenceAnalyzer([temp_log_dir])
        analyzer.analyze_logs(hours_back=3, max_files=10)

        # Verify spike detection
        results = analyzer.analysis_results

        assert results["total_entries"] > 0
        assert results["error_count"] > 10  # Should detect the spike

        # Check error trends
        if "error_trends" in results and results["error_trends"]:
            trends = results["error_trends"]
            # Should detect increase in error rate
            assert "trend_percentage" in trends
            # The exact percentage depends on timing, but should be positive
            assert trends["current_hour_errors"] > 0

    def test_critical_pattern_detection(self, log_generator, temp_log_dir):
        """Test detection of critical error patterns"""
        # Generate logs with critical patterns
        log_file = log_generator.generate_critical_pattern_logs()

        # Analyze logs
        analyzer = LogIntelligenceAnalyzer([temp_log_dir])
        analyzer.analyze_logs(hours_back=1, max_files=10)

        # Verify critical pattern detection
        results = analyzer.analysis_results

        assert len(results["critical_patterns"]) >= 8  # Should detect most patterns

        # Verify specific critical patterns are detected
        detected_patterns = [cp["pattern"] for cp in results["critical_patterns"]]

        expected_patterns = [
            "Database Connection Failure",
            "Memory Exhaustion",
            "Disk Space Critical",
            "Security: Auth Failure",
            "SSL Certificate Issue",
            "Performance: Timeout",
            "HTTP 500 Errors",
            "Database Deadlock",
            "Circuit Breaker Activated",
            "Rate Limiting Triggered",
        ]

        # Should detect at least 7 out of 10 critical patterns
        detected_count = sum(1 for pattern in expected_patterns if pattern in detected_patterns)
        assert detected_count >= 7

    def test_performance_issue_detection(self, log_generator, temp_log_dir):
        """Test detection of performance-related issues"""
        # Generate performance issue logs
        log_file = log_generator.generate_performance_issue_logs()

        # Analyze logs
        analyzer = LogIntelligenceAnalyzer([temp_log_dir])
        analyzer.analyze_logs(hours_back=1, max_files=10)

        # Verify performance issue detection
        results = analyzer.analysis_results

        assert len(results["performance_issues"]) >= 4  # Should detect most issues

        # Verify specific performance patterns
        detected_issues = [pi["issue_type"] for pi in results["performance_issues"]]

        expected_issues = [
            "Slow Database Query",
            "High Response Time",
            "GC Performance Issue",
            "Thread Pool Exhaustion",
            "Connection Pool Exhaustion",
        ]

        detected_count = sum(1 for issue in expected_issues if issue in detected_issues)
        assert detected_count >= 3

    def test_security_alert_detection(self, log_generator, temp_log_dir):
        """Test detection of security-related alerts"""
        # Generate security alert logs
        log_file = log_generator.generate_security_alert_logs()

        # Analyze logs
        analyzer = LogIntelligenceAnalyzer([temp_log_dir])
        analyzer.analyze_logs(hours_back=1, max_files=10)

        # Verify security alert detection
        results = analyzer.analysis_results

        assert len(results["security_alerts"]) >= 4  # Should detect most alerts

        # Verify specific security patterns
        detected_alerts = [sa["alert_type"] for sa in results["security_alerts"]]

        expected_alerts = [
            "Failed Login Attempt",
            "Suspicious Activity",
            "Security: Injection Attempt",
            "Brute Force Attack",
            "Unauthorized API Access",
        ]

        detected_count = sum(1 for alert in expected_alerts if alert in detected_alerts)
        assert detected_count >= 3

    def test_todo_comment_extraction(self, log_generator, temp_log_dir):
        """Test extraction and attribution of TODO comments"""
        # Generate code file with TODO comments
        code_file = log_generator.generate_todo_comment_code()

        # Analyze for TODO comments (using the scan_todo_comments functionality)
        analyzer = LogIntelligenceAnalyzer([temp_log_dir])
        analyzer.scan_todo_comments()

        # Verify TODO comment detection
        results = analyzer.analysis_results

        assert len(results["new_todos"]) >= 5  # Should find multiple TODO comments

        # Verify different types of comments are detected
        comment_types = [todo["type"] for todo in results["new_todos"]]

        expected_types = ["TODO", "FIXME", "HACK", "XXX", "BUG"]
        detected_types = set(comment_types)

        # Should detect at least 3 different types
        assert len(detected_types.intersection(expected_types)) >= 3

        # Verify comments contain meaningful content
        for todo in results["new_todos"]:
            assert len(todo["comment"]) > 10  # Should have substantial content
            assert todo["file"] == "service.py"
            assert todo["line"] > 0

    def test_log_parsing_accuracy(self, log_generator, temp_log_dir):
        """Test accuracy of log line parsing"""
        # Generate logs with various formats
        log_file = temp_log_dir / "mixed_format.log"

        with open(log_file, "w") as f:
            # Different log formats
            f.write("2023-12-01T10:30:45.123Z [ERROR] ISO format error message\n")
            f.write("2023-12-01 10:31:45 WARNING Standard format warning\n")
            f.write("Dec  1 10:32:45 hostname service[1234]: INFO Syslog format info\n")
            f.write("ERROR:module.submodule:Python logging format error\n")
            f.write("[DEBUG] Simple bracket format debug\n")

        # Analyze logs
        analyzer = LogIntelligenceAnalyzer([temp_log_dir])
        analyzer.analyze_logs(hours_back=1, max_files=10)

        # Verify parsing accuracy
        results = analyzer.analysis_results

        assert results["total_entries"] == 5
        assert results["error_count"] == 2  # Two ERROR level entries
        assert results["warning_count"] == 1  # One WARNING entry

        # Verify entries were parsed correctly
        entries = analyzer.log_entries
        assert len(entries) == 5

        # Check specific parsing
        error_entries = [e for e in entries if e.is_error]
        assert len(error_entries) == 2

        warning_entries = [e for e in entries if e.is_warning]
        assert len(warning_entries) == 1

    def test_report_generation_accuracy(self, log_generator, temp_log_dir):
        """Test accuracy of generated reports"""
        # Generate mixed scenario logs
        log_generator.generate_critical_pattern_logs()
        log_generator.generate_performance_issue_logs()
        log_generator.generate_security_alert_logs()

        # Analyze logs
        analyzer = LogIntelligenceAnalyzer([temp_log_dir])
        analyzer.analyze_logs(hours_back=1, max_files=10)

        # Generate report
        report = analyzer.generate_daily_digest()

        # Verify report structure and content
        assert "Daily Log Intelligence Digest" in report
        assert "Executive Summary" in report
        assert "Critical Issues Detected" in report
        assert "Performance Issues" in report
        assert "Security Alerts" in report
        assert "Recommended Actions" in report

        # Verify report contains actual data
        results = analyzer.analysis_results

        if results["critical_patterns"]:
            assert str(len(results["critical_patterns"])) in report

        if results["performance_issues"]:
            assert "Performance Issues" in report

        if results["security_alerts"]:
            assert "Security Alerts" in report

        # Verify recommendations are present
        if results["critical_patterns"] or results["performance_issues"] or results["security_alerts"]:
            assert "Immediate" in report or "High Priority" in report

    def test_trend_analysis_accuracy(self, log_generator, temp_log_dir):
        """Test accuracy of error trend analysis"""
        # Generate logs with clear trend pattern
        log_file = temp_log_dir / "trend_test.log"

        with open(log_file, "w") as f:
            base_time = datetime.now() - timedelta(hours=3)

            # Hour 1: 5 errors
            for i in range(5):
                timestamp = base_time + timedelta(hours=1, minutes=i * 10)
                timestamp_str = timestamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                f.write(f"{timestamp_str} [ERROR] Error {i} in hour 1\n")

            # Hour 2: 10 errors (100% increase)
            for i in range(10):
                timestamp = base_time + timedelta(hours=2, minutes=i * 5)
                timestamp_str = timestamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                f.write(f"{timestamp_str} [ERROR] Error {i} in hour 2\n")

        # Analyze logs
        analyzer = LogIntelligenceAnalyzer([temp_log_dir])
        analyzer.analyze_logs(hours_back=4, max_files=10)

        # Verify trend analysis
        results = analyzer.analysis_results

        if "error_trends" in results and results["error_trends"]:
            trends = results["error_trends"]

            # Should detect the increase
            assert trends["trend_percentage"] > 50  # Should be close to 100% increase
            assert trends["current_hour_errors"] >= trends["previous_hour_errors"]


class TestLogIntelligenceIntegration:
    """Integration tests for complete log intelligence workflow"""

    @pytest.fixture
    def comprehensive_log_scenario(self, temp_log_dir):
        """Create a comprehensive log scenario for integration testing"""
        generator = SyntheticLogGenerator(temp_log_dir)

        # Generate multiple types of logs
        generator.generate_healthy_logs("app1.log", 50)
        generator.generate_error_spike_logs("app2.log", spike_hour=0)
        generator.generate_critical_pattern_logs("critical.log")
        generator.generate_performance_issue_logs("performance.log")
        generator.generate_security_alert_logs("security.log")
        generator.generate_todo_comment_code("service.py")

        return temp_log_dir

    def test_comprehensive_analysis_workflow(self, comprehensive_log_scenario):
        """Test the complete log intelligence analysis workflow"""
        # Run comprehensive analysis
        analyzer = LogIntelligenceAnalyzer([comprehensive_log_scenario])
        analyzer.analyze_logs(hours_back=3, max_files=20)

        # Verify comprehensive results
        results = analyzer.analysis_results

        # Should have processed multiple log files
        assert results["total_entries"] > 50

        # Should detect various types of issues
        assert len(results["critical_patterns"]) > 0
        assert len(results["performance_issues"]) > 0
        assert len(results["security_alerts"]) > 0

        # Generate and verify report
        report = analyzer.generate_daily_digest()

        assert len(report) > 1000  # Should be a substantial report
        assert "Critical Issues Detected" in report
        assert "Performance Issues" in report
        assert "Security Alerts" in report

        # Save results and verify files are created
        analyzer.save_analysis_results()

        results_file = Path("log_intelligence_results.json")
        digest_file = Path("daily_log_digest.md")

        assert results_file.exists()
        assert digest_file.exists()

        # Verify saved content
        with open(results_file) as f:
            saved_results = json.load(f)
            assert saved_results["total_entries"] == results["total_entries"]

        with open(digest_file) as f:
            saved_digest = f.read()
            assert "Daily Log Intelligence Digest" in saved_digest

        # Cleanup
        results_file.unlink()
        digest_file.unlink()


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
