#!/usr/bin/env python3
"""
V2.0 Platform Verification Script
Comprehensive test suite to verify the Hive V2.0 platform functionality.
"""

import sys
import time
from pathlib import Path

# Add packages to path
sys.path.insert(0, str(Path(__file__).parent / "packages" / "hive-core-db" / "src"))

from hive_core_db import (
    init_db,
    create_task,
    close_connection
)
from hive_core_db.database import get_connection


class V2PlatformVerifier:
    """Verification test suite for V2.0 platform."""

    def __init__(self):
        self.test_results = []

    def log_test(self, test_name: str, passed: bool, details: str = ""):
        """Log test result."""
        status = "[PASS]" if passed else "[FAIL]"
        self.test_results.append((test_name, passed, details))
        print(f"{status} {test_name}")
        if details and not passed:
            print(f"      Details: {details}")

    def test_database_connectivity(self):
        """Test database initialization and connectivity."""
        try:
            init_db()
            conn = get_connection()
            cursor = conn.cursor()

            # Test basic queries
            cursor.execute("SELECT COUNT(*) FROM tasks")
            cursor.execute("SELECT COUNT(*) FROM runs")
            cursor.execute("SELECT COUNT(*) FROM workers")

            self.log_test("Database Connectivity", True)
        except Exception as e:
            self.log_test("Database Connectivity", False, str(e))

    def test_task_creation(self):
        """Test task creation functionality."""
        try:
            task_id = create_task(
                title="Test Task Creation",
                task_type="verification",
                description="Testing V2.0 task creation",
                priority=1
            )

            # Verify task was created
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, title FROM tasks WHERE id = ?", (task_id,))
            result = cursor.fetchone()

            passed = result is not None and result[0] == task_id
            self.log_test("Task Creation", passed)

        except Exception as e:
            self.log_test("Task Creation", False, str(e))

    def test_database_schema(self):
        """Test database schema completeness."""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Check required tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            required_tables = ['tasks', 'runs', 'workers']
            missing_tables = [t for t in required_tables if t not in tables]

            passed = len(missing_tables) == 0
            details = f"Missing tables: {missing_tables}" if missing_tables else ""
            self.log_test("Database Schema", passed, details)

        except Exception as e:
            self.log_test("Database Schema", False, str(e))

    def test_parallel_config(self):
        """Test parallel execution configuration."""
        try:
            config_path = Path("hive_config.json")
            if config_path.exists():
                import json
                with open(config_path) as f:
                    config = json.load(f)

                max_parallel = config.get("orchestration", {}).get("max_parallel_per_role", {})
                has_parallel_config = len(max_parallel) > 0

                self.log_test("Parallel Configuration", has_parallel_config,
                             f"Config: {max_parallel}")
            else:
                self.log_test("Parallel Configuration", False, "No hive_config.json found")

        except Exception as e:
            self.log_test("Parallel Configuration", False, str(e))

    def test_orchestrator_structure(self):
        """Test hive-orchestrator app structure."""
        try:
            orchestrator_path = Path("apps/hive-orchestrator")
            required_files = [
                "pyproject.toml",
                "src/hive_orchestrator/__init__.py",
                "src/hive_orchestrator/queen.py",
                "src/hive_orchestrator/worker.py",
                "src/hive_orchestrator/dashboard.py",
                "src/hive_orchestrator/cli.py"
            ]

            missing_files = []
            for file_path in required_files:
                if not (orchestrator_path / file_path).exists():
                    missing_files.append(file_path)

            passed = len(missing_files) == 0
            details = f"Missing files: {missing_files}" if missing_files else ""
            self.log_test("Orchestrator Structure", passed, details)

        except Exception as e:
            self.log_test("Orchestrator Structure", False, str(e))

    def test_dashboard_imports(self):
        """Test dashboard can import required libraries."""
        try:
            # Test rich library import
            from rich.console import Console
            from rich.table import Table

            # Test dashboard module
            dashboard_path = Path("apps/hive-orchestrator/src/hive_orchestrator/dashboard.py")
            dashboard_exists = dashboard_path.exists()

            self.log_test("Dashboard Dependencies", dashboard_exists)

        except ImportError as e:
            self.log_test("Dashboard Dependencies", False, f"Import error: {e}")
        except Exception as e:
            self.log_test("Dashboard Dependencies", False, str(e))

    def run_all_tests(self):
        """Run complete verification suite."""
        print("=" * 60)
        print("HIVE V2.0 PLATFORM VERIFICATION")
        print("=" * 60)

        # Run all tests
        self.test_database_connectivity()
        self.test_database_schema()
        self.test_task_creation()
        self.test_parallel_config()
        self.test_orchestrator_structure()
        self.test_dashboard_imports()

        # Summary
        passed_tests = [r for r in self.test_results if r[1]]
        failed_tests = [r for r in self.test_results if not r[1]]

        print("\n" + "=" * 60)
        print("VERIFICATION SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {len(self.test_results)}")
        print(f"Passed: {len(passed_tests)}")
        print(f"Failed: {len(failed_tests)}")

        if failed_tests:
            print(f"\nFailed Tests:")
            for test_name, _, details in failed_tests:
                print(f"  - {test_name}: {details}")

        # Overall result
        success_rate = len(passed_tests) / len(self.test_results) * 100
        print(f"\nSuccess Rate: {success_rate:.1f}%")

        if success_rate >= 85:
            print("\n[SUCCESS] V2.0 Platform verification passed! Platform is stable.")
        else:
            print("\n[WARNING] V2.0 Platform has issues. Review failed tests.")

        close_connection()
        return success_rate >= 85


def main():
    """Main verification entry point."""
    verifier = V2PlatformVerifier()
    success = verifier.run_all_tests()

    if success:
        print("\n" + "=" * 60)
        print("V2.0 PLATFORM READY FOR PRODUCTION")
        print("=" * 60)
        print("Next steps:")
        print("  1. Test parallel execution: python seed_parallel_test.py")
        print("  2. Run dashboard: poetry run hive-dashboard")
        print("  3. Start Queen: poetry run hive-queen")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())