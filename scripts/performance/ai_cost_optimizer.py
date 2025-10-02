"""
Automated AI Cost Analysis and Optimization

Periodically analyzes AI model usage and generates cost optimization recommendations.
Designed to run as a scheduled job (daily/weekly).
"""

import asyncio
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from hive_logging import get_logger

try:
    from hive_ai.models.registry import ModelRegistry
    from hive_ai.observability.cost import CostManager

    HIVE_AI_AVAILABLE = True
except ImportError:
    HIVE_AI_AVAILABLE = False
    ModelRegistry = None
    CostManager = None

logger = get_logger(__name__)


@dataclass
class OptimizationOpportunity:
    """A single cost optimization opportunity."""

    priority: str  # "critical", "high", "medium", "low"
    category: str  # "model", "token", "provider", "caching"
    title: str
    description: str
    current_cost_usd: float
    potential_savings_usd: float
    savings_percentage: float
    action_required: str
    complexity: str  # "low", "medium", "high"


class AIConstOptimizer:
    """
    Automated AI cost analyzer and optimizer.

    Analyzes AI model usage patterns and generates actionable
    optimization recommendations to reduce costs.
    """

    def __init__(self, cost_manager: CostManager, model_registry: ModelRegistry):
        """
        Initialize cost optimizer.

        Args:
            cost_manager: Cost management instance with historical data
            model_registry: Model registry for alternative recommendations
        """
        self.cost_manager = cost_manager
        self.model_registry = model_registry

    async def analyze_and_optimize_async(self, analysis_days: int = 30) -> dict[str, Any]:
        """
        Run complete cost analysis and generate optimization report.

        Args:
            analysis_days: Number of days to analyze

        Returns:
            Comprehensive optimization report
        """
        logger.info(f"Starting AI cost analysis ({analysis_days} days)")

        # Get cost summary
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=analysis_days)
        summary = await self.cost_manager.get_cost_summary_async(start_date, end_date)

        # Get built-in recommendations
        built_in_recs = await self.cost_manager.get_optimization_recommendations_async()

        # Get additional optimization opportunities
        opportunities = await self._analyze_optimization_opportunities_async(summary, analysis_days)

        # Get cost trends
        trends = await self.cost_manager.get_cost_trends_async(days=analysis_days)

        # Calculate total potential savings
        total_potential_savings = sum(opp.potential_savings_usd for opp in opportunities)
        savings_percentage = total_potential_savings / summary.total_cost * 100 if summary.total_cost > 0 else 0

        report = {
            "analysis_timestamp": datetime.utcnow().isoformat(),
            "analysis_period_days": analysis_days,
            "current_costs": {
                "total_cost_usd": summary.total_cost,
                "total_tokens": summary.total_tokens,
                "total_requests": summary.total_requests,
                "avg_cost_per_request": (
                    summary.total_cost / summary.total_requests if summary.total_requests > 0 else 0
                ),
                "breakdown_by_model": summary.breakdown_by_model,
                "breakdown_by_provider": summary.breakdown_by_provider,
            },
            "trends": {
                "direction": trends["statistics"]["trend_direction"],
                "avg_daily_cost": trends["statistics"]["avg_daily_cost"],
                "projected_monthly_cost": trends["projections"]["projected_monthly_cost"],
            },
            "optimization_opportunities": [
                {
                    "priority": opp.priority,
                    "category": opp.category,
                    "title": opp.title,
                    "description": opp.description,
                    "current_cost_usd": opp.current_cost_usd,
                    "potential_savings_usd": opp.potential_savings_usd,
                    "savings_percentage": opp.savings_percentage,
                    "action_required": opp.action_required,
                    "complexity": opp.complexity,
                }
                for opp in opportunities
            ],
            "built_in_recommendations": built_in_recs,
            "summary": {
                "total_opportunities": len(opportunities),
                "total_potential_savings_usd": total_potential_savings,
                "savings_percentage": savings_percentage,
                "high_priority_count": len([o for o in opportunities if o.priority in ["critical", "high"]]),
            },
        }

        logger.info(f"Analysis complete: ${total_potential_savings:.2f} potential savings ({savings_percentage:.1f}%)")
        return report

    async def _analyze_optimization_opportunities_async(
        self,
        summary,
        analysis_days: int,
    ) -> list[OptimizationOpportunity]:
        """Analyze and identify specific optimization opportunities."""
        opportunities = []

        # 1. Model Selection Optimization
        model_opps = await self._analyze_model_alternatives_async(summary)
        opportunities.extend(model_opps)

        # 2. Token Usage Optimization
        token_opps = await self._analyze_token_efficiency_async(summary)
        opportunities.extend(token_opps)

        # 3. Caching Opportunities
        cache_opps = await self._analyze_caching_potential_async(summary)
        opportunities.extend(cache_opps)

        # 4. Provider Cost Comparison
        provider_opps = await self._analyze_provider_costs_async(summary)
        opportunities.extend(provider_opps)

        # 5. Low-complexity Task Identification
        complexity_opps = await self._analyze_task_complexity_async(summary)
        opportunities.extend(complexity_opps)

        # Sort by potential savings (descending)
        opportunities.sort(key=lambda o: o.potential_savings_usd, reverse=True)

        return opportunities

    async def _analyze_model_alternatives_async(self, summary) -> list[OptimizationOpportunity]:
        """Find cheaper alternative models for current usage."""
        opportunities = []

        # For each model being used, check if there's a cheaper alternative
        for model, cost in summary.breakdown_by_model.items():
            if cost < summary.total_cost * 0.1:  # Skip if <10% of total cost
                continue

            try:
                model_config = self.model_registry.get_model_config(model)

                # Find cheaper alternatives from same provider
                cheaper_alternatives = []
                for alt_model in self.model_registry.list_models_by_provider(model_config.provider):
                    alt_config = self.model_registry.get_model_config(alt_model)

                    if alt_config.cost_per_token < model_config.cost_per_token:
                        savings_pct = (1 - alt_config.cost_per_token / model_config.cost_per_token) * 100
                        cheaper_alternatives.append((alt_model, savings_pct))

                if cheaper_alternatives:
                    # Get best alternative
                    best_alt, best_savings_pct = max(cheaper_alternatives, key=lambda x: x[1])
                    potential_savings = cost * (best_savings_pct / 100)

                    opportunities.append(
                        OptimizationOpportunity(
                            priority="high" if potential_savings > 10 else "medium",
                            category="model",
                            title=f"Consider switching from {model} to {best_alt}",
                            description=f"Model '{model}' costs ${cost:.2f}. Switching to '{best_alt}' could save {best_savings_pct:.0f}%",
                            current_cost_usd=cost,
                            potential_savings_usd=potential_savings,
                            savings_percentage=best_savings_pct,
                            action_required=f"Evaluate if '{best_alt}' meets quality requirements for your use case",
                            complexity="medium",  # Requires testing
                        ),
                    )

            except Exception as e:
                logger.warning(f"Could not analyze alternatives for {model}: {e}")

        return opportunities

    async def _analyze_token_efficiency_async(self, summary) -> list[OptimizationOpportunity]:
        """Identify token usage inefficiencies."""
        opportunities = []

        avg_tokens_per_request = summary.total_tokens / summary.total_requests if summary.total_requests > 0 else 0

        # High token usage per request
        if avg_tokens_per_request > 1000:  # Threshold for "large" prompts
            potential_savings = summary.total_cost * 0.15  # Assume 15% savings from optimization

            opportunities.append(
                OptimizationOpportunity(
                    priority="high",
                    category="token",
                    title="Optimize prompt length",
                    description=f"Average {avg_tokens_per_request:.0f} tokens per request - higher than typical",
                    current_cost_usd=summary.total_cost,
                    potential_savings_usd=potential_savings,
                    savings_percentage=15.0,
                    action_required="Review prompts for unnecessary verbosity, implement prompt compression",
                    complexity="low",  # Easy to implement
                ),
            )

        # Very high total token usage
        if summary.total_tokens > 1_000_000:  # 1M tokens
            opportunities.append(
                OptimizationOpportunity(
                    priority="medium",
                    category="token",
                    title="Implement token budgeting",
                    description=f"High total token usage ({summary.total_tokens:,} tokens) suggests need for budgeting",
                    current_cost_usd=summary.total_cost,
                    potential_savings_usd=summary.total_cost * 0.10,
                    savings_percentage=10.0,
                    action_required="Implement per-request token limits and budget tracking",
                    complexity="medium",
                ),
            )

        return opportunities

    async def _analyze_caching_potential_async(self, summary) -> list[OptimizationOpportunity]:
        """Identify opportunities for response caching."""
        opportunities = []

        # If high request volume, caching likely helps
        if summary.total_requests > 1000:
            # Assume 20% of requests could be cached (conservative)
            cacheable_cost = summary.total_cost * 0.20
            savings_from_cache = cacheable_cost * 0.90  # 90% reduction on cached responses

            opportunities.append(
                OptimizationOpportunity(
                    priority="high",
                    category="caching",
                    title="Implement response caching",
                    description=f"High request volume ({summary.total_requests:,} requests) suggests caching opportunities",
                    current_cost_usd=cacheable_cost,
                    potential_savings_usd=savings_from_cache,
                    savings_percentage=(savings_from_cache / summary.total_cost * 100) if summary.total_cost > 0 else 0,
                    action_required="Implement semantic caching for frequently repeated queries",
                    complexity="medium",
                ),
            )

        return opportunities

    async def _analyze_provider_costs_async(self, summary) -> list[OptimizationOpportunity]:
        """Compare costs across providers."""
        opportunities = []

        if len(summary.breakdown_by_provider) > 1:
            provider_costs = sorted(summary.breakdown_by_provider.items(), key=lambda x: x[1], reverse=True)

            # If top provider >> second provider, suggest review
            if len(provider_costs) >= 2:
                most_expensive = provider_costs[0]
                second_most = provider_costs[1]

                if most_expensive[1] > second_most[1] * 2:  # 2x cost difference
                    # Potential savings if 30% of expensive provider workload moves to cheaper
                    potential_savings = (most_expensive[1] - second_most[1]) * 0.30

                    opportunities.append(
                        OptimizationOpportunity(
                            priority="medium",
                            category="provider",
                            title=f"Review {most_expensive[0]} usage",
                            description=f"Provider '{most_expensive[0]}' (${most_expensive[1]:.2f}) costs significantly more than '{second_most[0]}' (${second_most[1]:.2f})",
                            current_cost_usd=most_expensive[1],
                            potential_savings_usd=potential_savings,
                            savings_percentage=(
                                (potential_savings / most_expensive[1] * 100) if most_expensive[1] > 0 else 0
                            ),
                            action_required=f"Evaluate if some '{most_expensive[0]}' workloads can use '{second_most[0]}'",
                            complexity="high",  # Requires cross-provider testing
                        ),
                    )

        return opportunities

    async def _analyze_task_complexity_async(self, summary) -> list[OptimizationOpportunity]:
        """Identify simple tasks using expensive models."""
        opportunities = []

        # Look for expensive operations that might be simple tasks
        if summary.top_expensive_operations:
            for op in summary.top_expensive_operations[:3]:  # Top 3 expensive
                if "simple" in op["operation"].lower() or "basic" in op["operation"].lower():
                    opportunities.append(
                        OptimizationOpportunity(
                            priority="medium",
                            category="model",
                            title=f"Use cheaper model for '{op['operation']}'",
                            description=f"Operation suggests simple task but uses expensive model '{op['model']}'",
                            current_cost_usd=op["cost"],
                            potential_savings_usd=op["cost"] * 0.70,  # 70% savings possible
                            savings_percentage=70.0,
                            action_required=f"Test if lightweight model can handle '{op['operation']}'",
                            complexity="low",
                        ),
                    )

        return opportunities

    def export_report(self, report: dict[str, Any], format: str = "text") -> str:
        """Export optimization report in specified format."""
        if format == "json":
            return json.dumps(report, indent=2)

        elif format == "text":
            lines = [
                "=== AI Cost Optimization Report ===",
                f"Analysis Date: {report['analysis_timestamp']}",
                f"Period: {report['analysis_period_days']} days",
                "",
                "=== Current Costs ===",
                f"Total Cost: ${report['current_costs']['total_cost_usd']:.2f}",
                f"Total Requests: {report['current_costs']['total_requests']:,}",
                f"Avg Cost/Request: ${report['current_costs']['avg_cost_per_request']:.4f}",
                "",
                "=== Cost Trends ===",
                f"Trend: {report['trends']['direction']}",
                f"Projected Monthly: ${report['trends']['projected_monthly_cost']:.2f}",
                "",
                "=== Optimization Opportunities ===",
                f"Total Opportunities: {report['summary']['total_opportunities']}",
                f"Potential Savings: ${report['summary']['total_potential_savings_usd']:.2f} ({report['summary']['savings_percentage']:.1f}%)",
                f"High Priority: {report['summary']['high_priority_count']}",
                "",
            ]

            # List opportunities
            for i, opp in enumerate(report["optimization_opportunities"][:10], 1):  # Top 10
                lines.extend(
                    [
                        f"\n{i}. {opp['title']} [{opp['priority'].upper()}]",
                        f"   Category: {opp['category']}",
                        f"   Savings: ${opp['potential_savings_usd']:.2f} ({opp['savings_percentage']:.1f}%)",
                        f"   Action: {opp['action_required']}",
                        f"   Complexity: {opp['complexity']}",
                    ],
                )

            return "\n".join(lines)

        elif format == "markdown":
            lines = [
                "# AI Cost Optimization Report",
                "",
                f"**Analysis Date**: {report['analysis_timestamp']}  ",
                f"**Period**: {report['analysis_period_days']} days",
                "",
                "## Current Costs",
                "",
                f"- **Total Cost**: ${report['current_costs']['total_cost_usd']:.2f}",
                f"- **Total Requests**: {report['current_costs']['total_requests']:,}",
                f"- **Avg Cost/Request**: ${report['current_costs']['avg_cost_per_request']:.4f}",
                "",
                "## Cost Trends",
                "",
                f"- **Trend Direction**: {report['trends']['direction']}",
                f"- **Projected Monthly Cost**: ${report['trends']['projected_monthly_cost']:.2f}",
                "",
                "## Optimization Summary",
                "",
                f"- **Total Opportunities**: {report['summary']['total_opportunities']}",
                f"- **Potential Savings**: ${report['summary']['total_potential_savings_usd']:.2f} ({report['summary']['savings_percentage']:.1f}%)",
                f"- **High Priority Items**: {report['summary']['high_priority_count']}",
                "",
                "## Optimization Opportunities",
                "",
            ]

            for i, opp in enumerate(report["optimization_opportunities"], 1):
                lines.extend(
                    [
                        f"### {i}. {opp['title']}",
                        "",
                        f"- **Priority**: {opp['priority'].upper()}",
                        f"- **Category**: {opp['category']}",
                        f"- **Current Cost**: ${opp['current_cost_usd']:.2f}",
                        f"- **Potential Savings**: ${opp['potential_savings_usd']:.2f} ({opp['savings_percentage']:.1f}%)",
                        f"- **Action Required**: {opp['action_required']}",
                        f"- **Implementation Complexity**: {opp['complexity']}",
                        "",
                        f"**Description**: {opp['description']}",
                        "",
                    ],
                )

            return "\n".join(lines)

        else:
            raise ValueError(f"Unsupported format: {format}")


