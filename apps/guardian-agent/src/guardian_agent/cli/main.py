"""Main CLI entry point for Guardian Agent."""

import asyncio
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from guardian_agent.core.config import GuardianConfig
from guardian_agent.core.interfaces import Severity
from guardian_agent.genesis.genesis_agent import GenesisAgent, GenesisConfig
from guardian_agent.intelligence.oracle_service import OracleConfig, OracleService
from guardian_agent.review.engine import ReviewEngine

console = Console()


@click.group()
@click.option("--config", "-c", type=click.Path(exists=True), help="Path to configuration file")
@click.pass_context
def cli(ctx: click.Context, config: Optional[str]) -> None:
    """Hive Guardian Agent - AI-powered code review and platform intelligence Oracle."""
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


# Oracle Intelligence Commands


@cli.group()
@click.pass_context
def oracle(ctx: click.Context) -> None:
    """Hive Oracle - Platform Intelligence and Strategic Insights."""
    pass


@oracle.command()
@click.option("--daemon", "-d", is_flag=True, help="Run as daemon service")
@click.option("--config", "-c", type=click.Path(), help="Oracle configuration file")
@click.pass_context
def start(ctx: click.Context, daemon: bool, config: Optional[str]) -> None:
    """Start the Hive Oracle Intelligence Service."""

    # Load Oracle configuration
    oracle_config = OracleConfig()

    console.print("🔮 [bold blue]Initializing Hive Oracle Intelligence System[/bold blue]")
    console.print("Guardian Agent evolving into Oracle...")

    async def start_oracle():
        oracle_service = OracleService(oracle_config)

        try:
            await oracle_service.start_async()

            if daemon:
                console.print("🌟 [bold green]Oracle Service running as daemon[/bold green]")
                console.print(f"Dashboard: http://localhost:{oracle_config.dashboard_port}")
                console.print("Press Ctrl+C to stop...")

                # Keep running until interrupted
                try:
                    while True:
                        await asyncio.sleep(1)
                except KeyboardInterrupt:
                    console.print("\n🛑 Stopping Oracle Service...")
            else:
                console.print("🌟 [bold green]Oracle Service started successfully[/bold green]")

        finally:
            await oracle_service.stop_async()
            console.print("Oracle Service stopped")

        asyncio.run(start_oracle())


# Genesis Agent Commands - The Oracle's App Creation Engine


@cli.group()
@click.pass_context
def genesis(ctx: click.Context) -> None:
    """Hive Genesis Agent - Oracle-Powered App Creation Engine."""
    pass


@genesis.command("create")
@click.argument("name")
@click.option("--description", "-d", required=True, help="Description of the application to create")
@click.option("--path", "-p", type=click.Path(), help="Target path for the new application")
@click.option("--no-oracle", is_flag=True, help="Disable Oracle consultation")
@click.pass_context
def create_app(ctx: click.Context, name: str, description: str, path: Optional[str], no_oracle: bool) -> None:
    """Create a new Hive application with Oracle intelligence."""

    console.print("🔮 [bold blue]Hive Genesis Agent - Creating Application[/bold blue]")
    console.print(f"App Name: [bold]{name}[/bold]")
    console.print(f"Description: {description}")

    async def create_app_async():
        try:
            # Initialize Genesis Agent
            genesis_config = GenesisConfig(enable_oracle_consultation=not no_oracle)

            # Initialize Oracle if enabled
            oracle_service = None
            if not no_oracle:
                console.print("🔮 Initializing Oracle consultation...")
                oracle_config = OracleConfig()
                oracle_service = OracleService(oracle_config)

            genesis_agent = GenesisAgent(genesis_config, oracle_service)

            # Create application
            with Progress(
                SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console
            ) as progress:
                task = progress.add_task("Creating application...", total=None)

                target_path = Path(path) if path else None
                app_spec = await genesis_agent.create_app_async(name, description, target_path)

                progress.update(task, description="Application created successfully!")

            # Display results
            console.print("\n✅ [bold green]Application Created Successfully![/bold green]")
            console.print(f"📁 Location: {target_path or f'apps/{name}'}")
            console.print(f"🎯 Oracle Confidence: {app_spec.oracle_confidence:.1%}")
            console.print(f"📋 Features Identified: {len(app_spec.features)}")
            console.print(f"📦 Packages: {', '.join(app_spec.recommended_packages)}")

            # Show feature summary
            if app_spec.features:
                console.print("\n🚀 [bold]Feature Roadmap (Oracle-Prioritized):[/bold]")

                table = Table(show_header=True, header_style="bold magenta")
                table.add_column("Feature", style="cyan")
                table.add_column("Priority", style="yellow")
                table.add_column("Effort", style="green")
                table.add_column("Business Value", style="blue")

                for feature in app_spec.features[:5]:  # Top 5 features
                    priority_icon = {"critical": "🚨", "high": "⚠️", "medium": "📋", "low": "💡", "future": "🔮"}.get(
                        feature.priority.value, "📋"
                    )

                    business_value = (
                        feature.business_value[:40] + "..."
                        if len(feature.business_value) > 40
                        else feature.business_value
                    )

                    table.add_row(
                        feature.name,
                        f"{priority_icon} {feature.priority.value.title()}",
                        feature.estimated_effort,
                        business_value,
                    )

                console.print(table)

            # Show Oracle insights
            if app_spec.market_opportunity:
                console.print(f"\n💡 [bold]Oracle Market Insight:[/bold] {app_spec.market_opportunity}")

            # Next steps
            console.print("\n🔧 [bold]Next Steps:[/bold]")
            console.print("1. Navigate to the application directory")
            console.print("2. Install dependencies: [bold]pip install -e .[/bold]")
            console.print("3. Review generated features and implement by priority")
            console.print("4. Run tests: [bold]pytest tests/[/bold]")

        except Exception as e:
            console.print(f"❌ [bold red]Failed to create application:[/bold red] {e}")
            raise click.ClickException(str(e))

    asyncio.run(create_app_async())


