from hive_logging import get_logger

logger = get_logger(__name__)
#!/usr/bin/env python
"""Integration test script for EcoSystemiser v3.0 Presentation Layer.

This script validates the complete workflow from Discovery Engine
execution through to report generation and presentation.
"""

import json
import subprocess
import sys
import tempfile
import time
import webbrowser
from pathlib import Path
from typing import Any


def run_command(cmd: str) -> tuple[int, str, str]:
    """Execute a shell command and capture output."""
    logger.info(f"Running: {cmd}")
    # Split command into arguments for security
    import shlex
    cmd_args = shlex.split(cmd),
    result = subprocess.run(
        cmd_args,
        capture_output=True,
        text=True
    )
    return result.returncode, result.stdout, result.stderr


def create_test_config() -> dict[str, Any]:
    """Create a minimal test configuration for GA optimization."""
    return {
        "system": {
            "name": "test_system",
            "description": "Integration test system"
        },
        "optimization": {
            "algorithm": "nsga2",
            "objectives": ["minimize_cost", "maximize_efficiency"],
            "population_size": 10,
            "generations": 5,
            "variables": [
                {
                    "name": "solar_capacity",
                    "min": 1.0,
                    "max": 10.0
                },
                {
                    "name": "battery_capacity",
                    "min": 1.0,
                    "max": 20.0
                }
            ]
        }
    }


def create_mc_config() -> dict[str, Any]:
    """Create a minimal test configuration for MC uncertainty analysis."""
    return {
        "system": {
            "name": "test_mc_system",
            "description": "Monte Carlo test system"
        },
        "uncertainty": {
            "method": "monte_carlo",
            "samples": 100,
            "sampling_method": "lhs",
            "parameters": [
                {
                    "name": "demand_factor",
                    "distribution": "normal",
                    "mean": 1.0,
                    "std": 0.1
                },
                {
                    "name": "efficiency",
                    "distribution": "uniform",
                    "min": 0.8,
                    "max": 0.95
                }
            ]
        }
    }


def test_ga_workflow() -> None:
    """Test GA optimization to report generation workflow."""
    logger.info("\n" + "="*60)
    logger.info("Testing GA Optimization Workflow")
    logger.info("="*60)

    # Create temporary config file
    config = create_test_config()
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config, f)
        config_path = f.name

    try:
        # Run optimization with report generation
        cmd = f"ecosystemiser discover optimize {config_path} --algorithm nsga2 --report"
        returncode, stdout, stderr = run_command(cmd)

        if returncode != 0:
            logger.info(f"GA optimization failed: {stderr}")
            return False

        logger.info("GA optimization completed successfully")

        # Extract study ID from output
        lines = stdout.split('\n'),
        study_id = None
        for line in lines:
            if 'Study ID:' in line:
                study_id = line.split('Study ID:')[1].strip()
                break

        if study_id:
            logger.info(f"Generated study ID: {study_id}")

            # Test report generation via CLI
            results_file = f"results/ga_optimization_{study_id}.json"
            if Path(results_file).exists():
                cmd = f"ecosystemiser report generate {results_file}"
                returncode, stdout, stderr = run_command(cmd)

                if returncode == 0:
                    logger.info("Report generation successful")
                    return True
            else:
                logger.info(f"Results file not found: {results_file}")

        return False

    finally:
        Path(config_path).unlink(missing_ok=True)


def test_mc_workflow() -> None:
    """Test MC uncertainty analysis to report generation workflow."""
    logger.info("\n" + "="*60)
    logger.info("Testing Monte Carlo Uncertainty Workflow")
    logger.info("="*60)

    # Create temporary config file
    config = create_mc_config()
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config, f)
        config_path = f.name

    try:
        # Run uncertainty analysis with report generation
        cmd = f"ecosystemiser discover analyze {config_path} --method monte_carlo --report"
        returncode, stdout, stderr = run_command(cmd)

        if returncode != 0:
            logger.info(f"MC analysis failed: {stderr}")
            return False

        logger.info("MC analysis completed successfully")

        # Extract study ID from output
        lines = stdout.split('\n'),
        study_id = None
        for line in lines:
            if 'Study ID:' in line:
                study_id = line.split('Study ID:')[1].strip()
                break

        if study_id:
            logger.info(f"Generated study ID: {study_id}")

            # Test report generation
            results_file = f"results/mc_uncertainty_{study_id}.json"
            if Path(results_file).exists():
                cmd = f"ecosystemiser report generate {results_file}"
                returncode, stdout, stderr = run_command(cmd)

                if returncode == 0:
                    logger.info("Report generation successful")
                    return True
            else:
                logger.info(f"Results file not found: {results_file}")

        return False

    finally:
        Path(config_path).unlink(missing_ok=True)


def test_flask_app() -> None:
    """Test Flask reporting application startup."""
    logger.info("\n" + "="*60)
    logger.info("Testing Flask Reporting Application")
    logger.info("="*60)

    # Start Flask app in background
    cmd_args = ["ecosystemiser", "report", "serve", "--port", "5001"]
    process = subprocess.Popen(
        cmd_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # Give Flask time to start
    time.sleep(3)

    try:
        # Check if server is running
        import requests
        response = requests.get("http://localhost:5001/", timeout=5)

        if response.status_code == 200:
            logger.info("Flask app running successfully")
            logger.info("Opening browser to view reports...")
            webbrowser.open("http://localhost:5001/")
            return True
        else:
            logger.info(f"Flask app returned status: {response.status_code}")
            return False

    except Exception as e:
        logger.info(f"Could not connect to Flask app: {e}")
        return False

    finally:
        # Terminate Flask process
        process.terminate()
        process.wait()


def main() -> None:
    """Run all integration tests."""
    logger.info("\nEcoSystemiser v3.0 Presentation Layer Integration Tests")
    logger.info("="*60)

    results = {
        "GA Workflow": test_ga_workflow(),
        "MC Workflow": test_mc_workflow(),
        "Flask App": test_flask_app()
    }

    logger.info("\n" + "="*60)
    logger.info("Test Results Summary")
    logger.info("="*60)

    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        logger.info(f"{test_name}: {status}")

    all_passed = all(results.values())

    if all_passed:
        logger.info("\n🎉 All tests passed! Presentation layer is ready for deployment.")
        return 0
    else:
        logger.info("\n⚠️ Some tests failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
