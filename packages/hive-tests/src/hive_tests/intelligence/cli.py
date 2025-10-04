"""Command-line interface for test intelligence.

Provides commands for analyzing test health, detecting flaky tests,
and viewing failure trends.
"""
import argparse
import sys
from datetime import datetime

from rich.console import Console
from rich.table import Table

from .analyzer import TestIntelligenceAnalyzer
from .storage import TestIntelligenceStorage


def cmd_status(args):
    """Show current platform test health status."""
    console = Console()
    storage = TestIntelligenceStorage()
    analyzer = TestIntelligenceAnalyzer(storage)

    console.print("\n[bold cyan]Platform Test Health Dashboard[/bold cyan]")
    console.print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Get recent runs
    recent_runs = storage.get_recent_runs(limit=args.days)

    if not recent_runs:
        console.print("[yellow]No test data available. Run tests with the intelligence plugin enabled.[/yellow]")
        return

    latest_run = recent_runs[0]

    # Overall statistics
    console.print("[bold]Latest Test Run:[/bold]")
    console.print(f"  Total Tests: {latest_run.total_tests}")
    console.print(f"  Passed: [green]{latest_run.passed}[/green]")
    console.print(f"  Failed: [red]{latest_run.failed}[/red]")
    console.print(f"  Errors: [red]{latest_run.errors}[/red]")
    console.print(f"  Skipped: [yellow]{latest_run.skipped}[/yellow]")
    console.print(f"  Pass Rate: [{'green' if latest_run.pass_rate > 80 else 'yellow'}]{latest_run.pass_rate:.1f}%[/]")
    console.print(f"  Duration: {latest_run.duration_seconds:.2f}s\n")

    # Package health
    package_health = analyzer.analyze_package_health(days=args.days)

    if package_health:
        console.print("[bold]Package Health (Last {args.days} Days):[/bold]")

        table = Table()
        table.add_column("Package", style="cyan")
        table.add_column("Tests", justify="right")
        table.add_column("Pass Rate", justify="right")
        table.add_column("Trend", justify="center")
        table.add_column("Flaky", justify="right")
        table.add_column("Avg Duration", justify="right")

        for health in package_health[:15]:  # Top 15 packages
            # Color code based on health
            if health.pass_rate >= 95:
                pass_color = "green"
                status_icon = "[OK]"
            elif health.pass_rate >= 80:
                pass_color = "yellow"
                status_icon = "[!]"
            else:
                pass_color = "red"
                status_icon = "[X]"

            # Trend indicators
            if health.trend_direction == "improving":
                trend = f"[green]UP +{health.trend_percentage:.1f}%[/green]"
            elif health.trend_direction == "degrading":
                trend = f"[red]DN {health.trend_percentage:.1f}%[/red]"
            else:
                trend = "[dim]-> stable[/dim]"

            table.add_row(
                f"{status_icon} {health.package_name}",
                str(health.total_tests),
                f"[{pass_color}]{health.pass_rate:.1f}%[/{pass_color}]",
                trend,
                f"[red]{health.flaky_count}[/red]" if health.flaky_count > 0 else "0",
                f"{health.avg_duration_ms:.0f}ms",
            )

        console.print(table)


def cmd_flaky(args):
    """Detect and report flaky tests."""
    console = Console()
    analyzer = TestIntelligenceAnalyzer()

    console.print("\n[bold cyan]Flaky Test Detection[/bold cyan]\n")

    flaky_tests = analyzer.detect_flaky_tests(threshold=args.threshold)

    if not flaky_tests:
        console.print("[green]No flaky tests detected! All tests are stable.[/green]")
        return

    console.print(f"[red]Found {len(flaky_tests)} flaky tests:[/red]\n")

    for i, flaky in enumerate(flaky_tests[:args.limit], 1):
        console.print(f"[bold]{i}. {flaky.test_id}[/bold]")
        console.print(f"   Fail Rate: [red]{flaky.fail_rate:.1%}[/red] ({flaky.failed_runs + flaky.error_runs}/{flaky.total_runs} runs)")
        console.print(f"   Passed: [green]{flaky.passed_runs}[/green] | Failed: [red]{flaky.failed_runs}[/red] | Errors: [red]{flaky.error_runs}[/red]")

        if flaky.error_messages:
            console.print("   Recent Errors:")
            for msg in flaky.error_messages[:2]:  # Show first 2 error messages
                console.print(f"     • {msg[:100]}...")
        console.print()