@genesis.command("analyze")
@click.argument("description")
@click.pass_context
def analyze_description(ctx: click.Context, description: str) -> None:
    """Analyze an app description without creating the application."""

    console.print("🔍 [bold blue]Analyzing Application Description[/bold blue]")
    console.print(f"Description: {description}")

    async def analyze_async():
        try:
            genesis_config = GenesisConfig()
            genesis_agent = GenesisAgent(genesis_config)

            # Analyze description
            analysis_result = await genesis_agent.analyzer.analyze_description_async(description)

            # Display analysis results
            console.print("\n📊 [bold green]Analysis Results:[/bold green]")
            console.print(f"🎯 Confidence Score: {analysis_result['confidence_score']:.1%}")
            console.print(f"🔧 Complexity: {analysis_result['complexity'].title()}")

            # Features
            if analysis_result["features"]:
                console.print("\n🚀 [bold]Identified Features:[/bold]")
                for feature in analysis_result["features"]:
                    console.print(f"  • {feature}")

            # Keywords
            if analysis_result["keywords"]:
                console.print("\n🏷️ [bold]Technical Keywords:[/bold]")
                console.print(f"  {', '.join(analysis_result['keywords'])}")

            # Suggested packages
            if analysis_result["suggested_packages"]:
                console.print("\n📦 [bold]Recommended Packages:[/bold]")
                for package in analysis_result["suggested_packages"]:
                    console.print(f"  • {package}")

            # User personas
            if analysis_result["user_personas"]:
                console.print("\n👥 [bold]User Personas:[/bold]")
                console.print(f"  {', '.join(analysis_result['user_personas'])}")

            # Data requirements
            data_req = analysis_result["data_requirements"]
            if data_req:
                console.print("\n💾 [bold]Data Requirements:[/bold]")
                console.print(f"  Storage: {data_req['storage_type']}")
                console.print(f"  Volume: {data_req['data_volume']}")
                if data_req["data_types"]:
                    console.print(f"  Types: {', '.join(data_req['data_types'])}")

        except Exception as e:
            console.print(f"❌ [bold red]Analysis failed:[/bold red] {e}")
            raise click.ClickException(str(e))

    asyncio.run(analyze_async())


