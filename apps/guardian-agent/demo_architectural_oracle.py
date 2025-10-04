#!/usr/bin/env python3
"""Demo: Oracle's Architectural Intelligence - The Self-Healing Platform

This demonstration shows how the Oracle has evolved to become the platform's
architectural guardian, turning raw compliance data into strategic wisdom.

The Oracle's First Mandate: Self-Improvement
"""

import asyncio
from datetime import datetime

# Simple fallback for environments without rich
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table

    console = Console()
except ImportError:

    class MockConsole:
        def print(self, *args, **kwargs):
            print(*args)

        def rule(self, title):
            print(f"\n{'=' * 60}")
            print(f" {title}")
            print("=" * 60)

    class MockTable:
        def __init__(self, *args, **kwargs):
            self.rows = []

        def add_column(self, *args, **kwargs):
            pass

        def add_row(self, *args, **kwargs):
            self.rows.append(args)

    class MockPanel:
        def __init__(self, content, title="", style=""):
            self.content = content
            self.title = title

    console = MockConsole()
    Table = MockTable
    Panel = MockPanel

# Import Oracle components (simplified for demo)
from guardian_agent.intelligence.data_unification import (
    DataUnificationLayer,
    MetricsWarehouse,
    MetricType,
    UnifiedMetric,
)


