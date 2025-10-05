#!/usr/bin/env python
# Security: subprocess calls in this script use sys.executable with hardcoded,
# trusted arguments only. No user input is passed to subprocess.

"""Ultimate CLI Test Suite for EcoSystemiser
Cross-platform, comprehensive end-to-end testing
"""

import platform
import shlex
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from hive_logging import get_logger

logger = get_logger(__name__)

# --- Configuration ---
PROJECT_ROOT = Path(__file__).parent
OUTPUT_DIR = PROJECT_ROOT / "cli_test_output"
EPW_FILE = PROJECT_ROOT / "tests/test_data/USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw"
ECOSYS_CMD = f"{sys.executable} -m EcoSystemiser.cli"


# --- ANSI Color Codes for Output ---
class TColors:
    HEADER = ("\033[95m",)
    OKBLUE = ("\033[94m",)
    OKGREEN = ("\033[92m",)
    WARNING = ("\033[93m",)
    FAIL = ("\033[91m",)
    ENDC = ("\033[0m",)
    BOLD = "\033[1m"


def run_command(name: str, command: str, expected_to_fail: bool = False) -> bool:
    """Runs a command, captures its output, and reports success/failure."""
    logger.info(f"\n{TColors.HEADER}--- [RUNNING] {name} ---{TColors.ENDC}")
    logger.info(f"{TColors.OKBLUE}CMD: {command}{TColors.ENDC}")

    # For Windows, we need to handle paths differently
    if platform.system() == "Windows":
        # Don't use shlex on Windows for complex commands
        args = command
    else:
        args = (shlex.split(command),)

    try:
        # Run the command, capture output, and check for errors
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            check=not expected_to_fail,  # Don't raise on expected failures,
            shell=platform.system() == "Windows",  # Use shell on Windows,
            cwd=PROJECT_ROOT,  # Run from ecosystemiser directory
        )

        if expected_to_fail:
            if result.returncode != 0:
                logger.error(
                    f"{TColors.OKGREEN}[✓] SUCCESS: {name} (failed as expected){TColors.ENDC}",
                )
                return True
            logger.error(f"{TColors.FAIL}[✗] FAIL: {name} (should have failed but succeeded){TColors.ENDC}")
            return False
        logger.info(f"{TColors.OKGREEN}[✓] SUCCESS: {name} (completed){TColors.ENDC}")
        # Print the last few lines of output for context
        if result.stdout:
            output_lines = result.stdout.strip().split("\n")
            for line in output_lines[-3:]:
                logger.info(f"    {line}")
        return True

    except FileNotFoundError:
        logger.error(f"{TColors.FAIL}[✗] FAIL: {name} (FileNotFoundError){TColors.ENDC}")
        logger.error("    ERROR: Command not found. Is the package installed in editable mode?")
        return False

    except subprocess.CalledProcessError as e:
        if expected_to_fail:
            logger.error(f"{TColors.OKGREEN}[✓] SUCCESS: {name} (failed as expected){TColors.ENDC}")
            return True
        logger.error(f"{TColors.FAIL}[✗] FAIL: {name} (exit code {e.returncode}){TColors.ENDC}")
        logger.info("    --- STDERR ---")
        if e.stderr:
            for line in e.stderr.split("\n")[:5]:  # First 5 lines of error
                logger.info(f"    {line}")
        return False


def verify_output_file(filepath: Path, test_name: str) -> bool:
    """Verify that output file exists and has reasonable content."""
    if not filepath.exists():
        logger.warning(f"    {TColors.WARNING}Warning: Output file not created: {filepath}{TColors.ENDC}")
        return False

    size = filepath.stat().st_size
    if size == 0:
        logger.warning(f"    {TColors.WARNING}Warning: Output file is empty: {filepath}{TColors.ENDC}")
        return False

    logger.info(f"    Output file created: {filepath.name} ({size:,} bytes)")
    return True