@genesis.command("templates")
@click.pass_context
def list_templates(ctx: click.Context) -> None:
    """List available application templates and categories."""

    console.print("📋 [bold blue]Available Application Categories[/bold blue]")

    categories = [
        ("web_application", "Web Application", "FastAPI-based web applications with UI"),
        ("api_service", "API Service", "RESTful API services and microservices"),
        ("cli_tool", "CLI Tool", "Command-line tools and utilities"),
        ("ai_service", "AI Service", "AI-powered services using hive-ai"),
        ("data_processor", "Data Processor", "Data processing and ETL applications"),
        ("background_service", "Background Service", "Long-running background services"),
        ("microservice", "Microservice", "General-purpose microservices"),
    ]

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Category", style="cyan")
    table.add_column("Name", style="yellow")
    table.add_column("Description", style="green")

    for category, name, description in categories:
        table.add_row(category, name, description)

    console.print(table)

    console.print("\n💡 [bold]Usage Examples:[/bold]")
    console.print(
        "• [bold]Web App:[/bold] hive genesis create photo-gallery -d 'A web app for storing and tagging photos'"
    )
    console.print("• [bold]API Service:[/bold] hive genesis create user-api -d 'REST API for user management'")
    console.print(
        "• [bold]AI Service:[/bold] hive genesis create text-analyzer -d 'AI service for text analysis and summarization'"
    )
    console.print(
        "• [bold]CLI Tool:[/bold] hive genesis create data-migrator -d 'Command-line tool for database migrations'"
    )


