"""
AI cost management and budget control.

Provides comprehensive cost tracking, budget enforcement
and optimization recommendations for AI operations.
"""
from __future__ import annotations


import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, ListTuple

from hive_cache import CacheManager
from hive_db import AsyncSession, get_async_session
from hive_logging import get_logger

from ..core.exceptions import AIError, CostLimitError
from ..core.interfaces import TokenUsage

logger = get_logger(__name__)


class BudgetPeriod(Enum):
    """Budget tracking periods."""

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


@dataclass
class CostBudget:
    """Budget configuration for cost control."""

    name: str
    period: BudgetPeriod
    limit: float  # USD
    warning_threshold: float = 0.8  # 80% of limit
    enabled: bool = True
    categories: List[str] = field(default_factory=list)  # model, provider, operation
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CostRecord:
    """Individual cost record."""

    timestamp: datetime
    model: str
    provider: str
    operation: str
    tokens_used: int
    cost_usd: float
    request_id: str | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CostSummary:
    """Cost summary for a period."""

    period: str
    total_cost: float
    total_tokens: int
    total_requests: int
    breakdown_by_model: Dict[str, float]
    breakdown_by_provider: Dict[str, float]
    breakdown_by_operation: Dict[str, float]
    top_expensive_operations: List[Dict[str, Any]]


@dataclass
class BudgetStatus:
    """Current status of a budget."""

    budget_name: str
    period: BudgetPeriod
    current_spending: float
    budget_limit: float
    percentage_used: float
    remaining_budget: float
    warning_triggered: bool
    limit_exceeded: bool
    time_remaining: timedelta


