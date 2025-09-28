#!/usr/bin/env python3
"""
Hive Platform Integration Test Runner

A convenient script for running integration tests locally during development.
Provides different test modes and detailed reporting.

Usage:
    python scripts/run_integration_tests.py --mode quick    # Fast validation tests
    python scripts/run_integration_tests.py --mode full     # Complete integration suite
    python scripts/run_integration_tests.py --mode perf     # Performance tests only
    python scripts/run_integration_tests.py --mode custom --tests "test1,test2"
"""

import argparse
import subprocess
import sys
import time
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import os


@dataclass
class TestResult:
    """Test execution result"""
    name: str
    passed: bool
    duration: float
    output: str
    error: Optional[str] = None


class IntegrationTestRunner:
    """Hive platform integration test runner"""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.test_results: List[TestResult] = []
        self.start_time = time.time()

    def run_quick_validation(self) -> bool:
        """Run quick validation tests for fast feedback"""
        print("[START] Running Quick Validation Tests...")
        print("=" * 60)

        tests = [
            ("Platform Health Check", self._run_platform_health_check),
            ("Database Connectivity", self._run_database_connectivity_test),
            ("Event Bus Basic", self._run_event_bus_basic_test),
            ("Import Patterns", self._run_import_patterns_test),
        ]

        return self._execute_test_suite(tests)

    def run_full_integration(self) -> bool:
        """Run complete integration test suite"""
        print("[STAR] Running Full Integration Test Suite...")
        print("=" * 60)

        # First run quick validation
        if not self.run_quick_validation():
            print("[FAIL] Quick validation failed, skipping full integration tests")
            return False

        # Then run comprehensive tests
        return self._run_comprehensive_integration_tests()

    def run_performance_tests(self) -> bool:
        """Run performance-focused tests"""
        print("[FAST] Running Performance Integration Tests...")
        print("=" * 60)

        tests = [
            ("Async Infrastructure Performance", self._run_async_performance_test),
            ("Concurrent Task Processing", self._run_concurrent_processing_test),
            ("Database Connection Pooling", self._run_database_pooling_test),
            ("Performance Improvement Validation", self._run_performance_improvement_test),
        ]

        return self._execute_test_suite(tests)

    def run_custom_tests(self, test_names: List[str]) -> bool:
        """Run custom selection of tests"""
        print(f"[UNI] Running Custom Tests: {', '.join(test_names)}")
        print("=" * 60)

        available_tests = {
            "platform_health": self._run_platform_health_check,
            "database": self._run_database_connectivity_test,
            "event_bus": self._run_event_bus_basic_test,
            "imports": self._run_import_patterns_test,
            "async_perf": self._run_async_performance_test,
            "concurrent": self._run_concurrent_processing_test,
            "db_pooling": self._run_database_pooling_test,
            "comprehensive": self._run_comprehensive_integration_tests,
        }

        tests = []
        for test_name in test_names:
            if test_name in available_tests:
                tests.append((test_name.replace("_", " ").title(), available_tests[test_name]))
            else:
                print(f"[WARN] Unknown test: {test_name}")
                print(f"Available tests: {', '.join(available_tests.keys())}")

        return self._execute_test_suite(tests)

    def _execute_test_suite(self, tests: List[tuple]) -> bool:
        """Execute a suite of tests"""
        all_passed = True

        for test_name, test_func in tests:
            print(f"\n[LIST] Running: {test_name}")
            print("-" * 40)

            start_time = time.time()
            try:
                result = test_func()
                duration = time.time() - start_time

                if result:
                    print(f"[PASS] {test_name}: PASSED ({duration:.2f}s)")
                    self.test_results.append(TestResult(test_name, True, duration, ""))
                else:
                    print(f"[FAIL] {test_name}: FAILED ({duration:.2f}s)")
                    self.test_results.append(TestResult(test_name, False, duration, ""))
                    all_passed = False

            except Exception as e:
                duration = time.time() - start_time
                print(f"[BOOM] {test_name}: EXCEPTION ({duration:.2f}s) - {e}")
                self.test_results.append(TestResult(test_name, False, duration, "", str(e)))
                all_passed = False

        return all_passed

    def _run_platform_health_check(self) -> bool:
        """Run platform health check"""
        try:
            result = subprocess.run([
                sys.executable, "-m", "pytest",
                str(self.project_root / "tests" / "test_hive_platform_validation.py::test_platform_health_check"),
                "-v", "--tb=short"
            ], capture_output=True, text=True, timeout=60)

            return result.returncode == 0

        except subprocess.TimeoutExpired:
            print("[TIMEOUT] Platform health check timed out")
            return False

    def _run_database_connectivity_test(self) -> bool:
        """Test database connectivity"""
        try:
            result = subprocess.run([
                sys.executable, "-m", "pytest",
                str(self.project_root / "tests" / "test_hive_platform_validation.py::PlatformValidationTests::test_database_connectivity"),
                "-v", "--tb=short"
            ], capture_output=True, text=True, timeout=30)

            return result.returncode == 0

        except subprocess.TimeoutExpired:
            print("[TIMEOUT] Database connectivity test timed out")
            return False

    def _run_event_bus_basic_test(self) -> bool:
        """Test basic event bus functionality"""
        try:
            result = subprocess.run([
                sys.executable, "-m", "pytest",
                str(self.project_root / "tests" / "test_hive_platform_validation.py::PlatformValidationTests::test_event_bus_basic_functionality"),
                "-v", "--tb=short"
            ], capture_output=True, text=True, timeout=30)

            return result.returncode == 0

        except subprocess.TimeoutExpired:
            print("[TIMEOUT] Event bus test timed out")
            return False

    def _run_import_patterns_test(self) -> bool:
        """Test import patterns"""
        try:
            # Simple import test
            test_code = '''
import sys
from pathlib import Path

project_root = Path(".")
sys.path.insert(0, str(project_root / "apps" / "hive-orchestrator" / "src"))

try:
    import hive_orchestrator
    print("[PASS] Hive orchestrator imports successfully")
    exit(0)
except ImportError as e:
    print(f"[FAIL] Import failed: {e}")
    exit(1)
'''

            result = subprocess.run([
                sys.executable, "-c", test_code
            ], capture_output=True, text=True, timeout=15, cwd=self.project_root)

            return result.returncode == 0

        except subprocess.TimeoutExpired:
            print("[TIMEOUT] Import patterns test timed out")
            return False

    def _run_async_performance_test(self) -> bool:
        """Test async infrastructure performance"""
        test_code = '''
import sys
from pathlib import Path

sys.path.insert(0, str(Path(".") / "tests"))

from test_comprehensive_integration import PerformanceIntegrationTests, PlatformTestEnvironment

env = PlatformTestEnvironment()
env.setup()

try:
    perf_tests = PerformanceIntegrationTests(env)
    result = perf_tests.test_async_infrastructure_performance()
    print(f"Async infrastructure test: {'PASSED' if result else 'FAILED'}")
    exit(0 if result else 1)
finally:
    env.teardown()
'''

        try:
            result = subprocess.run([
                sys.executable, "-c", test_code
            ], capture_output=True, text=True, timeout=120, cwd=self.project_root)

            return result.returncode == 0

        except subprocess.TimeoutExpired:
            print("[TIMEOUT] Async performance test timed out")
            return False

    def _run_concurrent_processing_test(self) -> bool:
        """Test concurrent task processing"""
        test_code = '''
import sys
from pathlib import Path

sys.path.insert(0, str(Path(".") / "tests"))

from test_comprehensive_integration import PerformanceIntegrationTests, PlatformTestEnvironment

env = PlatformTestEnvironment()
env.setup()

try:
    perf_tests = PerformanceIntegrationTests(env)
    result = perf_tests.test_concurrent_task_processing()

    # Print performance metrics
    for sample in env.metrics.performance_samples:
        if "concurrent" in sample.get("test", ""):
            throughput = sample.get("throughput", 0)
            print(f"Concurrent processing throughput: {throughput:.2f} tasks/sec")

    print(f"Concurrent processing test: {'PASSED' if result else 'FAILED'}")
    exit(0 if result else 1)
finally:
    env.teardown()
'''

        try:
            result = subprocess.run([
                sys.executable, "-c", test_code
            ], capture_output=True, text=True, timeout=120, cwd=self.project_root)

            return result.returncode == 0

        except subprocess.TimeoutExpired:
            print("[TIMEOUT] Concurrent processing test timed out")
            return False

    def _run_database_pooling_test(self) -> bool:
        """Test database connection pooling"""
        test_code = '''
import sys
from pathlib import Path

sys.path.insert(0, str(Path(".") / "tests"))

from test_comprehensive_integration import PerformanceIntegrationTests, PlatformTestEnvironment

env = PlatformTestEnvironment()
env.setup()

try:
    perf_tests = PerformanceIntegrationTests(env)
    result = perf_tests.test_database_connection_pooling()

    # Print performance metrics
    for sample in env.metrics.performance_samples:
        if "database" in sample.get("test", ""):
            ops_per_sec = sample.get("ops_per_second", 0)
            print(f"Database operations: {ops_per_sec:.2f} ops/sec")

    print(f"Database pooling test: {'PASSED' if result else 'FAILED'}")
    exit(0 if result else 1)
finally:
    env.teardown()
'''

        try:
            result = subprocess.run([
                sys.executable, "-c", test_code
            ], capture_output=True, text=True, timeout=90, cwd=self.project_root)

            return result.returncode == 0

        except subprocess.TimeoutExpired:
            print("[TIMEOUT] Database pooling test timed out")
            return False

    def _run_performance_improvement_test(self) -> bool:
        """Test performance improvement claims"""
        test_code = '''
import sys
from pathlib import Path

sys.path.insert(0, str(Path(".") / "tests"))

from test_comprehensive_integration import PerformanceIntegrationTests, PlatformTestEnvironment

env = PlatformTestEnvironment()
env.setup()

try:
    perf_tests = PerformanceIntegrationTests(env)
    result = perf_tests.test_performance_improvement_claims()

    # Print improvement metrics
    for sample in env.metrics.performance_samples:
        if "improvement" in sample.get("test", ""):
            factor = sample.get("improvement_factor", 0)
            print(f"Performance improvement: {factor:.1f}x")

    print(f"Performance improvement test: {'PASSED' if result else 'FAILED'}")
    exit(0 if result else 1)
finally:
    env.teardown()
'''

        try:
            result = subprocess.run([
                sys.executable, "-c", test_code
            ], capture_output=True, text=True, timeout=90, cwd=self.project_root)

            return result.returncode == 0

        except subprocess.TimeoutExpired:
            print("[TIMEOUT] Performance improvement test timed out")
            return False

    def _run_comprehensive_integration_tests(self) -> bool:
        """Run the full comprehensive integration test suite"""
        try:
            result = subprocess.run([
                sys.executable,
                str(self.project_root / "tests" / "test_comprehensive_integration.py")
            ], capture_output=True, text=True, timeout=1800, cwd=self.project_root)  # 30 minutes

            # Print output for visibility
            if result.stdout:
                print(result.stdout)
            if result.stderr and result.returncode != 0:
                print("STDERR:", result.stderr)

            return result.returncode == 0

        except subprocess.TimeoutExpired:
            print("[TIMEOUT] Comprehensive integration tests timed out")
            return False

    def print_summary(self):
        """Print test execution summary"""
        total_duration = time.time() - self.start_time
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result.passed)

        print("\n" + "=" * 80)
        print("[SUMMARY] INTEGRATION TEST SUMMARY")
        print("=" * 80)

        print(f"[STATS] Results: {passed_tests}/{total_tests} tests passed")
        print(f"[TIME]  Total Duration: {total_duration:.2f} seconds")

        if self.test_results:
            avg_duration = sum(r.duration for r in self.test_results) / len(self.test_results)
            print(f"[PERF] Average Test Duration: {avg_duration:.2f} seconds")

        print(f"\n[LIST] Individual Test Results:")
        for result in self.test_results:
            status = "[PASS] PASSED" if result.passed else "[FAIL] FAILED"
            print(f"   {status} {result.name} ({result.duration:.2f}s)")
            if result.error:
                print(f"      Error: {result.error}")

        print("\n" + "=" * 80)
        if passed_tests == total_tests:
            print("[SUCCESS] ALL TESTS PASSED!")
            print("[STAR] Hive platform integration is working correctly")
        else:
            print("[FAIL] SOME TESTS FAILED")
            print("[FIX] Review failed tests above")
        print("=" * 80)

    def generate_report(self, output_file: Optional[Path] = None) -> Dict[str, Any]:
        """Generate JSON test report"""
        report = {
            "timestamp": time.time(),
            "total_duration": time.time() - self.start_time,
            "total_tests": len(self.test_results),
            "passed_tests": sum(1 for r in self.test_results if r.passed),
            "test_results": [
                {
                    "name": result.name,
                    "passed": result.passed,
                    "duration": result.duration,
                    "error": result.error
                }
                for result in self.test_results
            ]
        }

        if output_file:
            with open(output_file, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"[FILE] Report saved to: {output_file}")

        return report


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Hive Platform Integration Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --mode quick                    # Fast validation tests
  %(prog)s --mode full                     # Complete integration suite
  %(prog)s --mode perf                     # Performance tests only
  %(prog)s --mode custom --tests "platform_health,database"
  %(prog)s --mode quick --report results.json
        """
    )

    parser.add_argument(
        "--mode",
        choices=["quick", "full", "perf", "custom"],
        default="quick",
        help="Test mode to run (default: quick)"
    )

    parser.add_argument(
        "--tests",
        help="Comma-separated list of tests for custom mode"
    )

    parser.add_argument(
        "--report",
        type=Path,
        help="Output file for JSON test report"
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )

    args = parser.parse_args()

    # Set up environment
    project_root = Path(__file__).parent.parent
    os.environ["HIVE_TEST_MODE"] = "true"
    os.environ["PYTHONPATH"] = str(project_root)

    # Create test runner
    runner = IntegrationTestRunner(project_root)

    # Run tests based on mode
    success = False

    try:
        if args.mode == "quick":
            success = runner.run_quick_validation()
        elif args.mode == "full":
            success = runner.run_full_integration()
        elif args.mode == "perf":
            success = runner.run_performance_tests()
        elif args.mode == "custom":
            if not args.tests:
                print("[FAIL] Custom mode requires --tests parameter")
                sys.exit(1)
            test_list = [t.strip() for t in args.tests.split(",")]
            success = runner.run_custom_tests(test_list)

    except KeyboardInterrupt:
        print("\n[WARN] Tests interrupted by user")
        success = False

    # Print summary and generate report
    runner.print_summary()

    if args.report:
        runner.generate_report(args.report)

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()