@oracle.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Get Oracle Service status and platform health."""

    async def get_status():
        oracle_service = OracleService()

        try:
            # Get service status
            service_status = oracle_service.get_service_status()

            console.print("🔮 [bold blue]Hive Oracle Status[/bold blue]")
            console.print(f"Running: {'✅' if service_status['running'] else '❌'}")
            console.print(f"Active Tasks: {service_status['active_tasks']}")

            if service_status["last_analysis"]:
                console.print(f"Last Analysis: {service_status['last_analysis']}")

            # Get platform health if Oracle is running
            if service_status["running"]:
                health = await oracle_service.get_platform_health_async()

                console.print("\n🏥 [bold green]Platform Health[/bold green]")
                console.print(f"Overall Score: {health['overall_score']:.1f}/100")
                console.print(f"Status: {health['status'].upper()}")
                console.print(f"Active Alerts: {health['active_alerts']}")

        except Exception as e:
            console.print(f"❌ [red]Error getting Oracle status: {e}[/red]")

    asyncio.run(get_status())


@oracle.command()
@click.option("--hours", "-h", default=24, help="Analysis time window in hours")
@click.option("--format", "-f", type=click.Choice(["text", "json"]), default="text", help="Output format")
@click.pass_context
def insights(ctx: click.Context, hours: int, format: str) -> None:
    """Get strategic insights and recommendations."""

    async def get_insights():
        oracle_service = OracleService()

        try:
            console.print(f"🔍 [bold blue]Generating Strategic Insights ({hours}h window)[/bold blue]")

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Analyzing platform data...", total=None)

                insights = await oracle_service.get_strategic_insights_async(hours=hours)
                recommendations = await oracle_service.get_recommendations_async()

                progress.remove_task(task)

            if format == "json":
                data = {"insights": insights, "recommendations": recommendations}
                console.print_json(data=data)
            else:
                # Display insights
                console.print(f"\n🎯 [bold green]Strategic Insights ({len(insights)} found)[/bold green]")

                if not insights:
                    console.print("No critical insights at this time. Platform is operating normally.")
                else:
                    for insight in insights[:10]:  # Top 10
                        severity_color = {
                            "critical": "red",
                            "high": "orange1",
                            "medium": "yellow",
                            "low": "blue",
                            "info": "green",
                        }.get(insight["severity"], "white")

                        console.print(f"\n[{severity_color}]● {insight['title']}[/{severity_color}]")
                        console.print(f"  {insight['description']}")
                        console.print(
                            f"  [dim]Confidence: {insight['confidence']:.0%} | Category: {insight['category']}[/dim]"
                        )

                # Display recommendations
                high_priority = recommendations.get("critical_recommendations", []) + recommendations.get(
                    "high_priority_recommendations", []
                )

                if high_priority:
                    console.print(f"\n⚡ [bold red]High Priority Recommendations ({len(high_priority)})[/bold red]")

                    for rec in high_priority[:5]:  # Top 5
                        console.print(f"\n🔥 [bold]{rec['title']}[/bold]")
                        console.print(f"   {rec['description']}")
                        console.print(
                            f"   [dim]Priority: {rec['priority'].upper()} | Impact: {rec['expected_impact'].upper()}[/dim]"
                        )

                        if rec.get("implementation_steps"):
                            console.print("   [bold]Next Steps:[/bold]")
                            for step in rec["implementation_steps"][:3]:
                                console.print(f"   • {step}")

        except Exception as e:
            console.print(f"❌ [red]Error getting insights: {e}[/red]")

    asyncio.run(get_insights())


@oracle.command()
@click.pass_context
def dashboard(ctx: click.Context) -> None:
    """Launch the Mission Control Dashboard."""

    async def show_dashboard():
        oracle_service = OracleService()

        try:
            console.print("🎮 [bold blue]Generating Mission Control Dashboard[/bold blue]")

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Loading dashboard data...", total=None)

                # Get dashboard data
                dashboard_data = await oracle_service.get_dashboard_html_async()

                progress.remove_task(task)

            # Save dashboard to file
            dashboard_file = Path("hive_mission_control.html")
            with open(dashboard_file, "w") as f:
                f.write(dashboard_data)

            console.print(f"📊 [bold green]Mission Control Dashboard saved to: {dashboard_file}[/bold green]")
            console.print("Open the file in your browser to view the dashboard")

        except Exception as e:
            console.print(f"❌ [red]Error generating dashboard: {e}[/red]")

    asyncio.run(show_dashboard())


@oracle.command()
@click.pass_context
def analyze(ctx: click.Context) -> None:
    """Force immediate platform analysis."""

    async def force_analysis():
        oracle_service = OracleService()

        try:
            console.print("🔬 [bold blue]Performing Immediate Platform Analysis[/bold blue]")

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Analyzing platform metrics...", total=None)

                results = await oracle_service.force_analysis_async()

                progress.remove_task(task)

            console.print("✅ [bold green]Analysis Complete[/bold green]")
            console.print(f"Platform Health Score: {results['platform_health']['overall_score']:.1f}/100")
            console.print(f"Status: {results['platform_health']['status'].upper()}")
            console.print(f"Insights Generated: {results['insights_count']}")
            console.print(f"Critical Issues: {len(results['critical_insights'])}")

            if results["critical_insights"]:
                console.print("\n🚨 [bold red]Critical Issues Found:[/bold red]")
                for issue in results["critical_insights"][:3]:
                    console.print(f"• {issue['title']}")

        except Exception as e:
            console.print(f"❌ [red]Error performing analysis: {e}[/red]")

    asyncio.run(force_analysis())


@oracle.command()
@click.pass_context
def costs(ctx: click.Context) -> None:
    """Get cost intelligence and optimization recommendations."""

    async def get_costs():
        oracle_service = OracleService()

        try:
            console.print("💰 [bold blue]Cost Intelligence Analysis[/bold blue]")

            cost_data = await oracle_service.get_cost_intelligence_async()

            console.print("\n📊 [bold green]Current Costs[/bold green]")
            console.print(f"Today: ${cost_data['daily_cost']:.2f}")
            console.print(f"This Month: ${cost_data['monthly_cost']:.2f}")
            console.print(f"Projected Monthly: ${cost_data['projected_monthly_cost']:.2f}")
            console.print(f"Budget Utilization: {cost_data['budget_utilization']:.1f}%")

            if cost_data["potential_savings"] > 0:
                console.print("\n💡 [bold yellow]Optimization Opportunity[/bold yellow]")
                console.print(f"Potential Savings: ${cost_data['potential_savings']:.2f}/month")

                if cost_data["optimization_recommendations"]:
                    console.print("\n🎯 [bold]Recommendations:[/bold]")
                    for rec in cost_data["optimization_recommendations"]:
                        console.print(f"• {rec}")

            console.print(f"\n[dim]Last Updated: {cost_data['last_updated']}[/dim]")

        except Exception as e:
            console.print(f"❌ [red]Error getting cost data: {e}[/red]")

    asyncio.run(get_costs())


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
    console.print(
        f"\n[dim]Violations: {sum(result.violations_count.values())} | Suggestions: {result.suggestions_count} | Auto-fixable: {result.auto_fixable_count}[/dim]"
    )


def _display_summary(results) -> None:
    """Display summary of multiple review results."""
    total_files = len(results)
    total_violations = sum(sum(r.violations_count.values()) for r in results)
    avg_score = sum(r.overall_score for r in results) / total_files if total_files > 0 else 0

    console.print("\n[bold]Review Summary[/bold]")
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
