#!/usr/bin/env python3
"""
Test runner for Hive Orchestrator
Runs integration tests and provides a simple test report.
"""

import sys
import subprocess
from pathlib import Path

def run_tests():
    """Run the integration tests"""
    test_dir = Path(__file__).parent / "tests"

    if not test_dir.exists():
        print("❌ Test directory not found")
        return 1

    print("🧪 Running Hive Orchestrator Integration Tests")
    print("=" * 50)

    try:
        # Try to run with pytest if available
        result = subprocess.run([
            sys.executable, "-m", "pytest",
            str(test_dir),
            "-v",
            "--tb=short"
        ], capture_output=True, text=True)

        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)

        if result.returncode == 0:
            print("✅ All tests passed!")
        else:
            print("❌ Some tests failed")

        return result.returncode

    except FileNotFoundError:
        # Fallback to running tests directly without pytest
        print("⚠️  pytest not found, running tests directly...")

        test_file = test_dir / "test_integration.py"
        if test_file.exists():
            result = subprocess.run([sys.executable, str(test_file)],
                                  capture_output=True, text=True)
            print(result.stdout)
            if result.stderr:
                print("STDERR:", result.stderr)
            return result.returncode
        else:
            print("❌ Test file not found")
            return 1

if __name__ == "__main__":
    sys.exit(run_tests())