from hive_logging import get_logger

logger = get_logger(__name__)
#!/usr/bin/env python3
"""
Test runner for Hive Orchestrator
Runs integration tests and provides a simple test report.
"""

import subprocess
import sys
from pathlib import Path


def run_tests():
    """Run the integration tests"""
    test_dir = Path(__file__).parent / "tests"

    if not test_dir.exists():
        logger.info("❌ Test directory not found")
        return 1

    logger.info("🧪 Running Hive Orchestrator Integration Tests")
    logger.info("=" * 50)

    try:
        # Try to run with pytest if available
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_dir), "-v", "--tb=short"], capture_output=True, text=True,
        )

        logger.info(result.stdout)
        if result.stderr:
            logger.info("STDERR:", result.stderr)

        if result.returncode == 0:
            logger.info("✅ All tests passed!")
        else:
            logger.error("❌ Some tests failed")

        return result.returncode

    except FileNotFoundError:
        # Fallback to running tests directly without pytest
        logger.info("⚠️  pytest not found, running tests directly...")

        test_file = test_dir / "test_integration.py"
        if test_file.exists():
            result = subprocess.run([sys.executable, str(test_file)], capture_output=True, text=True)
            logger.info(result.stdout)
            if result.stderr:
                logger.info("STDERR:", result.stderr)
            return result.returncode
        else:
            logger.info("❌ Test file not found")
            return 1


if __name__ == "__main__":
    sys.exit(run_tests())
