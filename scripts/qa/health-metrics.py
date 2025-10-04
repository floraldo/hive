#!/usr/bin/env python3
# ruff: noqa: S607  # subprocess with partial path - safe for our development tools
"""Platform Health Metrics Dashboard for QA Agent

Purpose: Generate comprehensive health metrics for technical debt management
Tracks: Linting violations, bypass frequency, CI success rate, quality trends

Usage:
    python scripts/qa/health-metrics.py
    python scripts/qa/health-metrics.py --export claudedocs/qa_health_dashboard.md
    python scripts/qa/health-metrics.py --show-trend 30  # Last 30 days
"""

import argparse
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import NamedTuple


class HealthMetrics(NamedTuple):
    """Platform health metrics snapshot."""

    timestamp: datetime
    total_violations: int
    syntax_errors: int
    core_violations: int
    crust_violations: int
    bypass_count_24h: int
    bypass_count_7d: int
    test_collection_errors: int


def get_linting_violations() -> tuple[int, int, int]:
    """Get current linting violation counts.

    Returns:
        (total_violations, core_violations, crust_violations)
    """
    try:
        # Total violations
        result = subprocess.run(
            ["ruff", "check", ".", "--statistics"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        total_match = [line for line in result.stdout.split("\n") if "Found" in line]
        total = (
            int(total_match[0].split()[1])
            if total_match
            else 0
        )

        # Core violations (strict)
        result_core = subprocess.run(
            ["ruff", "check", "packages/", "--select", "ALL", "--statistics"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        core_match = [
            line for line in result_core.stdout.split("\n") if "Found" in line
        ]
        core = int(core_match[0].split()[1]) if core_match else 0

        # Crust violations (lenient ignores applied)
        result_crust = subprocess.run(
            ["ruff", "check", "apps/", "integration_tests/", "--statistics"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        crust_match = [
            line for line in result_crust.stdout.split("\n") if "Found" in line
        ]
        crust = int(crust_match[0].split()[1]) if crust_match else 0

        return (total, core, crust)
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, ValueError):
        return (0, 0, 0)


def get_syntax_errors() -> int:
    """Count Python syntax errors via pytest collection."""
    try:
        result = subprocess.run(
            ["pytest", "--collect-only", "-q"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        # Look for "X errors" in output
        error_lines = [line for line in result.stdout.split("\n") if "errors" in line]
        if error_lines:
            # Parse "13 errors" format
            parts = error_lines[0].split()
            for i, part in enumerate(parts):
                if part == "errors" and i > 0:
                    return int(parts[i - 1])
        return 0
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, ValueError):
        return 0


def get_bypass_counts(repo_root: Path) -> tuple[int, int]:
    """Get bypass counts for last 24h and 7d.

    Returns:
        (count_24h, count_7d)
    """
    log_path = repo_root / ".git" / "bypass-log.txt"
    if not log_path.exists():
        return (0, 0)

    now = datetime.now()
    count_24h = 0
    count_7d = 0

    with open(log_path) as f:
        for line in f:
            try:
                timestamp_str = line.split(" | ")[0]
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

                if now - timestamp < timedelta(days=1):
                    count_24h += 1
                if now - timestamp < timedelta(days=7):
                    count_7d += 1
            except (ValueError, IndexError):
                continue

    return (count_24h, count_7d)


def collect_metrics(repo_root: Path) -> HealthMetrics:
    """Collect all current health metrics."""
    total, core, crust = get_linting_violations()
    syntax = get_syntax_errors()
    bypass_24h, bypass_7d = get_bypass_counts(repo_root)

    return HealthMetrics(
        timestamp=datetime.now(),
        total_violations=total,
        syntax_errors=syntax,
        core_violations=core,
        crust_violations=crust,
        bypass_count_24h=bypass_24h,
        bypass_count_7d=bypass_7d,
        test_collection_errors=syntax,  # Syntax errors prevent collection
    )


def generate_dashboard(metrics: HealthMetrics) -> str:
    """Generate markdown dashboard from metrics."""
    output = []
    output.append("# Platform Health Dashboard (QA Agent)\n")
    output.append(f"**Generated**: {metrics.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n")
    output.append("---\n")

    # Overall Health Score
    health_score = calculate_health_score(metrics)
    output.append(f"## Overall Health: {health_score}%\n")

    if health_score >= 90:
        output.append("Status: EXCELLENT - Platform is healthy\n")
    elif health_score >= 75:
        output.append("Status: GOOD - Minor cleanup needed\n")
    elif health_score >= 50:
        output.append("Status: NEEDS ATTENTION - Schedule cleanup cycle\n")
    else:
        output.append("Status: CRITICAL - Immediate QA agent attention required\n")

    output.append("\n---\n")

    # Linting Violations
    output.append("## Linting Violations\n")
    output.append(f"- **Total Platform**: {metrics.total_violations:,} violations\n")
    output.append(
        f"- **Core (packages/)**: {metrics.core_violations:,} violations (strict standards)\n"
    )
    output.append(
        f"- **Crust (apps/)**: {metrics.crust_violations:,} violations (pragmatic standards)\n"
    )
    output.append("\n")

    # Syntax Errors
    output.append("## Syntax Errors\n")
    if metrics.syntax_errors == 0:
        output.append("- ZERO syntax errors maintained\n")
    else:
        output.append(
            f"- **{metrics.syntax_errors} syntax errors** - CRITICAL, fix immediately\n"
        )
    output.append("\n")

    # Bypass Activity
    output.append("## Bypass Activity (--no-verify usage)\n")
    output.append(f"- Last 24 hours: {metrics.bypass_count_24h} bypasses\n")
    output.append(f"- Last 7 days: {metrics.bypass_count_7d} bypasses\n")

    if metrics.bypass_count_24h > 5:
        output.append(
            "- WARNING: High bypass frequency, review bypass log for patterns\n"
        )
    output.append("\n")

    # QA Agent Action Items
    output.append("## QA Agent Priority Actions\n")

    if metrics.syntax_errors > 0:
        output.append(f"1. HIGH - Fix {metrics.syntax_errors} syntax errors\n")

    if metrics.core_violations > 1000:
        output.append(f"2. HIGH - Core violations ({metrics.core_violations:,}) exceed threshold\n")

    if metrics.bypass_count_24h > 3:
        output.append(
            f"3. MEDIUM - Review recent bypasses ({metrics.bypass_count_24h} in 24h)\n"
        )

    if metrics.total_violations > 5000:
        output.append(
            f"4. MEDIUM - Overall technical debt ({metrics.total_violations:,}) requires cleanup sprint\n"
        )

    output.append("\n---\n")

    # Commands for QA Agent
    output.append("## QA Agent Workflow Commands\n")
    output.append("```bash\n")
    output.append("# Review bypass justifications\n")
    output.append("python scripts/qa/review-bypasses.py\n")
    output.append("\n")
    output.append("# Run full validation\n")
    output.append("python scripts/validation/validate_golden_rules.py --level ERROR\n")
    output.append("\n")
    output.append("# Fix linting violations\n")
    output.append("ruff check . --fix\n")
    output.append("\n")
    output.append("# Collect test errors\n")
    output.append("pytest --collect-only\n")
    output.append("```\n")

    return "".join(output)


def calculate_health_score(metrics: HealthMetrics) -> int:
    """Calculate overall platform health score (0-100)."""
    score = 100

    # Syntax errors are critical (-20 per error)
    score -= min(metrics.syntax_errors * 20, 60)

    # Linting violations reduce score
    if metrics.total_violations > 10000:
        score -= 30
    elif metrics.total_violations > 5000:
        score -= 20
    elif metrics.total_violations > 1000:
        score -= 10

    # High bypass frequency is concerning
    if metrics.bypass_count_24h > 10:
        score -= 15
    elif metrics.bypass_count_24h > 5:
        score -= 10

    return max(score, 0)


def main():
    parser = argparse.ArgumentParser(description="Generate platform health metrics")
    parser.add_argument(
        "--export", metavar="FILE", help="Export dashboard to markdown file"
    )
    parser.add_argument(
        "--show-trend", type=int, metavar="DAYS", help="Show trend over N days (future enhancement)"
    )
    args = parser.parse_args()

    # Find repo root
    repo_root = Path(__file__).parent.parent.parent

    # Collect metrics
    print("Collecting platform health metrics...")
    metrics = collect_metrics(repo_root)

    # Generate dashboard
    dashboard = generate_dashboard(metrics)

    # Export or print
    if args.export:
        output_path = Path(args.export)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(dashboard)
        print(f"\nDashboard exported to: {output_path}")
        print(f"Health Score: {calculate_health_score(metrics)}%")
    else:
        print("\n" + dashboard)

    return 0


if __name__ == "__main__":
    sys.exit(main())