def main() -> None:
    """Main function to run the test suite."""
    logger.info(f"{TColors.BOLD}========================================{TColors.ENDC}")
    logger.info(f"{TColors.BOLD}   EcoSystemiser CLI Test Suite{TColors.ENDC}")
    logger.info(f"{TColors.BOLD}   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{TColors.ENDC}")
    logger.info(f"{TColors.BOLD}========================================{TColors.ENDC}")

    # --- Setup ---
    logger.info(f"\n{TColors.BOLD}--- Setting up test environment ---{TColors.ENDC}")
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Test outputs will be saved to: {OUTPUT_DIR}")

    # Create minimal EPW test file if needed
    if not EPW_FILE.exists():
        logger.info(f"Creating sample EPW file at: {EPW_FILE}")
        EPW_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(EPW_FILE, "w") as f:
            f.write(
                """LOCATION,Chicago Ohare Intl Ap,IL,USA,TMY3,725300,41.98,-87.90,-6.0,201.0,
DESIGN CONDITIONS,1,Climate Design Data 2009 ASHRAE Handbook,
TYPICAL/EXTREME PERIODS,6,Summer - Week Nearest Max Temperature For Period,
GROUND TEMPERATURES,3,.5,,,20.0,20.0,20.0,20.0,20.0,20.0,20.0,20.0,20.0,20.0,20.0,20.0,
HOLIDAYS/DAYLIGHT SAVING,No,0,0,0,
COMMENTS 1,Custom/User Format
COMMENTS 2,Example EPW for testing
DATA PERIODS,1,1,Data,Sunday, 1/ 1,12/31
1990,1,1,1,0,?9?9?9?9E0?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9*9*9*9*9*9,-3.3,-7.2,73,99000,0,0,253,0,0,0,0,0,0,0,280,2.1,0,0,16.1,77777,9,999999999,89,0.0820,0,88,999,999
1990,1,1,2,0,?9?9?9?9E0?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9*9*9*9*9*9,-3.9,-7.8,73,99000,0,0,251,0,0,0,0,0,0,0,270,2.6,0,0,16.1,77777,9,999999999,89,0.0820,0,88,999,999
""",
            )

    # Define all test cases
    test_cases = [
        {
            "name": "Test 1: Basic NASA POWER Request",
            "command": f'{ECOSYS_CMD} climate get --loc "38.7,-9.1" --year 2019 --vars "temp_air,ghi" --source "nasa_power" --out "{OUTPUT_DIR / "nasa_power.parquet"}"',
            "output_file": OUTPUT_DIR / "nasa_power.parquet",
        },
        {
            "name": "Test 2: JSON Output Format",
            "command": f'{ECOSYS_CMD} climate get --loc "40.7,-74.0" --year 2022 --source "nasa_power" --vars "temp_air" --json-out "{OUTPUT_DIR / "nyc_2022.json"}"',
            "output_file": OUTPUT_DIR / "nyc_2022.json",
        },
        {
            "name": "Test 3: Statistics Generation",
            "command": f'{ECOSYS_CMD} climate get --loc "34.0,-118.2" --start "2023-06-01" --end "2023-06-30" --source "nasa_power" --stats --out "{OUTPUT_DIR / "la_june_stats.parquet"}"',
            "output_file": OUTPUT_DIR / "la_june_stats.parquet",
        },
        {
            "name": "Test 4: Local EPW File Processing",
            "command": f'{ECOSYS_CMD} climate get --loc "41.9,-87.9" --file "{EPW_FILE}" --source "file_epw" --vars "temp_air,wind_speed" --out "{OUTPUT_DIR / "chicago_epw.parquet"}"',
            "output_file": OUTPUT_DIR / "chicago_epw.parquet",
        },
        {
            "name": "Test 5: Different Time Resolution",
            "command": f'{ECOSYS_CMD} climate get --loc "51.5,-0.1" --start "2023-01-01" --end "2023-01-07" --source "nasa_power" --resolution "3H" --out "{OUTPUT_DIR / "london_3h.parquet"}"',
            "output_file": OUTPUT_DIR / "london_3h.parquet",
        },
    ]

    # Add expected failure tests
    failure_tests = [
        {
            "name": "Test 6: Invalid Coordinates (Expected Failure)",
            "command": f'{ECOSYS_CMD} climate get --loc "999,999" --year 2023 --source "nasa_power"',
            "expected_to_fail": True,
        },
        {
            "name": "Test 7: Invalid Variables (Expected Failure)",
            "command": f'{ECOSYS_CMD} climate get --loc "40.7,-74.0" --year 2023 --vars "invalid_var" --source "nasa_power"',
            "expected_to_fail": True,
        },
    ]

    results = []

    # Run regular tests
    logger.info(f"\n{TColors.BOLD}--- Running Success Tests ---{TColors.ENDC}")
    for test in test_cases:
        success = run_command(test["name"], test["command"])
        results.append(success)

        # Verify output file if test succeeded
        if success and "output_file" in test:
            verify_output_file(test["output_file"], test["name"])

    # Run failure tests
    logger.error(f"\n{TColors.BOLD}--- Running Expected Failure Tests ---{TColors.ENDC}")
    for test in failure_tests:
        success = run_command(
            test["name"],
            test["command"],
            expected_to_fail=test.get("expected_to_fail", False),
        )
        results.append(success)

    # --- Summary ---
    passed = (sum(1 for r in results if r),)
    failed = (len(results) - passed,)

    logger.info(f"\n{TColors.BOLD}========================================{TColors.ENDC}")
    logger.info(f"{TColors.BOLD}         TEST SUITE SUMMARY{TColors.ENDC}")
    logger.info(f"{TColors.BOLD}========================================{TColors.ENDC}")
    logger.info(f"Total Tests: {len(results)}")
    logger.info(f"{TColors.OKGREEN}Passed: {passed}{TColors.ENDC}")
    logger.error(f"{TColors.FAIL}Failed: {failed}{TColors.ENDC}")

    if OUTPUT_DIR.exists():
        output_files = list(OUTPUT_DIR.glob("*"))
        if output_files:
            logger.info(f"\nGenerated {len(output_files)} output files:")
            for f in output_files:
                logger.info(f"  - {f.name} ({f.stat().st_size:,} bytes)")

    if failed == 0:
        logger.info(f"\n{TColors.BOLD}{TColors.OKGREEN}✅ All tests passed!{TColors.ENDC}")

        # Ask about cleanup
        cleanup = input(f"\n{TColors.BOLD}Delete test output directory? (y/N): {TColors.ENDC}")
        if cleanup.lower() == "y":
            shutil.rmtree(OUTPUT_DIR)
            logger.info("Test output directory cleaned up.")

        sys.exit(0)
    else:
        logger.error(f"\n{TColors.BOLD}{TColors.FAIL}❌ Some tests failed.{TColors.ENDC}")
        logger.info(f"Output logs retained in: {OUTPUT_DIR}")
        sys.exit(1)


if __name__ == "__main__":
    main()