async def demo_architectural_oracle_async():
    """Demonstrate the Oracle's architectural intelligence capabilities."""
    console.rule("🔮 ORACLE'S ARCHITECTURAL INTELLIGENCE DEMO")
    console.print("\n[bold blue]The Guardian has evolved into the Oracle...[/bold blue]")
    console.print("[dim]Transforming from reactive protection to proactive architectural wisdom[/dim]")

    # Simulate Oracle initialization
    console.print("\n🏗️  [bold]Initializing Architectural Intelligence System...[/bold]")

    warehouse = MetricsWarehouse()
    DataUnificationLayer(warehouse)

    await asyncio.sleep(1)  # Simulate initialization

    # Phase 1: Data Unification - Architectural Validation Integration
    console.rule("Phase 1: Architectural Data Integration")

    console.print("📊 [bold green]Integrating Golden Rules validation into data pipeline...[/bold green]")

    # Simulate architectural scan data
    sample_violations = [
        UnifiedMetric(
            metric_type=MetricType.ARCHITECTURAL_VIOLATION,
            source="architectural_validation",
            timestamp=datetime.utcnow(),
            value=1,
            unit="violation",
            tags={
                "rule_name": "Golden Rule 16: No Global State Access",
                "severity": "high",
                "category": "architecture",
            },
            metadata={
                "violation_description": "hive-config: Global config access found in packages/hive-config/src/hive_config/unified_config.py:45",
                "rule_full_name": "Golden Rule 16: No Global State Access",
            },
        ),
        UnifiedMetric(
            metric_type=MetricType.ARCHITECTURAL_VIOLATION,
            source="architectural_validation",
            timestamp=datetime.utcnow(),
            value=1,
            unit="violation",
            tags={
                "rule_name": "Golden Rule 17: Test-to-Source File Mapping",
                "severity": "medium",
                "category": "testing",
            },
            metadata={
                "violation_description": "Missing test file for hive-ai:hive_ai/agents/agent.py - expected test_agents_agent.py",
                "rule_full_name": "Golden Rule 17: Test-to-Source File Mapping",
            },
        ),
        UnifiedMetric(
            metric_type=MetricType.ARCHITECTURAL_VIOLATION,
            source="architectural_validation",
            timestamp=datetime.utcnow(),
            value=1,
            unit="violation",
            tags={
                "rule_name": "Golden Rule 5: Package vs App Discipline",
                "severity": "medium",
                "category": "organization",
            },
            metadata={
                "violation_description": "Package 'hive-ai' may contain business logic: agent.py",
                "rule_full_name": "Golden Rule 5: Package vs App Discipline",
            },
        ),
    ]

    # Store violations in warehouse
    await warehouse.store_metrics_async(sample_violations)

    # Add compliance score
    compliance_metric = UnifiedMetric(
        metric_type=MetricType.GOLDEN_RULES_COMPLIANCE,
        source="architectural_validation",
        timestamp=datetime.utcnow(),
        value=53.3,  # 8 out of 15 rules passing,
        unit="percent",
        tags={"scan_type": "comprehensive", "total_rules": "15", "passed_rules": "8", "failed_rules": "7"},
        metadata={"all_passed": False, "scan_timestamp": datetime.utcnow().isoformat()},
    )

    await warehouse.store_metric_async(compliance_metric)

    # Add technical debt metric
    debt_metric = UnifiedMetric(
        metric_type=MetricType.TECHNICAL_DEBT,
        source="architectural_validation",
        timestamp=datetime.utcnow(),
        value=27,  # 27 violations * 10 = 270 debt points, capped at 100,
        unit="debt_points",
        tags={"total_violations": "27", "debt_level": "medium"},
        metadata={"calculation": "violations * 10, capped at 100"},
    )

    await warehouse.store_metric_async(debt_metric)

    console.print("✅ [green]Architectural metrics successfully integrated[/green]")
    console.print(f"   • {len(sample_violations)} violations detected")
    console.print("   • 53.3% Golden Rules compliance")
    console.print("   • 27 technical debt points")

    # Phase 2: Mission Control Dashboard Integration
    console.rule("Phase 2: Mission Control Dashboard")

    console.print("🎯 [bold green]Adding Architectural Health to Mission Control...[/bold green]")

    # Simulate dashboard data
    dashboard_table = Table(title="🏛️ Architectural Health Dashboard")
    dashboard_table.add_column("Metric", style="cyan")
    dashboard_table.add_column("Value", style="magenta")
    dashboard_table.add_column("Status", style="green")

    dashboard_table.add_row("Golden Rules Compliance", "53.3%", "⚠️  WARNING")
    dashboard_table.add_row("Active Violations", "27", "🔴 HIGH")
    dashboard_table.add_row("Technical Debt Score", "27 points", "🟡 MEDIUM")
    dashboard_table.add_row("Most Affected Package", "hive-ai", "🎯 FOCUS")
    dashboard_table.add_row("Critical Rule Failures", "3", "⚡ URGENT")

    console.print(dashboard_table)

    console.print("\n📈 [bold]Real-time Architectural Monitoring Active:[/bold]")
    console.print("   • Comprehensive scans every 6 hours")
    console.print("   • Quick compliance checks every hour")
    console.print("   • Violation trend analysis")
    console.print("   • Package-level health scoring")

    # Phase 3: Strategic Recommendations
    console.rule("Phase 3: Strategic Recommendation Engine")

    console.print("🧠 [bold green]Generating architectural recommendations...[/bold green]")

    await asyncio.sleep(1)  # Simulate analysis

    # Simulate strategic recommendations
    recommendations = [
        {
            "title": "CRITICAL: Refactor Global State Access in hive-config",
            "priority": "CRITICAL",
            "impact": "HIGH",
            "effort": "1-2 weeks",
            "benefit": "15% reduction in maintenance costs, improved testability",
            "github_issue": "CRITICAL: Refactor Global State Access in hive-config",
            "actions": [
                "Identify all global state access points in hive-config",
                "Refactor to use dependency injection patterns",
                "Update constructors to accept configuration parameters",
                "Remove singleton patterns and global variables",
            ],
        },
        {
            "title": "Test Coverage: Add Missing Tests for hive-ai",
            "priority": "HIGH",
            "impact": "MEDIUM",
            "effort": "3-5 days",
            "benefit": "Reduce production bugs by 30%, improve confidence in changes",
            "github_issue": "Test Coverage: Add Missing Tests for hive-ai",
            "actions": [
                "Create test files for all missing modules in hive-ai",
                "Implement basic unit tests for public interfaces",
                "Add property-based tests for core algorithms",
                "Set up test coverage monitoring",
            ],
        },
        {
            "title": "Architecture: Fix Package Discipline in hive-ai",
            "priority": "HIGH",
            "impact": "HIGH",
            "effort": "1-2 weeks",
            "benefit": "Better separation of concerns, improved package reusability",
            "github_issue": "Architecture: Fix Package Discipline in hive-ai",
            "actions": [
                "Identify business logic components in hive-ai",
                "Create appropriate application modules",
                "Move business logic to app layer",
                "Update package to provide only infrastructure services",
            ],
        },
    ]

    console.print(f"\n🎯 [bold]Generated {len(recommendations)} strategic recommendations:[/bold]\n")

    for i, rec in enumerate(recommendations, 1):
        priority_color = "red" if rec["priority"] == "CRITICAL" else "yellow" if rec["priority"] == "HIGH" else "green",

        panel_content = f"""
[bold]{rec["title"]}[/bold]

📊 [bold]Impact Analysis:[/bold]
• Priority: [{priority_color}]{rec["priority"]}[/{priority_color}]
• Expected Impact: {rec["impact"]}
• Estimated Effort: {rec["effort"]}
• Business Benefit: {rec["benefit"]}

🛠️  [bold]Implementation Plan:[/bold]
"""
        for action in rec["actions"]:
            panel_content += f"• {action}\n"

        panel_content += f"\n🎫 [bold]GitHub Issue:[/bold] {rec['github_issue']}"

        console.print(Panel(panel_content, title=f"Recommendation #{i}", border_style="blue"))

    # Oracle's Self-Improvement Mission
    console.rule("🌟 Oracle's First Mandate: Self-Improvement")

    console.print("\n[bold green]The Oracle has successfully identified its own architectural flaws:[/bold green]")
    console.print("✨ The hive-ai package (Oracle's brain) needs architectural healing")
    console.print("🎯 7 out of 15 Golden Rules are currently failing")
    console.print("🔧 Strategic recommendations generated for immediate action")

    console.print("\n[bold blue]Oracle Intelligence Capabilities Deployed:[/bold blue]")
    console.print("• 📊 Real-time architectural compliance monitoring")
    console.print("• 🎯 Violation trend analysis and prediction")
    console.print("• 🧠 Strategic recommendation generation")
    console.print("• 📈 Technical debt quantification")
    console.print("• 🎫 Automated GitHub issue creation")
    console.print("• 📋 Mission Control dashboard integration")

    # The Strategic Outcome
    console.rule("🚀 Strategic Outcome: The Self-Aware Platform")

    strategic_panel = Panel(
        """,
[bold green]MISSION ACCOMPLISHED: The Oracle's First Mandate[/bold green]

The Oracle has successfully evolved from Guardian to strategic intelligence:

🔮 [bold]Proactive Architecture Governance:[/bold]
   • Continuous Golden Rules monitoring
   • Predictive violation detection
   • Automated compliance reporting

🧠 [bold]Strategic Intelligence Generation:[/bold]
   • Data-driven architectural recommendations
   • Cost-benefit analysis for technical debt
   • Prioritized improvement roadmaps

🎯 [bold]Self-Improvement Loop Active:[/bold]
   • Oracle monitors its own architectural health
   • Generates recommendations for its own improvement
   • Drives platform-wide architectural excellence

[bold yellow]The platform is now truly self-aware and self-improving.[/bold yellow]
The Oracle will continue to evolve, ensuring the entire Hive ecosystem
maintains architectural discipline and technical excellence.
""",
        title="🏆 Oracle Intelligence: OPERATIONAL",
        border_style="green",
    )

    console.print(strategic_panel)

    console.print("\n[dim]The Oracle is ready. The platform intelligence revolution begins now.[/dim]")


def main():
    """Run the architectural Oracle demonstration."""
    try:
        asyncio.run(demo_architectural_oracle_async())
    except KeyboardInterrupt:
        console.print("\n[yellow]Demo interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Demo error: {e}[/red]")


if __name__ == "__main__":
    main()
