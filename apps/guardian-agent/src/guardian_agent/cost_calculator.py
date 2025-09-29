"""Custom cost calculator for Guardian Agent operations."""

from pathlib import Path
from typing import Any, Dict

from hive_app_toolkit.cost import ResourceCost, ResourceType


class GuardianCostCalculator:
    """Custom cost calculator for code review operations."""

    # Cost per operation by type and model
    COSTS = {
        "gpt-4": {
            "file_review": 0.05,  # $0.05 per file review
            "full_analysis": 0.10,  # $0.10 for comprehensive analysis
            "security_scan": 0.08,  # $0.08 for security-focused review
            "quick_review": 0.02,  # $0.02 for quick review
        },
        "gpt-3.5-turbo": {
            "file_review": 0.01,  # $0.01 per file review
            "full_analysis": 0.02,  # $0.02 for comprehensive analysis
            "security_scan": 0.015,  # $0.015 for security-focused review
            "quick_review": 0.005,  # $0.005 for quick review
        },
        "gpt-4-32k": {
            "file_review": 0.08,  # Higher cost for larger context
            "full_analysis": 0.15,
            "security_scan": 0.12,
            "quick_review": 0.03,
        },
    }

    def calculate_cost(self, operation: str, parameters: Dict[str, Any]) -> ResourceCost:
        """Calculate cost based on model, operation type, and file complexity."""
        model = parameters.get("model", "gpt-3.5-turbo")
        review_type = parameters.get("review_type", "file_review")
        file_paths = parameters.get("file_paths", [])

        # Get base cost per file
        cost_per_file = self.COSTS.get(model, {}).get(review_type, 0.01)

        # Calculate total files
        num_files = len(file_paths) if file_paths else 1

        # Adjust cost based on file size/complexity if file paths provided
        complexity_multiplier = 1.0
        if file_paths:
            total_size = 0
            for file_path in file_paths:
                try:
                    path = Path(file_path)
                    if path.exists():
                        size_kb = path.stat().st_size / 1024
                        total_size += size_kb
                except:
                    pass

            # Increase cost for larger files
            if total_size > 100:  # > 100KB total
                complexity_multiplier = 1.5
            elif total_size > 50:  # > 50KB total
                complexity_multiplier = 1.2

        total_cost = cost_per_file * num_files * complexity_multiplier

        # Determine resource type based on operation
        if review_type in ["security_scan"]:
            resource_type = ResourceType.AI_SECURITY
        elif model.startswith("gpt-4"):
            resource_type = ResourceType.AI_ADVANCED
        else:
            resource_type = ResourceType.AI_STANDARD

        return ResourceCost(
            resource_type=resource_type,
            units=num_files,
            cost_per_unit=cost_per_file * complexity_multiplier,
            metadata={
                "model": model,
                "review_type": review_type,
                "num_files": num_files,
                "complexity_multiplier": complexity_multiplier,
                "operation": operation,
            },
        )
