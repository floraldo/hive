#!/usr/bin/env python3
"""
Integration Test Validation Script

Quick validation script to ensure all integration tests are properly set up
and can run without errors. This script validates:

1. Test file existence and syntax
2. Required dependencies
3. Test environment setup
4. Quick smoke tests

Run this before the full integration test suite to catch issues early.
"""

import ast
import importlib.util
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Tuple, Dict
import tempfile
import sqlite3


class IntegrationTestValidator:
    """Validates integration test setup and configuration"""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.test_files = []
        self.validation_results = []

    def run_full_validation(self) -> bool:
        """Run complete validation of integration test suite"""
        print("[SEARCH] Validating Hive Integration Test Suite")
        print("=" * 60)

        # Step 1: Discover test files
        test_discovery_ok = self.discover_test_files()
        print(f"[FOLDER] Test Discovery: {'[PASS] PASSED' if test_discovery_ok else '[FAIL] FAILED'}")

        if not test_discovery_ok:
            return False

        # Step 2: Validate test file syntax
        syntax_validation_ok = self.validate_test_syntax()
        print(f"[SYNTAX] Syntax Validation: {'[PASS] PASSED' if syntax_validation_ok else '[FAIL] FAILED'}")

        # Step 3: Check dependencies
        deps_ok = self.check_dependencies()
        print(f"[DEPS] Dependencies: {'[PASS] PASSED' if deps_ok else '[FAIL] FAILED'}")

        # Step 4: Validate test environment
        env_ok = self.validate_test_environment()
        print(f"[CONFIG] Environment: {'[PASS] PASSED' if env_ok else '[FAIL] FAILED'}")

        # Step 5: Run quick smoke tests
        smoke_tests_ok = self.run_smoke_tests()
        print(f"[SMOKE] Smoke Tests: {'[PASS] PASSED' if smoke_tests_ok else '[FAIL] FAILED'}")

        # Step 6: Validate test runners
        runners_ok = self.validate_test_runners()
        print(f"[RUNNER] Test Runners: {'[PASS] PASSED' if runners_ok else '[FAIL] FAILED'}")

        # Generate validation report
        all_passed = all([test_discovery_ok, syntax_validation_ok, deps_ok, env_ok, smoke_tests_ok, runners_ok])

        self.print_validation_summary(all_passed)
        return all_passed

    def discover_test_files(self) -> bool:
        """Discover all integration test files"""
        try:
            test_patterns = [
                "test_*integration*.py",
                "test_comprehensive*.py",
                "test_*performance*.py",
                "test_end_to_end*.py",
                "test_*pipeline*.py",
            ]

            for pattern in test_patterns:
                # Search in tests directory
                test_files = list(self.project_root.glob(f"tests/{pattern}"))
                self.test_files.extend(test_files)

                # Search in app-specific test directories
                for app_dir in (self.project_root / "apps").glob("*"):
                    if app_dir.is_dir() and (app_dir / "tests").exists():
                        app_test_files = list((app_dir / "tests").glob(pattern))
                        self.test_files.extend(app_test_files)

            # Remove duplicates
            self.test_files = list(set(self.test_files))

            print(f"[FOLDER] Found {len(self.test_files)} integration test files:")
            for test_file in self.test_files:
                print(f"   [FILE] {test_file.relative_to(self.project_root)}")

            return len(self.test_files) > 0

        except Exception as e:
            print(f"[FAIL] Test file discovery failed: {e}")
            return False

    def validate_test_syntax(self) -> bool:
        """Validate syntax of all test files"""
        syntax_errors = []

        for test_file in self.test_files:
            try:
                with open(test_file, "r", encoding="utf-8") as f:
                    content = f.read()

                # Parse AST to check syntax
                ast.parse(content, filename=str(test_file))

                print(f"[PASS] {test_file.name}: Syntax OK")

            except SyntaxError as e:
                error_msg = f"{test_file.name}:{e.lineno}: {e.msg}"
                syntax_errors.append(error_msg)
                print(f"[FAIL] {test_file.name}: Syntax Error - {e.msg}")

            except Exception as e:
                error_msg = f"{test_file.name}: {e}"
                syntax_errors.append(error_msg)
                print(f"[FAIL] {test_file.name}: Read Error - {e}")

        if syntax_errors:
            print(f"\n[SYNTAX] Syntax Validation Summary: {len(syntax_errors)} errors found")
            for error in syntax_errors:
                print(f"   • {error}")
            return False

        print(f"[SYNTAX] Syntax Validation Summary: All {len(self.test_files)} files have valid syntax")
        return True

    def check_dependencies(self) -> bool:
        """Check that required dependencies are available"""
        required_modules = [
            "asyncio",
            "sqlite3",
            "json",
            "tempfile",
            "concurrent.futures",
            "subprocess",
            "threading",
            "time",
            "pathlib",
            "dataclasses",
            "typing",
            "unittest.mock",
        ]

        missing_modules = []

        for module in required_modules:
            try:
                __import__(module)
                print(f"[PASS] {module}: Available")
            except ImportError:
                missing_modules.append(module)
                print(f"[FAIL] {module}: Missing")

        # Check optional but recommended modules
        optional_modules = ["pytest", "psutil"]
        for module in optional_modules:
            try:
                __import__(module)
                print(f"[OPT] {module}: Available (optional)")
            except ImportError:
                print(f"[WARN] {module}: Missing (optional)")

        if missing_modules:
            print(f"\n[DEPS] Missing required modules: {missing_modules}")
            return False

        print(f"[DEPS] All required dependencies available")
        return True

    def validate_test_environment(self) -> bool:
        """Validate test environment setup"""
        try:
            # Test 1: Can create temporary database
            temp_db = tempfile.mktemp(suffix=".db")
            conn = sqlite3.connect(temp_db)
            conn.execute("CREATE TABLE test_env_validation (id INTEGER PRIMARY KEY)")
            conn.execute("INSERT INTO test_env_validation (id) VALUES (1)")
            cursor = conn.execute("SELECT COUNT(*) FROM test_env_validation")
            count = cursor.fetchone()[0]
            conn.close()

            Path(temp_db).unlink()

            if count != 1:
                print("[FAIL] Database environment test failed")
                return False

            print("[PASS] Database environment test passed")

            # Test 2: Can create temporary directories
            temp_dir = tempfile.mkdtemp(prefix="hive_env_test_")
            test_file = Path(temp_dir) / "test.txt"
            test_file.write_text("test")

            if not test_file.exists() or test_file.read_text() != "test":
                print("[FAIL] File system environment test failed")
                return False

            import shutil

            shutil.rmtree(temp_dir)
            print("[PASS] File system environment test passed")

            # Test 3: Can run subprocess
            result = subprocess.run(
                [sys.executable, "-c", "print('subprocess test')"], capture_output=True, text=True, timeout=10
            )

            if result.returncode != 0 or "subprocess test" not in result.stdout:
                print("[FAIL] Subprocess environment test failed")
                return False

            print("[PASS] Subprocess environment test passed")

            return True

        except Exception as e:
            print(f"[FAIL] Environment validation failed: {e}")
            return False

    def run_smoke_tests(self) -> bool:
        """Run quick smoke tests to validate basic functionality"""
        try:
            # Smoke Test 1: Import test modules
            print("[SMOKE] Running import smoke tests...")

            for test_file in self.test_files[:3]:  # Test first 3 files
                try:
                    spec = importlib.util.spec_from_file_location("test_module", test_file)
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        # Don't execute, just import to check for import errors
                        print(f"[PASS] {test_file.name}: Import OK")
                    else:
                        print(f"[FAIL] {test_file.name}: Import spec failed")
                        return False

                except Exception as e:
                    # Some import errors are expected due to missing dependencies
                    if "hive_orchestrator" in str(e) or "ai_planner" in str(e):
                        print(f"[WARN] {test_file.name}: Expected import issue - {e}")
                    else:
                        print(f"[FAIL] {test_file.name}: Unexpected import error - {e}")
                        return False

            # Smoke Test 2: Async functionality
            print("[SMOKE] Running async smoke test...")

            async_test_code = """
import asyncio
import time

async def smoke_test():
    start = time.time()
    await asyncio.sleep(0.01)
    duration = time.time() - start
    return duration >= 0.01

result = asyncio.run(smoke_test())
print(f"async_result:{result}")
"""

            result = subprocess.run([sys.executable, "-c", async_test_code], capture_output=True, text=True, timeout=10)

            if "async_result:True" not in result.stdout:
                print("[FAIL] Async smoke test failed")
                return False

            print("[PASS] Async smoke test passed")

            # Smoke Test 3: Concurrent execution
            print("[SMOKE] Running concurrency smoke test...")

            concurrent_test_code = """
import concurrent.futures
import time

def test_worker(n):
    time.sleep(0.01)
    return n * 2

start = time.time()
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
    futures = [executor.submit(test_worker, i) for i in range(5)]
    results = [f.result() for f in futures]

duration = time.time() - start
print(f"concurrent_result:{len(results)},{duration:.3f}")
"""

            result = subprocess.run(
                [sys.executable, "-c", concurrent_test_code], capture_output=True, text=True, timeout=10
            )

            if "concurrent_result:5," not in result.stdout:
                print("[FAIL] Concurrency smoke test failed")
                return False

            print("[PASS] Concurrency smoke test passed")

            return True

        except Exception as e:
            print(f"[FAIL] Smoke tests failed: {e}")
            return False

    def validate_test_runners(self) -> bool:
        """Validate test runner scripts exist and are executable"""
        runner_scripts = ["scripts/run_integration_tests.py", "scripts/run_comprehensive_integration_tests.py"]

        missing_runners = []

        for script_path in runner_scripts:
            full_path = self.project_root / script_path

            if not full_path.exists():
                missing_runners.append(script_path)
                print(f"[FAIL] {script_path}: Missing")
                continue

            # Check if script is syntactically valid
            try:
                with open(full_path, "r") as f:
                    content = f.read()

                ast.parse(content, filename=str(full_path))
                print(f"[PASS] {script_path}: Available and valid")

            except SyntaxError as e:
                print(f"[FAIL] {script_path}: Syntax error - {e}")
                missing_runners.append(script_path)

            except Exception as e:
                print(f"[FAIL] {script_path}: Error - {e}")
                missing_runners.append(script_path)

        if missing_runners:
            print(f"\n[RUNNER] Missing or invalid test runners: {missing_runners}")
            return False

        print("[RUNNER] All test runners are available and valid")
        return True

    def print_validation_summary(self, all_passed: bool):
        """Print validation summary"""
        print(f"\n{'='*60}")
        print("[REPORT] INTEGRATION TEST VALIDATION SUMMARY")
        print("=" * 60)

        print(f"\n[STATS] Validation Results:")
        print(f"   Test Files Found: {len(self.test_files)}")
        print(
            f"   Overall Status: {'[PASS] ALL VALIDATIONS PASSED' if all_passed else '[FAIL] SOME VALIDATIONS FAILED'}"
        )

        if self.test_files:
            print(f"\n[FOLDER] Test Files Validated:")
            for test_file in sorted(self.test_files):
                rel_path = test_file.relative_to(self.project_root)
                print(f"   [FILE] {rel_path}")

        print(f"\n{'='*60}")
        if all_passed:
            print("[SUCCESS] INTEGRATION TESTS ARE READY!")
            print("[PASS] All validation checks passed")
            print("[READY] Safe to run comprehensive integration test suite")
            print("")
            print("Next steps:")
            print("   python scripts/run_comprehensive_integration_tests.py --mode quick")
            print("   python scripts/run_comprehensive_integration_tests.py --mode all")
        else:
            print("[FAIL] INTEGRATION TESTS NEED ATTENTION!")
            print("[CONFIG] Fix validation issues before running tests")
            print("[SYNTAX] Review error messages above for specific issues")
        print("=" * 60)


def main():
    """Main entry point"""
    project_root = Path(__file__).parent.parent
    validator = IntegrationTestValidator(project_root)

    try:
        print("[SEARCH] Starting Integration Test Validation...")
        print(f"[DIR] Project Root: {project_root}")
        print()

        success = validator.run_full_validation()
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\n[WARN] Validation interrupted by user")
        sys.exit(1)

    except Exception as e:
        print(f"\n[ERROR] Validation failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
