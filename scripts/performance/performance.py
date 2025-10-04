#!/usr/bin/env python3
# Security: subprocess calls in this script use sys.executable with hardcoded,
# trusted arguments only. No user input is passed to subprocess. This is safe for
# internal performance tooling.

"""Unified Performance Runner - Consolidates All Performance Operations

Replaces 8 separate performance scripts with a single unified interface:
- ai_cost_optimizer.py → performance.py --ai-costs
- benchmark_golden_rules.py → performance.py --benchmark
- ci_performance_analyzer.py → performance.py --ci-analysis
- ci_performance_baseline.py → performance.py --baseline
- performance_audit.py → performance.py --audit
- pool_config_manager.py → performance.py --pool-config
- pool_optimizer.py → performance.py --pool-optimize
- pool_tuning_orchestrator.py → performance.py --pool-tune

Usage:
    python performance.py --ai-costs --analyze
    python performance.py --benchmark --incremental
    python performance.py --ci-analysis --days 30
    python performance.py --baseline --mode check
    python performance.py --audit --scan-all
    python performance.py --pool-config --get database_pool
    python performance.py --pool-optimize --collect 5
    python performance.py --pool-tune --analyze
    python performance.py --all --quick
"""

import argparse
import subprocess
import sys
from pathlib import Path

# Script directory
SCRIPTS_DIR = Path(__file__).parent

# Available performance operations
PERFORMANCE_SCRIPTS = {
    "ai-costs": "ai_cost_optimizer.py",
    "benchmark": "benchmark_golden_rules.py",
    "ci-analysis": "ci_performance_analyzer.py",
    "baseline": "ci_performance_baseline.py",
    "audit": "performance_audit.py",
    "pool-config": "pool_config_manager.py",
    "pool-optimize": "pool_optimizer.py",
    "pool-tune": "pool_tuning_orchestrator.py",
}


def run_script(script_name: str, args: list[str]) -> int:
    """Run a performance script with given arguments."""
    script_path = SCRIPTS_DIR / script_name

    if not script_path.exists():
        print(f"Error: Script not found: {script_path}")
        return 1

    cmd = [sys.executable, str(script_path)] + args
    print(f"\n{'=' * 80}")
    print(f"Running: {script_name}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'=' * 80}\n")

    result = subprocess.run(cmd, check=False)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(
        description="Unified Performance Runner - One tool for all performance operations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # AI cost optimization
  python performance.py --ai-costs --analyze
  python performance.py --ai-costs --days 30

  # Golden rules benchmarking
  python performance.py --benchmark
  python performance.py --benchmark --incremental

  # CI/CD performance analysis
  python performance.py --ci-analysis --days 30
  python performance.py --ci-analysis --repo-owner myorg --repo-name myrepo

  # Performance baseline checking
  python performance.py --baseline --mode create
  python performance.py --baseline --mode check --threshold 0.10

  # Code performance auditing
  python performance.py --audit --scan-all
  python performance.py --audit --path apps/

  # Pool configuration management
  python performance.py --pool-config --get database_pool
  python performance.py --pool-config --update database_pool

  # Pool optimization
  python performance.py --pool-optimize --collect 5
  python performance.py --pool-optimize --analyze

  # Pool tuning orchestration
  python performance.py --pool-tune --analyze
  python performance.py --pool-tune --apply --dry-run

  # Run all performance checks (quick)
  python performance.py --all --quick

  # Get help for specific operation
  python performance.py --ai-costs --help
  python performance.py --benchmark --help
""",
    )

    # Main operation flags
    parser.add_argument("--ai-costs", action="store_true", help="AI model cost analysis and optimization")
    parser.add_argument("--benchmark", action="store_true", help="Golden rules performance benchmarking")
    parser.add_argument("--ci-analysis", action="store_true", help="CI/CD pipeline performance analysis")
    parser.add_argument("--baseline", action="store_true", help="Performance baseline creation and regression checking")
    parser.add_argument("--audit", action="store_true", help="Code performance auditing")
    parser.add_argument("--pool-config", action="store_true", help="Connection pool configuration management")
    parser.add_argument("--pool-optimize", action="store_true", help="Connection pool optimization analysis")
    parser.add_argument("--pool-tune", action="store_true", help="Automated connection pool tuning")
    parser.add_argument("--all", action="store_true", help="Run all performance operations (use with --quick)")

    # Quick mode for --all
    parser.add_argument("--quick", action="store_true", help="Quick mode: run minimal checks (use with --all)")

    # Common options
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without executing")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")

    args, unknown_args = parser.parse_known_args()

    # Determine which operations to run
    operations = []
    if args.all:
        operations = list(PERFORMANCE_SCRIPTS.keys())
    else:
        if getattr(args, "ai_costs", False):
            operations.append("ai-costs")
        if args.benchmark:
            operations.append("benchmark")
        if getattr(args, "ci_analysis", False):
            operations.append("ci-analysis")
        if args.baseline:
            operations.append("baseline")
        if args.audit:
            operations.append("audit")
        if getattr(args, "pool_config", False):
            operations.append("pool-config")
        if getattr(args, "pool_optimize", False):
            operations.append("pool-optimize")
        if getattr(args, "pool_tune", False):
            operations.append("pool-tune")

    # If no operation specified, show help
    if not operations:
        parser.print_help()
        print("\n" + "=" * 80)
        print("AVAILABLE PERFORMANCE SCRIPTS:")
        print("=" * 80)
        for op, script in PERFORMANCE_SCRIPTS.items():
            print(f"  --{op:15} → {script}")
        return 0

    # Dry run mode
    if args.dry_run:
        print("DRY RUN MODE - Would execute:")
        for op in operations:
            script = PERFORMANCE_SCRIPTS[op]
            print(f"  - {script} with args: {unknown_args}")
        return 0

    # Execute operations
    exit_codes = []
    for op in operations:
        script = PERFORMANCE_SCRIPTS[op]

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
    print("PERFORMANCE ANALYSIS SUMMARY")
    print(f"{'=' * 80}")
    print(f"Operations run: {len(operations)}")
    print(f"Successful: {exit_codes.count(0)}")
    print(f"Failed: {len([c for c in exit_codes if c != 0])}")

    # Return non-zero if any operation failed
    return 0 if all(code == 0 for code in exit_codes) else 1


if __name__ == "__main__":
    sys.exit(main())
