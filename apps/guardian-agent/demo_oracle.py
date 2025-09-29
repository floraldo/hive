#!/usr/bin/env python3
"""
Hive Oracle Intelligence System Demo

This script demonstrates the complete "Hive Intelligence Initiative" -
the evolution of Guardian Agent from reactive protector to proactive Oracle.

The Oracle provides:
- Real-time platform health monitoring
- Predictive analytics and insights
- Strategic recommendations
- Cost optimization guidance
- Performance improvement suggestions
- Automated GitHub issue creation
"""

import asyncio
from datetime import datetime
from pathlib import Path

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table

    console = Console()
except ImportError:
    # Fallback if rich is not available
    class MockConsole:
        def print(self, *args, **kwargs):
            print(*args)

        def print_json(self, data=None):
            import json

            print(json.dumps(data, indent=2, default=str))

    class MockPanel:
        @staticmethod
        def fit(text, **kwargs):
            return text

    class MockProgress:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def add_task(self, desc, total=None):
            print(f"⏳ {desc}")
            return 1

        def remove_task(self, task_id):
            pass

    class MockTable:
        def __init__(self, *args, **kwargs):
            self.rows = []

        def add_column(self, *args, **kwargs):
            pass

        def add_row(self, *args):
            self.rows.append(args)

        def __str__(self):
            return "\n".join(" | ".join(str(cell) for cell in row) for row in self.rows)

    console = MockConsole()
    Panel = MockPanel
    Progress = MockProgress
    SpinnerColumn = lambda: None
    TextColumn = lambda x: None
    Table = MockTable

from guardian_agent.intelligence.data_unification import MetricType, UnifiedMetric
from guardian_agent.intelligence.oracle_service import OracleConfig, OracleService


async def demo_oracle_intelligence():
    """Demonstrate the complete Oracle Intelligence system."""

    console.print(
        Panel.fit(
            "🔮 [bold blue]HIVE ORACLE INTELLIGENCE SYSTEM[/bold blue]\n",
            "Guardian Agent → Oracle Evolution\n\n",
            "[green]From Reactive Protection to Proactive Wisdom[/green]",
            border_style="blue",
        ),
    )

    # Initialize Oracle
    console.print("\n🚀 [bold]Initializing Oracle Intelligence System...[/bold]")

    oracle_config = OracleConfig(
        collection_interval=60,  # 1 minute for demo,
        analysis_interval=300,  # 5 minutes for demo,
        enable_predictive_analysis=True,
        enable_github_integration=False,  # Disable for demo
    )

    oracle = OracleService(oracle_config)

    try:
        # Demonstrate data ingestion
        await demo_data_ingestion(oracle)

        # Demonstrate analytics
        await demo_analytics_engine(oracle)

        # Demonstrate mission control dashboard
        await demo_mission_control(oracle)

        # Demonstrate strategic recommendations
        await demo_strategic_recommendations(oracle)

        # Demonstrate Oracle service
        await demo_oracle_service(oracle)

    except Exception as e:
        console.print(f"❌ [red]Demo error: {e}[/red]")

    console.print(
        Panel.fit(
            "🌟 [bold green]ORACLE INTELLIGENCE DEMO COMPLETE[/bold green]\n\n",
            "The Guardian Agent has successfully evolved into the Oracle,\n",
            "providing strategic intelligence and proactive insights\n",
            "for the entire Hive platform ecosystem.",
            border_style="green",
        ),
    )


