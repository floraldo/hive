"""Command-line interface for E2E Tester Agent."""

from __future__ import annotations

from pathlib import Path

import click
from hive_logging import get_logger

from .test_executor import TestExecutor
from .test_generator import TestGenerator

logger = get_logger(__name__)


@click.group()
def main() -> None:
    """E2E Tester Agent - AI-powered browser test generation and execution."""
    pass


@main.command()
@click.option(
    "--feature",
    "-f",
    required=True,
    help="Feature description in natural language"
)
@click.option(
    "--url",
    "-u",
    required=True,
    help="Target URL to test"
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    required=True,
    help="Output path for generated test file"
)
@click.option(
    "--success-indicator",
    help="Element that indicates success (optional)"
)
@click.option(
    "--failure-indicator",
    help="Element that indicates failure (optional)"
)
def generate(
    feature: str,
    url: str,
    output: Path,
    success_indicator: str | None,
    failure_indicator: str | None,
) -> None:
    """Generate E2E test from feature description."""
    click.echo(f"Generating E2E test for: {feature}")

    # Prepare context
    additional_context = {}
    if success_indicator:
        additional_context["success_indicator"] = success_indicator
    if failure_indicator:
        additional_context["failure_indicator"] = failure_indicator

    # Generate test
    generator = TestGenerator()
    generated = generator.generate_test_file(
        feature=feature,
        url=url,
        output_path=output,
        additional_context=additional_context if additional_context else None,
    )

    click.echo(f"✅ Test generated: {output}")
    click.echo(f"   Test name: {generated.test_name}")
    click.echo(f"   Lines: {len(generated.test_code.splitlines())}")


@main.command()
@click.option(
    "--test",
    "-t",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Path to test file to execute"
)
@click.option(
    "--report",
    "-r",
    type=click.Path(path_type=Path),
    help="Output path for test report (JSON)"
)
@click.option(
    "--headless/--no-headless",
    default=True,
    help="Run browser in headless mode"
)
@click.option(
    "--screenshots/--no-screenshots",
    default=True,
    help="Capture screenshots on failure"
)
@click.option(
    "--timeout",
    default=120,
    help="Test timeout in seconds"
)
def execute(
    test: Path,
    report: Path | None,
    headless: bool,
    screenshots: bool,
    timeout: int,
) -> None:
    """Execute E2E test file."""
    click.echo(f"Executing test: {test}")

    # Execute test
    executor = TestExecutor()
    result = executor.execute_test(
        test_path=test,
        headless=headless,
        capture_screenshots=screenshots,
        timeout=timeout,
    )

    # Display results
    click.echo("\nTest Results:")
    click.echo(f"  Status: {result.status.value.upper()}")
    click.echo(f"  Duration: {result.duration:.2f}s")
    click.echo(f"  Tests Run: {result.tests_run}")
    click.echo(f"  Passed: {result.tests_passed}")
    click.echo(f"  Failed: {result.tests_failed}")

    if result.screenshots:
        click.echo(f"  Screenshots: {len(result.screenshots)}")

    # Generate report if requested
    if report:
        executor.generate_report(result, report, format="json")
        click.echo(f"\n📄 Report saved: {report}")

    # Exit with appropriate code
    if result.status.value == "passed":
        click.echo("\n✅ All tests passed")
    elif result.status.value == "failed":
        click.echo("\n❌ Some tests failed")
        raise click.Abort()
    else:
        click.echo("\n⚠️ Test execution error")
        raise click.Abort()


@main.command()
@click.option(
    "--feature",
    "-f",
    required=True,
    help="Feature description in natural language"
)
@click.option(
    "--url",
    "-u",
    required=True,
    help="Target URL to test"
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(path_type=Path),
    default=Path("tests/e2e"),
    help="Output directory for generated test"
)
@click.option(
    "--headless/--no-headless",
    default=True,
    help="Run browser in headless mode"
)
def run(
    feature: str,
    url: str,
    output_dir: Path,
    headless: bool,
) -> None:
    """Generate and execute E2E test in one command."""
    click.echo(f"🚀 E2E Test Workflow for: {feature}\n")

    # Step 1: Generate test
    click.echo("Step 1: Generating test...")
    generator = TestGenerator()

    # Create test filename from feature
    test_name = feature.lower().replace(" ", "_")[:50]
    test_path = output_dir / f"test_{test_name}.py"

    generator.generate_test_file(
        feature=feature,
        url=url,
        output_path=test_path,
    )

    click.echo(f"   [OK] Generated: {test_path}\n")

    # Step 2: Execute test
    click.echo("Step 2: Executing test...")
    executor = TestExecutor()
    result = executor.execute_test(
        test_path=test_path,
        headless=headless,
    )

    # Display results
    click.echo("\n📊 Test Results:")
    click.echo(f"   Status: {result.status.value.upper()}")
    click.echo(f"   Duration: {result.duration:.2f}s")
    click.echo(f"   Tests: {result.tests_passed}/{result.tests_run} passed")

    if result.status.value == "passed":
        click.echo("\n✅ E2E workflow completed successfully")
    else:
        click.echo("\n❌ E2E workflow failed")
        raise click.Abort()


if __name__ == "__main__":
    main()
