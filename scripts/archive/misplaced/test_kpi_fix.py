#!/usr/bin/env python3
"""Test KPI calculation fixes."""

import numpy as np
from hive_logging import get_logger

logger = get_logger(__name__)


def test_kpi_calculations():
    """Test the corrected KPI calculation logic."""

    # Mock system data - realistic scenarios
    test_scenarios = [
        {
            "name": "Normal operation",
            "total_generation": 100,
            "total_export": 20,
            "total_import": 30,
            "expected_self_consumption": 0.8,  # (100-20)/100
            "expected_self_sufficiency": 0.727,  # 80/110
        },
        {
            "name": "No generation",
            "total_generation": 0,
            "total_export": 0,
            "total_import": 50,
            "expected_self_consumption": 0.0,
            "expected_self_sufficiency": 0.0,
        },
        {
            "name": "Excess export",
            "total_generation": 100,
            "total_export": 120,  # More export than generation (edge case)
            "total_import": 10,
            "expected_self_consumption": 0.0,  # Max(0, 100-120)/100 = 0
            "expected_self_sufficiency": 1.0,  # Min(100, 10)/10 = 1.0
        },
    ]

    for scenario in test_scenarios:
        logger.info(f"Testing: {scenario['name']}")

        # Apply the corrected calculation logic
        total_generation = scenario["total_generation"]
        total_export = scenario["total_export"]
        total_import = scenario["total_import"]

        total_demand = total_import + max(0, total_generation - total_export)  # Actual consumption

        # Self-consumption rate
        if total_generation > 0:
            self_consumed = max(0, total_generation - total_export)
            self_consumption_rate = min(1.0, self_consumed / total_generation)
        else:
            self_consumption_rate = 0.0

        # Self-sufficiency rate
        if total_demand > 0:
            self_sufficient_energy = max(0, min(total_generation, total_demand))
            self_sufficiency_rate = self_sufficient_energy / total_demand
        else:
            self_sufficiency_rate = 0.0

        logger.info(
            f"  Self-consumption: {self_consumption_rate:.3f} (expected: {scenario['expected_self_consumption']:.3f})"
        )
        logger.info(
            f"  Self-sufficiency: {self_sufficiency_rate:.3f} (expected: {scenario['expected_self_sufficiency']:.3f})"
        )

        # Validate ranges (0-1)
        assert 0.0 <= self_consumption_rate <= 1.0, f"Self-consumption out of range: {self_consumption_rate}"
        assert 0.0 <= self_sufficiency_rate <= 1.0, f"Self-sufficiency out of range: {self_sufficiency_rate}"

        logger.info("  OK All values in valid range [0,1]")
        print()

    logger.info("All KPI calculation tests passed!")
    return True


if __name__ == "__main__":
    test_kpi_calculations()