def cmd_trends(args):
    """Show test health trends over time."""
    console = Console()
    analyzer = TestIntelligenceAnalyzer()

    console.print("\n[bold cyan]Test Health Trends[/bold cyan]\n")

    package_health = analyzer.analyze_package_health(days=args.days)

    if args.packages:
        # Filter to specific packages
        package_list = args.packages.split(",")
        package_health = [h for h in package_health if h.package_name in package_list]

    if not package_health:
        console.print("[yellow]No trend data available for specified packages.[/yellow]")
        return

    table = Table(title=f"Trends Over Last {args.days} Days")
    table.add_column("Package", style="cyan")
    table.add_column("Direction", justify="center")
    table.add_column("Change", justify="right")
    table.add_column("Current Pass Rate", justify="right")

    for health in package_health:
        if health.trend_direction == "improving":
            direction = "[green]↗ Improving[/green]"
        elif health.trend_direction == "degrading":
            direction = "[red]↘ Degrading[/red]"
        else:
            direction = "[dim]→ Stable[/dim]"

        change_color = "green" if health.trend_percentage > 0 else "red" if health.trend_percentage < 0 else "white"

        table.add_row(
            health.package_name,
            direction,
            f"[{change_color}]{health.trend_percentage:+.1f}%[/{change_color}]",
            f"{health.pass_rate:.1f}%",
        )

    console.print(table)


def cmd_slow(args):
    """Identify slow tests."""
    console = Console()
    analyzer = TestIntelligenceAnalyzer()

    console.print("\n[bold cyan]Slow Test Detection[/bold cyan]\n")

    slow_tests = analyzer.detect_slow_tests(top_n=args.top)

    if not slow_tests:
        console.print("[yellow]No test data available.[/yellow]")
        return

    console.print(f"[bold]Top {args.top} Slowest Tests:[/bold]\n")

    table = Table()
    table.add_column("#", justify="right", style="dim")
    table.add_column("Test", style="cyan")
    table.add_column("Avg Duration", justify="right")

    for i, (test_id, duration_ms) in enumerate(slow_tests, 1):
        # Color code based on duration
        if duration_ms > 5000:
            duration_color = "red"
        elif duration_ms > 1000:
            duration_color = "yellow"
        else:
            duration_color = "green"

        table.add_row(str(i), test_id, f"[{duration_color}]{duration_ms:.0f}ms[/{duration_color}]")

    console.print(table)


def cmd_patterns(args):
    """Analyze failure patterns."""
    console = Console()
    analyzer = TestIntelligenceAnalyzer()

    console.print("\n[bold cyan]Failure Pattern Analysis[/bold cyan]\n")

    patterns = analyzer.cluster_failure_patterns()

    if not patterns:
        console.print("[green]No failure patterns detected![/green]")
        return

    console.print(f"[bold]Found {len(patterns)} failure patterns:[/bold]\n")

    for i, pattern in enumerate(patterns[:args.limit], 1):
        console.print(f"[bold]{i}. Pattern: {pattern.error_signature}[/bold]")
        console.print(f"   Affected Tests: [red]{len(pattern.affected_tests)}[/red]")
        console.print(f"   Packages: {', '.join(pattern.packages_affected)}")

        if pattern.suggested_root_cause:
            console.print(f"   [yellow]Suggested Cause: {pattern.suggested_root_cause}[/yellow]")

        console.print("   Tests:")
        for test in pattern.affected_tests[:5]:  # Show first 5
            console.print(f"     • {test}")
        if len(pattern.affected_tests) > 5:
            console.print(f"     ... and {len(pattern.affected_tests) - 5} more")
        console.print()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Hive Test Intelligence CLI", prog="hive-test-intel")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Status command
    status_parser = subparsers.add_parser("status", help="Show platform test health status")
    status_parser.add_argument("--days", type=int, default=7, help="Number of days to analyze (default: 7)")
    status_parser.set_defaults(func=cmd_status)

    # Flaky test detection
    flaky_parser = subparsers.add_parser("flaky", help="Detect flaky tests")
    flaky_parser.add_argument("--threshold", type=float, default=0.2, help="Minimum fail rate (default: 0.2)")
    flaky_parser.add_argument("--limit", type=int, default=20, help="Maximum number of results (default: 20)")
    flaky_parser.set_defaults(func=cmd_flaky)

    # Trend analysis
    trends_parser = subparsers.add_parser("trends", help="Show test health trends")
    trends_parser.add_argument("--days", type=int, default=7, help="Number of days to analyze (default: 7)")
    trends_parser.add_argument("--packages", type=str, help="Comma-separated list of packages to analyze")
    trends_parser.set_defaults(func=cmd_trends)

    # Slow test detection
    slow_parser = subparsers.add_parser("slow", help="Identify slow tests")
    slow_parser.add_argument("--top", type=int, default=20, help="Number of slow tests to show (default: 20)")
    slow_parser.set_defaults(func=cmd_slow)

    # Failure pattern analysis
    patterns_parser = subparsers.add_parser("patterns", help="Analyze failure patterns")
    patterns_parser.add_argument("--limit", type=int, default=10, help="Maximum number of patterns (default: 10)")
    patterns_parser.set_defaults(func=cmd_patterns)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