async def demo_data_ingestion(oracle: OracleService):
    """Demonstrate the Data Unification Layer."""

    console.print("\n📊 [bold blue]Phase 1: Data Unification Layer[/bold blue]")
    console.print("Ingesting metrics from all platform sources...")

    # Simulate some sample metrics
    sample_metrics = [
        UnifiedMetric(
            metric_type=MetricType.PRODUCTION_HEALTH,
            source="production_shield",
            timestamp=datetime.utcnow(),
            value={"status": "healthy", "uptime": 99.5, "response_time": 150},
            unit="status",
            tags={"service": "api-gateway", "environment": "production"},
        ),
        UnifiedMetric(
            metric_type=MetricType.AI_COST,
            source="hive_ai",
            timestamp=datetime.utcnow(),
            value={"cost_usd": 45.32, "tokens": 125000, "model": "gpt-4"},
            unit="usd",
            tags={"model": "gpt-4", "operation": "code_review"},
        ),
        UnifiedMetric(
            metric_type=MetricType.SYSTEM_PERFORMANCE,
            source="system_monitor",
            timestamp=datetime.utcnow(),
            value={"cpu_percent": 65.2, "memory_percent": 78.1, "disk_percent": 45.0},
            unit="percent",
            tags={"hostname": "hive-worker-1"},
        ),
        UnifiedMetric(
            metric_type=MetricType.CODE_QUALITY,
            source="guardian_agent",
            timestamp=datetime.utcnow(),
            value={"violations": 23, "score": 87.5, "golden_rules_compliance": 92.1},
            unit="score",
            tags={"repository": "hive", "branch": "main"},
        ),
    ]

    # Store sample metrics
    await oracle.warehouse.store_metrics_async(sample_metrics)

    # Display data sources
    table = Table(title="Data Sources Registered", show_header=True)
    table.add_column("Source", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Interval", justify="right")
    table.add_column("Status", style="green")

    for source_name, source in oracle.data_layer.data_sources.items():
        table.add_row(
            source_name,
            source.source_type,
            f"{source.collection_interval}s",
            "✅ Active" if source.enabled else "❌ Disabled",
        )

    console.print(table)
    console.print(f"✅ Stored {len(sample_metrics)} sample metrics in unified warehouse")


async def demo_analytics_engine(oracle: OracleService):
    """Demonstrate the Analytics & Insight Engine."""

    console.print("\n🔍 [bold blue]Phase 2: Analytics & Insight Engine[/bold blue]")
    console.print("Analyzing trends, detecting anomalies, and generating insights...")

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        task = progress.add_task("Running analytics...", total=None)

        # Generate insights
        insights = await oracle.get_strategic_insights_async(hours=24)

        progress.remove_task(task)

    console.print(f"🎯 Generated {len(insights)} strategic insights")

    if insights:
        console.print("\n📋 [bold]Sample Insights:[/bold]")
        for insight in insights[:3]:
            severity_color = {
                "critical": "red",
                "high": "orange1",
                "medium": "yellow",
                "low": "blue",
                "info": "green",
            }.get(insight.get("severity", "info"), "white")

            console.print(f"[{severity_color}]● {insight.get('title', 'Unknown')}[/{severity_color}]")
            console.print(f"  {insight.get('description', 'No description')}")
            console.print(
                f"  [dim]Confidence: {insight.get('confidence', 0):.0%} | Category: {insight.get('category', 'unknown')}[/dim]",
            )
    else:
        console.print("📊 Platform is operating normally - no critical insights detected")


async def demo_mission_control(oracle: OracleService):
    """Demonstrate the Mission Control Dashboard."""

    console.print("\n🎮 [bold blue]Phase 3: Mission Control Dashboard[/bold blue]")
    console.print("Generating single-pane-of-glass platform view...")

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        task = progress.add_task("Loading dashboard data...", total=None)

        # Get platform health
        health = await oracle.get_platform_health_async()
        cost_intel = await oracle.get_cost_intelligence_async()

        progress.remove_task(task)

    # Display platform health
    console.print("\n🏥 [bold green]Platform Health Overview[/bold green]")

    health_table = Table(show_header=True)
    health_table.add_column("Component", style="cyan")
    health_table.add_column("Score", justify="right")
    health_table.add_column("Status", style="green")

    # Simulate some component health data
    components = [
        ("Production Services", "95.2", "Excellent"),
        ("AI Services", "88.7", "Good"),
        ("Database", "99.1", "Excellent"),
        ("CI/CD Pipeline", "82.3", "Good"),
    ]

    for name, score, status in components:
        status_color = {"Excellent": "green", "Good": "blue", "Warning": "yellow", "Critical": "red"}.get(
            status, "white",
        )

        health_table.add_row(name, f"{score}%", f"[{status_color}]{status}[/{status_color}]")

    console.print(health_table)

    # Display cost intelligence
    console.print("\n💰 [bold yellow]Cost Intelligence[/bold yellow]")
    console.print(f"Daily Cost: ${cost_intel.get('daily_cost', 0):.2f}")
    console.print(f"Monthly Cost: ${cost_intel.get('monthly_cost', 0):.2f}")
    console.print(f"Budget Utilization: {cost_intel.get('budget_utilization', 0):.1f}%")

    # Generate HTML dashboard
    dashboard_html = await oracle.get_dashboard_html_async()
    dashboard_file = Path("hive_mission_control_demo.html")

    with open(dashboard_file, "w") as f:
        f.write(dashboard_html)

    console.print(f"📊 Full dashboard saved to: [cyan]{dashboard_file}[/cyan]")


async def demo_strategic_recommendations(oracle: OracleService):
    """Demonstrate the Strategic Recommendation Engine."""

    console.print("\n🎯 [bold blue]Phase 4: Strategic Recommendation Engine (Oracle)[/bold blue]")
    console.print("Generating strategic recommendations and GitHub issues...")

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        task = progress.add_task("Analyzing platform for recommendations...", total=None)

        recommendations = await oracle.get_recommendations_async(include_predictive=True)

        progress.remove_task(task)

    # Display recommendations summary
    critical = recommendations.get("critical_recommendations", [])
    high = recommendations.get("high_priority_recommendations", [])
    medium = recommendations.get("medium_priority_recommendations", [])

    console.print(f"🔥 Critical Recommendations: {len(critical)}")
    console.print(f"⚡ High Priority: {len(high)}")
    console.print(f"📋 Medium Priority: {len(medium)}")
    console.print(f"💰 Total Potential Savings: ${recommendations.get('total_potential_savings', 0):.2f}/month")

    # Show sample recommendations
    all_high_priority = critical + high
    if all_high_priority:
        console.print("\n🚨 [bold red]Top Strategic Recommendations:[/bold red]")

        for i, rec in enumerate(all_high_priority[:3], 1):
            console.print(f"\n{i}. [bold]{rec.get('title', 'Unknown')}[/bold]")
            console.print(f"   {rec.get('description', 'No description')}")
            console.print(
                f"   [dim]Priority: {rec.get('priority', 'unknown').upper()} | Impact: {rec.get('expected_impact', 'unknown').upper()}[/dim]",
            )

            steps = rec.get("implementation_steps", [])
            if steps:
                console.print("   [bold]Implementation Steps:[/bold]")
                for step in steps[:2]:  # Show first 2 steps
                    console.print(f"   • {step}")
    else:
        console.print("✅ No critical recommendations - platform is optimally configured")


async def demo_oracle_service(oracle: OracleService):
    """Demonstrate the complete Oracle Service."""

    console.print("\n🔮 [bold blue]Phase 5: Complete Oracle Service[/bold blue]")
    console.print("Demonstrating full Oracle intelligence capabilities...")

    # Get service status
    status = oracle.get_service_status()

    console.print(f"Oracle Service Status: {'🟢 Running' if status['running'] else '🔴 Stopped'}")
    console.print(f"Active Intelligence Tasks: {status['active_tasks']}")
    console.print(f"Predictive Analysis: {'✅ Enabled' if status['config']['predictive_analysis'] else '❌ Disabled'}")
    console.print(f"GitHub Integration: {'✅ Enabled' if status['config']['github_integration'] else '❌ Disabled'}")

    # Demonstrate forced analysis
    console.print("\n🔬 Performing immediate platform analysis...")

    analysis_results = await oracle.force_analysis_async()

    console.print("✅ [bold green]Oracle Analysis Complete[/bold green]")
    console.print(f"Platform Health Score: {analysis_results['platform_health']['overall_score']:.1f}/100")
    console.print(f"Status: {analysis_results['platform_health']['status'].upper()}")
    console.print(f"Insights Generated: {analysis_results['insights_count']}")
    console.print(f"Critical Issues: {len(analysis_results.get('critical_insights', []))}")

    # Show Oracle wisdom summary
    console.print("\n🌟 [bold cyan]Oracle Intelligence Summary[/bold cyan]")
    console.print("The Oracle has successfully analyzed the platform and provides:")
    console.print("• Real-time health monitoring and alerting")
    console.print("• Predictive failure detection and prevention")
    console.print("• Cost optimization recommendations")
    console.print("• Performance improvement strategies")
    console.print("• Strategic development guidance")
    console.print("• Automated issue creation and tracking")


if __name__ == "__main__":
    console.print("🔮 [bold blue]Starting Hive Oracle Intelligence Demo[/bold blue]")
    asyncio.run(demo_oracle_intelligence())