class CostManager:
    """
    Comprehensive AI cost management and budget control.

    Provides real-time cost tracking, budget enforcement
    and optimization recommendations for AI operations.
    """

    def __init__(self, config: Any = None):  # AIConfig type
        self.config = config
        self.cache = CacheManager("cost_manager")

        # Cost tracking
        self._cost_records: List[CostRecord] = []
        self._budgets: Dict[str, CostBudget] = {}

        # Cost aggregations
        self._hourly_costs: Dict[str, float] = defaultdict(float)
        self._daily_costs: Dict[str, float] = defaultdict(float)
        self._monthly_costs: Dict[str, float] = defaultdict(float)

        # Budget alerts
        self._budget_alerts: List[Dict[str, Any]] = []

        # Load default budgets if config provided
        if config:
            self._initialize_default_budgets()

    def _initialize_default_budgets(self) -> None:
        """Initialize default budgets from configuration."""
        if hasattr(self.config, "daily_cost_limit"):
            self.add_budget(
                CostBudget(
                    name="daily_limit"
                    period=BudgetPeriod.DAILY
                    limit=self.config.daily_cost_limit
                    warning_threshold=0.8
                )
            )

        if hasattr(self.config, "monthly_cost_limit"):
            self.add_budget(
                CostBudget(
                    name="monthly_limit"
                    period=BudgetPeriod.MONTHLY
                    limit=self.config.monthly_cost_limit
                    warning_threshold=0.9
                )
            )

    def add_budget(self, budget: CostBudget) -> None:
        """Add a new cost budget."""
        self._budgets[budget.name] = budget
        logger.info(f"Added budget: {budget.name} (${budget.limit} {budget.period.value})")

    def remove_budget(self, budget_name: str) -> bool:
        """Remove a cost budget."""
        if budget_name in self._budgets:
            del self._budgets[budget_name]
            logger.info(f"Removed budget: {budget_name}")
            return True
        return False

    async def record_cost_async(
        self
        model: str
        provider: str
        operation: str
        tokens_used: TokenUsage
        cost_usd: float
        request_id: str | None = None
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record a cost event.

        Args:
            model: Model name used
            provider: AI provider
            operation: Type of operation
            tokens_used: Token usage information
            cost_usd: Cost in USD
            request_id: Optional request identifier
            metadata: Additional metadata

        Raises:
            CostLimitError: Budget limit exceeded
        """
        timestamp = datetime.utcnow()

        # Create cost record
        record = CostRecord(
            timestamp=timestamp
            model=model
            provider=provider
            operation=operation
            tokens_used=tokens_used.total_tokens
            cost_usd=cost_usd
            request_id=request_id
            metadata=metadata or {}
        )

        # Store record
        self._cost_records.append(record)

        # Update aggregations
        self._update_cost_aggregations(record)

        # Check budgets
        await self._check_budgets_async(record)

        # Persist to database if available
        try:
            await self._persist_cost_record_async(record)
        except Exception as e:
            logger.warning(f"Failed to persist cost record: {e}")

        logger.debug(f"Recorded cost: {model} ${cost_usd:.4f} " f"({tokens_used.total_tokens} tokens)")

    def _update_cost_aggregations(self, record: CostRecord) -> None:
        """Update cost aggregation buckets."""
        # Hourly aggregation
        hour_key = record.timestamp.strftime("%Y-%m-%d-%H")
        self._hourly_costs[hour_key] += record.cost_usd

        # Daily aggregation
        day_key = record.timestamp.strftime("%Y-%m-%d")
        self._daily_costs[day_key] += record.cost_usd

        # Monthly aggregation
        month_key = record.timestamp.strftime("%Y-%m")
        self._monthly_costs[month_key] += record.cost_usd

    async def _check_budgets_async(self, record: CostRecord) -> None:
        """Check if any budget limits are exceeded."""
        for budget_name, budget in self._budgets.items():
            if not budget.enabled:
                continue

            try:
                status = await self.get_budget_status_async(budget_name)

                # Check warning threshold
                if status.percentage_used >= budget.warning_threshold and not status.warning_triggered:
                    self._budget_alerts.append(
                        {
                            "type": "budget_warning"
                            "budget_name": budget_name
                            "message": f"Budget {budget_name} is {status.percentage_used:.1%} used"
                            "current_spending": status.current_spending
                            "budget_limit": status.budget_limit
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    )

                    logger.warning(f"Budget warning: {budget_name} is {status.percentage_used:.1%} used")

                # Check limit exceeded
                if status.limit_exceeded:
                    self._budget_alerts.append(
                        {
                            "type": "budget_exceeded"
                            "budget_name": budget_name
                            "message": f"Budget {budget_name} limit exceeded"
                            "current_spending": status.current_spending
                            "budget_limit": status.budget_limit
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    )

                    logger.error(
                        f"Budget limit exceeded: {budget_name} "
                        f"(${status.current_spending:.2f} / ${status.budget_limit:.2f})"
                    )

                    # Raise exception to halt operation
                    raise CostLimitError(
                        f"Budget '{budget_name}' limit exceeded"
                        current_cost=status.current_spending
                        limit=status.budget_limit
                        period=budget.period.value
                    )

            except CostLimitError:
                raise  # Re-raise cost limit errors
            except Exception as e:
                logger.error(f"Error checking budget {budget_name}: {e}")

    async def get_budget_status_async(self, budget_name: str) -> BudgetStatus:
        """
        Get current status of a specific budget.

        Args:
            budget_name: Name of budget to check

        Returns:
            BudgetStatus with current state

        Raises:
            AIError: Budget not found
        """
        if budget_name not in self._budgets:
            raise AIError(f"Budget '{budget_name}' not found")

        budget = self._budgets[budget_name]
        current_spending = await self._calculate_period_cost_async(budget.period)

        percentage_used = current_spending / budget.limit if budget.limit > 0 else 0
        remaining_budget = max(0, budget.limit - current_spending)
        warning_triggered = percentage_used >= budget.warning_threshold
        limit_exceeded = current_spending > budget.limit

        # Calculate time remaining in period
        time_remaining = self._calculate_time_remaining(budget.period)

        return BudgetStatus(
            budget_name=budget_name
            period=budget.period
            current_spending=current_spending
            budget_limit=budget.limit
            percentage_used=percentage_used
            remaining_budget=remaining_budget
            warning_triggered=warning_triggered
            limit_exceeded=limit_exceeded
            time_remaining=time_remaining
        )

    async def _calculate_period_cost_async(self, period: BudgetPeriod) -> float:
        """Calculate total cost for the current period."""
        now = datetime.utcnow()

        if period == BudgetPeriod.HOURLY:
            hour_key = now.strftime("%Y-%m-%d-%H")
            return self._hourly_costs.get(hour_key, 0.0)

        elif period == BudgetPeriod.DAILY:
            day_key = now.strftime("%Y-%m-%d")
            return self._daily_costs.get(day_key, 0.0)

        elif period == BudgetPeriod.WEEKLY:
            # Calculate week start (Monday)
            week_start = now - timedelta(days=now.weekday())
            week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
            return sum(record.cost_usd for record in self._cost_records if record.timestamp >= week_start)

        elif period == BudgetPeriod.MONTHLY:
            month_key = now.strftime("%Y-%m")
            return self._monthly_costs.get(month_key, 0.0)

        elif period == BudgetPeriod.QUARTERLY:
            # Calculate quarter start
            quarter = (now.month - 1) // 3 + 1
            quarter_start = datetime(now.year, (quarter - 1) * 3 + 1, 1)
            return sum(record.cost_usd for record in self._cost_records if record.timestamp >= quarter_start)

        elif period == BudgetPeriod.YEARLY:
            year_start = datetime(now.year, 1, 1)
            return sum(record.cost_usd for record in self._cost_records if record.timestamp >= year_start)

        return 0.0

    def _calculate_time_remaining(self, period: BudgetPeriod) -> timedelta:
        """Calculate time remaining in the current period."""
        now = datetime.utcnow()

        if period == BudgetPeriod.HOURLY:
            next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            return next_hour - now

        elif period == BudgetPeriod.DAILY:
            next_day = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            return next_day - now

        elif period == BudgetPeriod.WEEKLY:
            days_until_monday = (7 - now.weekday()) % 7
            next_week = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=days_until_monday)
            return next_week - now

        elif period == BudgetPeriod.MONTHLY:
            if now.month == 12:
                next_month = datetime(now.year + 1, 1, 1)
            else:
                next_month = datetime(now.year, now.month + 1, 1)
            return next_month - now

        elif period == BudgetPeriod.QUARTERLY:
            quarter = (now.month - 1) // 3 + 1
            if quarter == 4:
                next_quarter = datetime(now.year + 1, 1, 1)
            else:
                next_quarter = datetime(now.year, quarter * 3 + 1, 1)
            return next_quarter - now

        elif period == BudgetPeriod.YEARLY:
            next_year = datetime(now.year + 1, 1, 1)
            return next_year - now

        return timedelta(0)

    async def get_cost_summary_async(
        self, start_date: datetime | None = None, end_date: datetime | None = None
    ) -> CostSummary:
        """
        Get comprehensive cost summary for a period.

        Args:
            start_date: Start of period (default: 30 days ago)
            end_date: End of period (default: now)

        Returns:
            CostSummary with detailed breakdown
        """
        end_date = end_date or datetime.utcnow()
        start_date = start_date or (end_date - timedelta(days=30))

        # Filter records for period
        period_records = [record for record in self._cost_records if start_date <= record.timestamp <= end_date]

        if not period_records:
            return CostSummary(
                period=f"{start_date.date()} to {end_date.date()}"
                total_cost=0.0
                total_tokens=0
                total_requests=0
                breakdown_by_model={}
                breakdown_by_provider={}
                breakdown_by_operation={}
                top_expensive_operations=[]
            )

        # Calculate totals
        total_cost = sum(record.cost_usd for record in period_records)
        total_tokens = sum(record.tokens_used for record in period_records)
        total_requests = len(period_records)

        # Breakdowns
        model_costs = defaultdict(float)
        provider_costs = defaultdict(float)
        operation_costs = defaultdict(float)

        for record in period_records:
            model_costs[record.model] += record.cost_usd
            provider_costs[record.provider] += record.cost_usd
            operation_costs[record.operation] += record.cost_usd

        # Top expensive operations
        expensive_ops = sorted(
            [
                {
                    "model": record.model
                    "provider": record.provider
                    "operation": record.operation
                    "cost": record.cost_usd
                    "tokens": record.tokens_used
                    "timestamp": record.timestamp.isoformat()
                }
                for record in period_records
            ]
            key=lambda x: x["cost"]
            reverse=True
        )[:10]

        return CostSummary(
            period=f"{start_date.date()} to {end_date.date()}"
            total_cost=total_cost
            total_tokens=total_tokens
            total_requests=total_requests
            breakdown_by_model=dict(model_costs)
            breakdown_by_provider=dict(provider_costs)
            breakdown_by_operation=dict(operation_costs)
            top_expensive_operations=expensive_ops
        )

    async def get_cost_trends_async(self, days: int = 30) -> Dict[str, Any]:
        """Get cost trends and projections."""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Daily cost trends
        daily_trends = defaultdict(float)
        for record in self._cost_records:
            if start_date <= record.timestamp <= end_date:
                day_key = record.timestamp.strftime("%Y-%m-%d")
                daily_trends[day_key] += record.cost_usd

        # Calculate trend statistics
        daily_costs = list(daily_trends.values())
        if daily_costs:
            avg_daily_cost = sum(daily_costs) / len(daily_costs)
            min_daily_cost = min(daily_costs)
            max_daily_cost = max(daily_costs)

            # Simple linear trend (positive = increasing costs)
            x = list(range(len(daily_costs)))
            y = daily_costs
            if len(x) > 1:
                slope = sum((x[i] - sum(x) / len(x)) * (y[i] - sum(y) / len(y)) for i in range(len(x))) / sum(
                    (x[i] - sum(x) / len(x)) ** 2 for i in range(len(x))
                )
                trend_direction = "increasing" if slope > 0 else "decreasing" if slope < 0 else "stable"
            else:
                trend_direction = "stable"

            # Project next 7 days
            projected_weekly_cost = avg_daily_cost * 7
            projected_monthly_cost = avg_daily_cost * 30
        else:
            avg_daily_cost = 0
            min_daily_cost = 0
            max_daily_cost = 0
            trend_direction = "stable"
            projected_weekly_cost = 0
            projected_monthly_cost = 0

        return {
            "analysis_period_days": days
            "daily_trends": dict(daily_trends)
            "statistics": {
                "avg_daily_cost": avg_daily_cost
                "min_daily_cost": min_daily_cost
                "max_daily_cost": max_daily_cost
                "trend_direction": trend_direction
            }
            "projections": {
                "projected_weekly_cost": projected_weekly_cost
                "projected_monthly_cost": projected_monthly_cost
            }
        }

    async def get_optimization_recommendations_async(self) -> List[Dict[str, Any]]:
        """Get cost optimization recommendations."""
        recommendations = []

        # Analyze recent costs
        summary = await self.get_cost_summary_async()

        # High-cost model recommendations
        if summary.breakdown_by_model:
            most_expensive_model = max(summary.breakdown_by_model.items(), key=lambda x: x[1])

            if most_expensive_model[1] > summary.total_cost * 0.5:
                recommendations.append(
                    {
                        "type": "model_optimization"
                        "priority": "high"
                        "title": "Consider alternative model"
                        "description": f"Model '{most_expensive_model[0]}' accounts for "
                        f"{most_expensive_model[1]/summary.total_cost:.1%} of costs"
                        "suggestion": "Evaluate if a more cost-effective model could achieve similar results"
                        "potential_savings": most_expensive_model[1] * 0.3,  # Estimated 30% savings
                    }
                )

        # High token usage recommendations
        if summary.total_tokens > 100000:  # 100k tokens
            recommendations.append(
                {
                    "type": "token_optimization"
                    "priority": "medium"
                    "title": "Optimize prompt length"
                    "description": f"High token usage detected ({summary.total_tokens:,} tokens)"
                    "suggestion": "Review prompts for unnecessary length, use prompt optimization features"
                    "potential_savings": summary.total_cost * 0.2,  # Estimated 20% savings
                }
            )

        # Provider cost comparison
        if len(summary.breakdown_by_provider) > 1:
            provider_costs = sorted(summary.breakdown_by_provider.items(), key=lambda x: x[1], reverse=True)

            if len(provider_costs) >= 2:
                most_expensive = provider_costs[0]
                least_expensive = provider_costs[-1]

                if most_expensive[1] > least_expensive[1] * 2:
                    recommendations.append(
                        {
                            "type": "provider_optimization"
                            "priority": "medium"
                            "title": "Review provider selection"
                            "description": f"Provider '{most_expensive[0]}' costs significantly more than '{least_expensive[0]}'"
                            "suggestion": "Evaluate if cheaper providers can handle some workloads"
                            "potential_savings": (most_expensive[1] - least_expensive[1]) * 0.5
                        }
                    )

        return recommendations

    async def _persist_cost_record_async(self, record: CostRecord) -> None:
        """Persist cost record to database."""
        # Implementation would depend on database schema
        # This is a placeholder for actual database persistence
        pass

    def get_budget_alerts(self) -> List[Dict[str, Any]]:
        """Get recent budget alerts."""
        # Return recent alerts (last 24 hours)
        cutoff = datetime.utcnow() - timedelta(hours=24)
        recent_alerts = [alert for alert in self._budget_alerts if datetime.fromisoformat(alert["timestamp"]) > cutoff]
        return recent_alerts

    def clear_alerts(self) -> None:
        """Clear all budget alerts."""
        self._budget_alerts.clear()

    async def export_cost_data_async(
        self, start_date: datetime | None = None, end_date: datetime | None = None, format: str = "json"
    ) -> Dict[str, Any]:
        """Export cost data for external analysis."""
        end_date = end_date or datetime.utcnow()
        start_date = start_date or (end_date - timedelta(days=30))

        # Filter records
        records = [record for record in self._cost_records if start_date <= record.timestamp <= end_date]

        export_data = {
            "metadata": {
                "exported_at": datetime.utcnow().isoformat()
                "period": {"start": start_date.isoformat(), "end": end_date.isoformat()}
                "format": format
                "record_count": len(records)
            }
            "cost_records": [
                {
                    "timestamp": record.timestamp.isoformat()
                    "model": record.model
                    "provider": record.provider
                    "operation": record.operation
                    "tokens_used": record.tokens_used
                    "cost_usd": record.cost_usd
                    "request_id": record.request_id
                    "metadata": record.metadata
                }
                for record in records
            ]
            "summary": await self.get_cost_summary_async(start_date, end_date)
        }

        return export_data

    async def close_async(self) -> None:
        """Close cost manager and clean up resources."""
        self.cache.clear()
        logger.info("Cost manager closed")
