"""Main CLI entry point for Guardian Agent."""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from guardian_agent.core.config import GuardianConfig
from guardian_agent.core.interfaces import Severity
from guardian_agent.review.engine import ReviewEngine

console = Console()


@click.group()
@click.option("--config", "-c", type=click.Path(exists=True), help="Path to configuration file")
@click.pass_context
def cli(ctx: click.Context, config: Optional[str]) -> None:
    """Hive Guardian Agent - AI-powered code review automation."""
    ctx.ensure_object(dict)

    # Load configuration
    if config:
        ctx.obj["config"] = GuardianConfig.load_from_file(Path(config))
    else:
        ctx.obj["config"] = GuardianConfig()


@cli.command()
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Choice(["text", "markdown", "json"]), default="text", help="Output format")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.pass_context
def review(ctx: click.Context, file_path: str, output: str, verbose: bool) -> None:
    """Review a single file."""
    config = ctx.obj["config"]
    file_path = Path(file_path)

    console.print(f"[bold blue]Reviewing:[/bold blue] {file_path}")

    # Run review
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Analyzing code...", total=None)

        async def run_review():
            engine = ReviewEngine(config)
            try:
                result = await engine.review_file(file_path)
                return result
            finally:
                await engine.close()

        result = asyncio.run(run_review())
        progress.remove_task(task)

    # Display results
    if output == "markdown":
        markdown = Markdown(result.to_markdown())
        console.print(markdown)
    elif output == "json":
        import json

        data = {
            "file": str(result.file_path),
            "score": result.overall_score,
            "summary": result.summary,
            "violations": [
                {
                    "severity": v.severity.value,
                    "message": v.message,
                    "line": v.line_number,
                }
                for v in result.all_violations
            ],
            "suggestions": [
                {
                    "message": s.message,
                    "confidence": s.confidence,
                }
                for s in result.all_suggestions
            ],
        }
        console.print_json(data=data)
    else:
        _display_text_results(result, verbose)


@cli.command()
@click.argument("directory", type=click.Path(exists=True))
@click.option("--recursive", "-r", is_flag=True, help="Review subdirectories")
@click.option("--summary", "-s", is_flag=True, help="Show summary only")
@click.pass_context
def review_dir(ctx: click.Context, directory: str, recursive: bool, summary: bool) -> None:
    """Review all files in a directory."""
    config = ctx.obj["config"]
    directory = Path(directory)

    console.print(f"[bold blue]Reviewing directory:[/bold blue] {directory}")

    async def run_review():
        engine = ReviewEngine(config)
        try:
            results = await engine.review_directory(directory, recursive=recursive)
            return results
        finally:
            await engine.close()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Reviewing files...", total=None)
        results = asyncio.run(run_review())
        progress.remove_task(task)

    if summary:
        _display_summary(results)
    else:
        for result in results:
            _display_text_results(result, verbose=False)
            console.print("─" * 40)


@cli.command()
@click.argument("file_path", type=click.Path(exists=True))
@click.pass_context
def autofix(ctx: click.Context, file_path: str) -> None:
    """Preview automatic fixes for a file."""
    from guardian_agent.analyzers.golden_rules import GoldenRulesAnalyzer

    file_path = Path(file_path)
    console.print(f"[bold blue]Checking automatic fixes for:[/bold blue] {file_path}")

    async def get_preview():
        analyzer = GoldenRulesAnalyzer()
        preview = await analyzer.get_autofix_preview(file_path)
        return preview

    preview = asyncio.run(get_preview())

    if preview:
        console.print("\n[bold green]Available Automatic Fixes:[/bold green]")
        console.print(preview)
        console.print("\n[dim]Run 'python -m hive_tests.autofix --execute' to apply these fixes[/dim]")
    else:
        console.print("[yellow]No automatic fixes available for this file[/yellow]")


@cli.command()
@click.option("--host", default="localhost", help="Server host")
@click.option("--port", default=8080, help="Server port")
@click.pass_context
def serve(ctx: click.Context, host: str, port: int) -> None:
    """Start the Guardian Agent API server."""
    console.print(f"[bold green]Starting Guardian Agent server on {host}:{port}[/bold green]")
    console.print("[dim]API server not yet implemented - coming in Week 2![/dim]")


def _display_text_results(result, verbose: bool) -> None:
    """Display review results in text format."""
    # Header
    console.print(f"\n[bold]{result.file_path.name}[/bold]")
    console.print(f"Score: [bold]{result.overall_score:.0f}/100[/bold]")
    console.print(f"Confidence: {result.ai_confidence:.0%}")

    # Summary
    console.print(f"\n[bold]Summary:[/bold] {result.summary}")

    # Violations table
    if result.all_violations:
        table = Table(title="Violations", show_header=True)
        table.add_column("Severity", style="bold")
        table.add_column("Line", justify="right")
        table.add_column("Message")

        for violation in sorted(result.all_violations, key=lambda v: (v.severity.value, v.line_number)):
            severity_color = {
                Severity.CRITICAL: "red",
                Severity.ERROR: "red",
                Severity.WARNING: "yellow",
                Severity.INFO: "blue",
            }.get(violation.severity, "white")

            table.add_row(
                f"[{severity_color}]{violation.severity.value}[/{severity_color}]",
                str(violation.line_number),
                violation.message[:80] + "..." if len(violation.message) > 80 else violation.message,
            )

        console.print(table)

    # Suggestions
    if result.all_suggestions and verbose:
        console.print("\n[bold]Suggestions:[/bold]")
        for suggestion in result.all_suggestions:
            console.print(f"• {suggestion.message} [dim](confidence: {suggestion.confidence:.0%})[/dim]")

    # Stats
    console.print(f"\n[dim]Violations: {sum(result.violations_count.values())} | Suggestions: {result.suggestions_count} | Auto-fixable: {result.auto_fixable_count}[/dim]")


def _display_summary(results) -> None:
    """Display summary of multiple review results."""
    total_files = len(results)
    total_violations = sum(sum(r.violations_count.values()) for r in results)
    avg_score = sum(r.overall_score for r in results) / total_files if total_files > 0 else 0

    console.print(f"\n[bold]Review Summary[/bold]")
    console.print(f"Files reviewed: {total_files}")
    console.print(f"Average score: {avg_score:.0f}/100")
    console.print(f"Total violations: {total_violations}")

    # Files with issues
    files_with_issues = [r for r in results if r.has_blocking_issues]
    if files_with_issues:
        console.print(f"\n[bold red]Files with blocking issues ({len(files_with_issues)}):[/bold red]")
        for result in files_with_issues[:10]:
            console.print(f"  • {result.file_path.name} (score: {result.overall_score:.0f})")


if __name__ == "__main__":
    cli()