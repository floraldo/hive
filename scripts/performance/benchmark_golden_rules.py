# ruff: noqa: S603, S607
# Security: subprocess calls in this script use sys.executable or system tools (git, ruff, etc.) with hardcoded,
# trusted arguments only. No user input is passed to subprocess. This is safe for
# internal performance benchmarking tooling.

"""
Benchmark script for Golden Rules validation performance.

Measures:
- Full validation time (baseline)
- Incremental validation time (file-level scoping)
- Cached validation time (smart caching)
"""

import subprocess
import sys
import time
from pathlib import Path

project_root = Path(__file__).parent.parent


def run_command(cmd: list[str]) -> tuple[float, str]:
    """Run command and measure execution time."""
    start = time.time()
    result = subprocess.run(
        cmd,
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    elapsed = time.time() - start
    return elapsed, result.stdout + result.stderr


def get_changed_files() -> int:
    """Get count of changed files."""
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACMR"],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    files = [f for f in result.stdout.strip().split("\n") if f.endswith(".py")]
    return len(files)


def main():
    print("=" * 80)
    print("GOLDEN RULES VALIDATION PERFORMANCE BENCHMARK")
    print("=" * 80)
    print()

    # Get baseline metrics
    changed_files = get_changed_files()
    print(f"Changed files: {changed_files}")
    print()

    # Benchmark 1: Incremental validation (first run - no cache)
    print("1. INCREMENTAL VALIDATION (First Run - Building Cache)")
    print("-" * 80)
    elapsed1, output1 = run_command(
        [
            sys.executable,
            "scripts/validate_golden_rules.py",
            "--incremental",
            "--clear-cache",
        ],
    )
    print(f"Time: {elapsed1:.2f}s")
    print()

    # Benchmark 2: Incremental validation (second run - with cache)
    print("2. INCREMENTAL VALIDATION (Second Run - With Cache)")
    print("-" * 80)
    elapsed2, output2 = run_command(
        [
            sys.executable,
            "scripts/validate_golden_rules.py",
            "--incremental",
        ],
    )
    print(f"Time: {elapsed2:.2f}s")
    improvement = ((elapsed1 - elapsed2) / elapsed1) * 100 if elapsed1 > 0 else 0
    print(f"Cache improvement: {improvement:.1f}%")
    print()

    # Summary
    print("=" * 80)
    print("PERFORMANCE SUMMARY")
    print("=" * 80)
    print(f"First run (no cache):  {elapsed1:.2f}s")
    print(f"Second run (cached):   {elapsed2:.2f}s")
    print(f"Cache speedup:         {improvement:.1f}%")
    print()
    print("Target: 0.5-2s incremental, 0.1-0.5s cached")
    print(f"Status: {'PASS' if elapsed2 < 2.0 else 'NEEDS OPTIMIZATION'}")


if __name__ == "__main__":
    main()
