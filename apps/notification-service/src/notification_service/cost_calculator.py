"""Custom cost calculator for notification operations."""

from typing import Any, Dict

from hive_app_toolkit.cost import ResourceCost, ResourceType


class NotificationCostCalculator:
    """Custom cost calculator for different notification types."""

    # Cost per notification by provider and priority
    COSTS = {
        "email": {
            "low": 0.001,  # $0.001 per low priority email
            "normal": 0.002,  # $0.002 per normal email
            "high": 0.005,  # $0.005 per high priority email
            "urgent": 0.010,  # $0.010 per urgent email
        },
        "slack": {
            "low": 0.0005,  # Slack is cheaper
            "normal": 0.001,
            "high": 0.0025,
            "urgent": 0.005,
        },
        "sms": {
            "low": 0.05,  # SMS is most expensive
            "normal": 0.05,
            "high": 0.05,
            "urgent": 0.05,
        },
    }

    def calculate_cost(self, operation: str, parameters: Dict[str, Any]) -> ResourceCost:
        """Calculate cost based on provider and priority."""
        provider = parameters.get("provider", "email")
        priority = parameters.get("priority", "normal")

        # Get cost per notification
        cost_per_unit = self.COSTS.get(provider, {}).get(priority, 0.002)

        # Determine resource type
        if provider == "email":
            resource_type = ResourceType.EMAIL
        elif provider == "sms":
            resource_type = ResourceType.SMS
        else:
            resource_type = ResourceType.API_CALL

        return ResourceCost(
            resource_type=resource_type,
            units=1,  # One notification
            cost_per_unit=cost_per_unit,
            metadata={
                "provider": provider,
                "priority": priority,
                "operation": operation,
            },
        )