async def main():
    """Main entry point for cost optimization script."""
    if not HIVE_AI_AVAILABLE:
        print("ERROR: hive-ai package not available")
        print("Install with: pip install -e packages/hive-ai")
        sys.exit(1)

    import argparse

    parser = argparse.ArgumentParser(description="AI Cost Optimization Analysis")
    parser.add_argument("--days", type=int, default=30, help="Days to analyze (default: 30)")
    parser.add_argument("--format", choices=["text", "json", "markdown"], default="text", help="Output format")
    parser.add_argument("--output", type=str, help="Output file (default: stdout)")

    args = parser.parse_args()

    # Initialize (would normally load from config/database)
    from hive_ai import AIConfig

    config = AIConfig()
    cost_manager = CostManager(config)
    model_registry = ModelRegistry(config)

    # Run analysis
    optimizer = AIConstOptimizer(cost_manager, model_registry)
    report = await optimizer.analyze_and_optimize_async(analysis_days=args.days)

    # Export report
    output = optimizer.export_report(report, format=args.format)

    if args.output:
        Path(args.output).write_text(output)
        print(f"Report written to: {args.output}")
    else:
        print(output)

    # Exit with code based on high-priority opportunities
    if report["summary"]["high_priority_count"] > 0:
        print(f"\n⚠️  {report['summary']['high_priority_count']} high-priority optimization opportunities found")
        sys.exit(1)
    else:
        print("\n✅ No high-priority cost optimizations needed")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
