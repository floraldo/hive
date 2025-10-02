#!/usr/bin/env python3
"""
Unified Monitoring Runner - Consolidates All Monitoring Operations

Replaces 5 separate monitoring scripts with a single unified interface:
- alert_validation_tracker.py → monitor.py --alerts
- log_intelligence.py → monitor.py --logs
- predictive_analysis_runner.py → monitor.py --predict
- production_monitor.py → monitor.py --production
- test_monitoring_integration.py → monitor.py --test

Usage:
    python monitor.py --alerts --validate
    python monitor.py --logs --hours 24
    python monitor.py --predict --run
    python monitor.py --production --check-health
    python monitor.py --test --integration
    python monitor.py --all --quick
"""

import argparse
import subprocess
import sys
from pathlib import Path

# Script directory
SCRIPTS_DIR = Path(__file__).parent

# Available monitoring operations
MONITORING_SCRIPTS = {
    "alerts": "alert_validation_tracker.py",
    "logs": "log_intelligence.py",
    "predict": "predictive_analysis_runner.py",
    "production": "production_monitor.py",
    "test": "test_monitoring_integration.py",
}


def run_script(script_name: str, args: list[str]) -> int:
    """Run a monitoring script with given arguments."""
    script_path = SCRIPTS_DIR / script_name

    if not script_path.exists():
        print(f"Error: Script not found: {script_path}")
        return 1

    cmd = [sys.executable, str(script_path)] + args
    print(f"\n{'=' * 80}")
    print(f"Running: {script_name}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'=' * 80}\n")

    result = subprocess.run(cmd)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(
        description="Unified Monitoring Runner - One tool for all monitoring operations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Alert validation
  python monitor.py --alerts --validate
  python monitor.py --alerts --report

  # Log intelligence
  python monitor.py --logs --hours 24 --log-dirs logs
  python monitor.py --logs --output-format markdown

  # Predictive analysis
  python monitor.py --predict --run
  python monitor.py --predict --check

  # Production monitoring
  python monitor.py --production --check-health
  python monitor.py --production --endpoints all

  # Integration tests
  python monitor.py --test --integration
  python monitor.py --test --smoke

  # Run all monitoring checks (quick)
  python monitor.py --all --quick

  # Get help for specific operation
  python monitor.py --alerts --help
  python monitor.py --logs --help
""",
    )

    # Main operation flags
    parser.add_argument("--alerts", action="store_true", help="Alert validation tracking operations")
    parser.add_argument("--logs", action="store_true", help="Log intelligence and analysis")
    parser.add_argument("--predict", action="store_true", help="Predictive failure analysis")
    parser.add_argument("--production", action="store_true", help="Production health monitoring")
    parser.add_argument("--test", action="store_true", help="Monitoring integration tests")
    parser.add_argument("--all", action="store_true", help="Run all monitoring operations (use with --quick)")

    # Quick mode for --all
    parser.add_argument("--quick", action="store_true", help="Quick mode: run minimal checks (use with --all)")

    # Common options
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without executing")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")

    args, unknown_args = parser.parse_known_args()

    # Determine which operations to run
    operations = []
    if args.all:
        operations = list(MONITORING_SCRIPTS.keys())
    else:
        if args.alerts:
            operations.append("alerts")
        if args.logs:
            operations.append("logs")
        if args.predict:
            operations.append("predict")
        if args.production:
            operations.append("production")
        if args.test:
            operations.append("test")

    # If no operation specified, show help
    if not operations:
        parser.print_help()
        print("\n" + "=" * 80)
        print("AVAILABLE MONITORING SCRIPTS:")
        print("=" * 80)
        for op, script in MONITORING_SCRIPTS.items():
            print(f"  --{op:12} → {script}")
        return 0

    # Dry run mode
    if args.dry_run:
        print("DRY RUN MODE - Would execute:")
        for op in operations:
            script = MONITORING_SCRIPTS[op]
            print(f"  - {script} with args: {unknown_args}")
        return 0

    # Execute operations
    exit_codes = []
    for op in operations:
        script = MONITORING_SCRIPTS[op]

        # Build arguments for this script
        script_args = unknown_args.copy()

        # Add --quick flag if in quick mode
        if args.quick and "--quick" not in script_args:
            script_args.append("--quick")

        # Add --verbose if requested
        if args.verbose and "--verbose" not in script_args:
            script_args.append("--verbose")

        # Run the script
        exit_code = run_script(script, script_args)
        exit_codes.append(exit_code)

        if exit_code != 0:
            print(f"\n⚠️  Warning: {script} exited with code {exit_code}")

    # Summary
    print(f"\n{'=' * 80}")
    print("MONITORING SUMMARY")
    print(f"{'=' * 80}")
    print(f"Operations run: {len(operations)}")
    print(f"Successful: {exit_codes.count(0)}")
    print(f"Failed: {len([c for c in exit_codes if c != 0])}")

    # Return non-zero if any operation failed
    return 0 if all(code == 0 for code in exit_codes) else 1


if __name__ == "__main__":
    sys.exit(main())
