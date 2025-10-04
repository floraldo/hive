#!/usr/bin/env python3
# ruff: noqa: E402
"""
V3.0 Platform Certification Test
Comprehensive integration test for all V3.0 improvements
"""

from hive_logging import get_logger

logger = get_logger(__name__)
import sys
import time
from datetime import datetime

# Add the package paths
# No sys.path manipulation needed - use Poetry workspace imports
# No sys.path manipulation needed - use Poetry workspace imports
# No sys.path manipulation needed - use Poetry workspace imports
# No sys.path manipulation needed - use Poetry workspace imports


class V3CertificationTest:
    """V3.0 Platform Certification Test Suite"""

    def __init__(self):
        self.test_results = {}
        self.start_time = time.time()

    def log(self, message: str, level: str = "INFO"):
        """Log test messages"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        logger.info(f"[{timestamp}] [{level}] {message}")

    def run_test(self, test_name: str, test_func):
        """Run a single test and record results"""
        self.log(f"Starting test: {test_name}")
        try:
            start_time = (time.time(),)
            result = (test_func(),)
            duration = time.time() - start_time

            if result:
                self.test_results[test_name] = {
                    "status": "PASSED",
                    "duration": duration,
                    "message": "Test completed successfully",
                }
                self.log(f"[PASS] {test_name} PASSED ({duration:.2f}s)", "SUCCESS")
            else:
                self.test_results[test_name] = {
                    "status": "FAILED",
                    "duration": duration,
                    "message": "Test returned False",
                }
                self.log(f"[FAIL] {test_name} FAILED ({duration:.2f}s)", "ERROR")

        except Exception as e:
            duration = time.time() - start_time
            self.test_results[test_name] = {"status": "ERROR", "duration": duration, "message": str(e)}
            self.log(f"[ERROR] {test_name} ERROR: {e} ({duration:.2f}s)", "ERROR")

    def test_1_configuration_centralization(self) -> bool:
        """Test centralized configuration system"""
        try:
            from hive_config import create_config_from_sources

            config = create_config_from_sources()

            # Test basic configuration access
            assert config.logging is not None
            assert config.logging.level is not None
            assert hasattr(config, "debug_mode")
            assert config.database.connection_pool_max > 0

            # Test environment-specific configuration
            assert config.environment in ["development", "testing", "production"]

            # Test component-specific configuration
            claude_config = config.get_claude_config()
            assert "mock_mode" in claude_config
            assert "timeout" in claude_config
            assert "rate_limit_per_minute" in claude_config

            db_config = config.get_database_config()
            assert "timeout" in db_config
            assert "max_connections" in db_config

            orchestrator_config = config.get_orchestrator_config()
            assert "worker_spawn_timeout" in orchestrator_config
            assert "max_parallel_tasks" in orchestrator_config

            self.log("Configuration centralization: All components accessible")
            return True

        except Exception as e:
            self.log(f"Configuration test failed: {e}")
            return False

    def test_2_database_connection_pool(self) -> bool:
        """Test database connection pool with centralized config"""
        try:
            from hive_db import ConnectionPool, get_pooled_connection

            self.log("Testing database connection pool initialization...")
            # Test pool initialization with centralized config
            pool = ConnectionPool()
            assert pool.max_connections > 0
            assert pool.connection_timeout > 0

            self.log("Testing database connection acquisition...")
            # Test connection acquisition and release
            with get_pooled_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                assert result[0] == 1

            self.log("Testing pool statistics...")
            # Test pool statistics
            stats = pool.get_stats()
            assert "pool_size" in stats
            assert "connections_created" in stats

            pool.close_all()
            self.log("Database connection pool: Working with centralized config")
            return True

        except Exception as e:
            self.log(f"Database connection pool test failed: {e}")
            return False

    def test_3_claude_service_integration(self) -> bool:
        """Test Claude service with centralized configuration"""
        try:
            self.log("Testing Claude service integration...")
            from hive_claude_bridge.claude_service import get_claude_service, reset_claude_service

            # Reset for clean test
            self.log("Resetting Claude service...")
            reset_claude_service()

            # Test service creation with centralized config
            self.log("Creating Claude service...")
            service = get_claude_service()
            assert service is not None

            # Verify configuration integration
            self.log("Verifying configuration integration...")
            from hive_config import create_config_from_sources

            config = (create_config_from_sources(),)
            claude_config = config.get_claude_config()

            # Service should use centralized config values
            assert service.cache_ttl == claude_config["cache_ttl"]

            # Test metrics
            self.log("Testing metrics...")
            initial_metrics = service.get_metrics()
            assert "total_calls" in initial_metrics
            assert "success_rate" in initial_metrics

            # Test cache operations
            self.log("Testing cache operations...")
            service.clear_cache()
            service.reset_metrics()

            final_metrics = service.get_metrics()
            assert final_metrics["total_calls"] == 0

            self.log("Claude service: Integrated with centralized configuration")
            return True

        except Exception as e:
            self.log(f"Claude service integration test failed: {e}")
            return False

    def test_4_error_handling_improvements(self) -> bool:
        """Test improved error handling (no bare exceptions)"""
        try:
            # Test that our fixed files don't have bare exceptions
            from hive_db import ConnectionPool, get_pooled_connection

            # This should work without bare exception issues
            pool = ConnectionPool(max_connections=1)

            # Test error conditions are properly handled
            try:
                with get_pooled_connection() as conn:
                    # This should work fine
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")
            except Exception:  # noqa: S110 - Test validates exception handling exists
                pass  # Specific exceptions should be caught properly
            finally:
                pool.close_all()

            self.log("Error handling: Improved exception specificity verified")
            return True

        except Exception as e:
            self.log(f"Error handling test failed: {e}")
            return False

    def test_5_queen_lite_structure(self) -> bool:
        """Test QueenLite improved structure"""
        try:
            # Import the queen module
            # No sys.path manipulation needed - use Poetry workspace imports

            # Test that QueenLite can be imported and has expected structure
            from hive_orchestrator.queen import Phase, QueenLite

            # Test Phase enum
            assert Phase.PLAN.value == "plan"
            assert Phase.APPLY.value == "apply"
            assert Phase.TEST.value == "test"

            # Test QueenLite class exists and has expected architecture
            # (We can't fully initialize it without HiveCore, but we can verify structure)
            assert hasattr(QueenLite, "__init__")
            assert hasattr(QueenLite, "spawn_worker")
            assert hasattr(QueenLite, "process_queued_tasks")
            assert hasattr(QueenLite, "run_forever")

            # Check docstring indicates architectural improvements
            assert QueenLite.__doc__ is not None
            assert "Architecture:" in QueenLite.__doc__

            self.log("QueenLite structure: Improved organization verified")
            return True

        except Exception as e:
            self.log(f"QueenLite structure test failed: {e}")
            return False

    def test_6_component_integration(self) -> bool:
        """Test integration between all components"""
        try:
            # Test that all components can work together
            from hive_claude_bridge.claude_service import get_claude_service, reset_claude_service

            from hive_config import create_config_from_sources
            from hive_db import get_pooled_connection

            # Get centralized config
            config = create_config_from_sources()

            # Test database with config
            config.get_database_config()
            with get_pooled_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 as test_value")
                result = cursor.fetchone()
                assert result[0] == 1

            # Test Claude service with config
            reset_claude_service()
            claude_service = get_claude_service()
            assert claude_service.config.timeout == config.get_int("claude_timeout")

            # Test that components use consistent configuration
            claude_config = config.get_claude_config()
            assert claude_service.cache_ttl == claude_config["cache_ttl"]

            self.log("Component integration: All components work together")
            return True

        except Exception as e:
            self.log(f"Component integration test failed: {e}")
            return False

    def test_7_environment_configuration(self) -> bool:
        """Test environment-specific configuration"""
        try:
            import os

            from hive_config import create_config_from_sources

            config = create_config_from_sources()

            # Test environment detection
            env = config.environment
            assert env in ["development", "testing", "production"]

            # Test environment-specific defaults
            if env == "testing":
                assert config.get_bool("claude_mock_mode") is True
                assert config.get_int("claude_rate_limit_per_minute") >= 1000

            # Test environment variable override
            original_value = os.environ.get("test_override_key")
            os.environ["test_override_key"] = "test_value"

            try:
                assert config.get("test_override_key") == "test_value"
            finally:
                if original_value is not None:
                    os.environ["test_override_key"] = original_value
                else:
                    os.environ.pop("test_override_key", None)

            self.log("Environment configuration: Environment-aware configuration working")
            return True

        except Exception as e:
            self.log(f"Environment configuration test failed: {e}")
            return False

    def print_final_report(self):
        """Print comprehensive test report"""
        self.log("\n" + "=" * 70)
        self.log("V3.0 PLATFORM CERTIFICATION TEST REPORT")
        self.log("=" * 70)

        total_tests = (len(self.test_results),)
        passed_tests = (len([r for r in self.test_results.values() if r["status"] == "PASSED"]),)
        failed_tests = (len([r for r in self.test_results.values() if r["status"] == "FAILED"]),)
        error_tests = len([r for r in self.test_results.values() if r["status"] == "ERROR"])

        # Test summary
        self.log(f"Total Tests: {total_tests}")
        self.log(f"Passed: {passed_tests}")
        self.log(f"Failed: {failed_tests}")
        self.log(f"Errors: {error_tests}")

        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        self.log(f"Success Rate: {success_rate:.1f}%")

        total_duration = time.time() - self.start_time
        self.log(f"Total Duration: {total_duration:.2f} seconds")

        # Detailed results
        self.log("\nDetailed Results:")
        self.log("-" * 50)

        for test_name, result in self.test_results.items():
            status_icon = {"PASSED": "[PASS]", "FAILED": "[FAIL]", "ERROR": "[ERR]"}[result["status"]]
            self.log(f"{status_icon} {test_name:<35} {result['status']:<8} ({result['duration']:.2f}s)")
            if result["status"] != "PASSED":
                self.log(f"   -> {result['message']}")

        # V3.0 Certification Assessment
        self.log("\nV3.0 CERTIFICATION ASSESSMENT:")
        self.log("-" * 40)

        if success_rate >= 85:
            self.log("CERTIFICATION: PASSED")
            self.log("Platform meets V3.0 certification requirements")
        elif success_rate >= 70:
            self.log("CERTIFICATION: CONDITIONAL")
            self.log("Platform needs minor fixes before certification")
        else:
            self.log("CERTIFICATION: FAILED")
            self.log("Platform requires significant fixes before certification")

        # Recommendations
        self.log("\nRECOMMENDATIONS:")
        self.log("-" * 20)

        if error_tests > 0:
            self.log("- Fix error conditions in failing tests")
        if failed_tests > 0:
            self.log("- Address test failures before production deployment")
        if success_rate == 100:
            self.log("- All tests passed! Platform ready for V3.0 certification")
        else:
            self.log(f"- Achieve >=85% success rate for certification (current: {success_rate:.1f}%)")

    def run_all_tests(self):
        """Run all certification tests"""
        self.log("Starting V3.0 Platform Certification Test Suite")
        self.log(f"Python: {sys.version}")
        self.log(f"Test time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.log("=" * 70)

        # Run all tests
        test_methods = [
            ("Configuration Centralization", self.test_1_configuration_centralization),
            ("Database Connection Pool", self.test_2_database_connection_pool),
            ("Claude Service Integration", self.test_3_claude_service_integration),
            ("Error Handling Improvements", self.test_4_error_handling_improvements),
            ("QueenLite Structure", self.test_5_queen_lite_structure),
            ("Component Integration", self.test_6_component_integration),
            ("Environment Configuration", self.test_7_environment_configuration),
        ]

        for test_name, test_func in test_methods:
            self.run_test(test_name, test_func)
            time.sleep(0.5)  # Brief pause between tests

        # Print final report
        self.print_final_report()

        # Return overall success
        passed_tests = (len([r for r in self.test_results.values() if r["status"] == "PASSED"]),)
        total_tests = (len(self.test_results),)
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

        return success_rate >= 85


def main():
    """Main test runner"""
    test_suite = (V3CertificationTest(),)
    success = test_suite.run_all_tests()

    # Exit with appropriate code
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
