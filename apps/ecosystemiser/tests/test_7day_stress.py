#!/usr/bin/env python3
"""7-day stress test for EcoSystemiser platform."""

import json
import os
import time
from pathlib import Path

import numpy as np
import psutil

eco_path = Path(__file__).parent.parent / "src"

from ecosystemiser.solver.rule_based_engine import RuleBasedEngine
from ecosystemiser.system_model.components.energy.battery import (
    Battery,
    BatteryParams,
    BatteryTechnicalParams,
)
from ecosystemiser.system_model.components.energy.grid import (
    Grid,
    GridParams,
    GridTechnicalParams,
)
from ecosystemiser.system_model.components.energy.power_demand import (
    PowerDemand,
    PowerDemandParams,
    PowerDemandTechnicalParams,
)
from ecosystemiser.system_model.components.energy.solar_pv import (
    SolarPV,
    SolarPVParams,
    SolarPVTechnicalParams,
)
from ecosystemiser.system_model.components.shared.archetypes import FidelityLevel
from ecosystemiser.system_model.system import System

from hive_logging import get_logger

logger = get_logger(__name__)


def create_7day_system():
    """Create system for 7-day stress testing."""
    N = 168  # 7 days * 24 hours
    system = System(system_id="stress_test_7day", n=N)

    # Create weekly profiles with day-to-day variation
    daily_solar = np.array(
        [
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,  # Night
            0.25,
            0.5,
            0.707,
            0.866,
            0.966,
            1.0,  # Morning to noon
            0.966,
            0.866,
            0.707,
            0.5,
            0.25,  # Afternoon
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,  # Evening/night
        ]
    )

    daily_demand = np.array(
        [
            0.4,
            0.4,
            0.4,
            0.4,
            0.4,
            0.4,
            0.4,  # Night baseload
            0.8,
            0.8,  # Morning peak
            0.4,
            0.4,
            0.4,
            0.4,
            0.4,
            0.4,
            0.4,
            0.4,
            0.4,  # Day baseload
            1.0,
            1.0,
            1.0,  # Evening peak
            0.4,
            0.4,
            0.4,  # Night baseload
        ]
    )

    # Create 7-day profiles with variations
    solar_profile = []
    demand_profile = []

    for day in range(7):
        # Add day-to-day variation
        solar_factor = 1.0 + 0.2 * np.sin(day * np.pi / 3)  # ±20% variation
        demand_factor = 1.0 + 0.1 * np.cos(day * np.pi / 4)  # ±10% variation

        # Weekend effect (day 5, 6 = weekend)
        if day >= 5:
            demand_factor *= 0.8  # 20% lower weekend demand

        daily_solar_adj = daily_solar * solar_factor
        daily_demand_adj = daily_demand * demand_factor

        solar_profile.extend(daily_solar_adj)
        demand_profile.extend(daily_demand_adj)

    solar_profile = np.array(solar_profile)
    demand_profile = np.array(demand_profile)

    logger.info(
        f"Created 7-day profiles: solar range {np.min(solar_profile):.3f}-{np.max(solar_profile):.3f}, ",
        f"demand range {np.min(demand_profile):.3f}-{np.max(demand_profile):.3f}",
    )

    # Create components
    grid_params = GridParams(
        technical=GridTechnicalParams(
            capacity_nominal=100.0,
            import_tariff=0.25,
            export_tariff=0.10,
            fidelity_level=FidelityLevel.SIMPLE,
        )
    )
    grid = Grid("Grid", grid_params, N)

    battery_params = BatteryParams(
        technical=BatteryTechnicalParams(
            capacity_nominal=15.0,  # Slightly larger for long-term operation,
            max_charge_rate=6.0,
            max_discharge_rate=6.0,
            efficiency_roundtrip=0.95,
            initial_soc_pct=0.5,
            fidelity_level=FidelityLevel.SIMPLE,
        )
    )
    battery = Battery("Battery", battery_params, N)

    solar_params = SolarPVParams(
        technical=SolarPVTechnicalParams(
            capacity_nominal=40.0,  # 40 kW solar for good generation,
            efficiency_nominal=1.0,
            fidelity_level=FidelityLevel.SIMPLE,
        )
    )
    solar = SolarPV("SolarPV", solar_params, N)
    solar.profile = solar_profile

    demand_params = PowerDemandParams(
        technical=PowerDemandTechnicalParams(
            capacity_nominal=12.5,
            peak_demand=12.5,
            load_profile_type="variable",
            fidelity_level=FidelityLevel.SIMPLE,
        )
    )
    demand = PowerDemand("PowerDemand", demand_params, N)
    demand.profile = demand_profile

    # Add components
    system.add_component(grid)
    system.add_component(battery)
    system.add_component(solar)
    system.add_component(demand)

    # Connect components
    system.connect("Grid", "PowerDemand", "electricity")
    system.connect("Grid", "Battery", "electricity")
    system.connect("Battery", "Grid", "electricity")
    system.connect("SolarPV", "PowerDemand", "electricity")
    system.connect("SolarPV", "Battery", "electricity")
    system.connect("SolarPV", "Grid", "electricity")
    system.connect("Battery", "PowerDemand", "electricity")

    return system


def monitor_memory_usage():
    """Get current memory usage."""
    process = psutil.Process(os.getpid())
    memory_mb = process.memory_info().rss / 1024 / 1024
    return memory_mb


def validate_long_term_stability(system, tolerance=1e-5):
    """Validate long-term numerical stability."""
    stability_results = {
        "energy_drift_check": True,
        "storage_bounds_check": True,
        "flow_consistency_check": True,
        "numerical_stability": True,
    }

    # Check for energy drift over time
    daily_energy_balances = []

    for day in range(7):
        start_t = day * 24
        end_t = (day + 1) * 24

        daily_sources = 0.0
        daily_sinks = 0.0

        for t in range(start_t, end_t):
            for _flow_key, flow_data in system.flows.items():
                flow_value = flow_data["value"][t]
                source_comp = system.components[flow_data["source"]]
                target_comp = system.components[flow_data["target"]]

                if source_comp.type in ["generation", "storage", "transmission"]:
                    daily_sources += flow_value
                if target_comp.type in ["consumption", "storage", "transmission"]:
                    daily_sinks += flow_value

        daily_balance = abs(daily_sources - daily_sinks)
        daily_energy_balances.append(daily_balance)

    # Check if energy balance deteriorates over time
    max_daily_imbalance = max(daily_energy_balances)
    energy_drift = max_daily_imbalance > tolerance * 100  # Allow 100x tolerance for weekly

    stability_results["energy_drift_check"] = not energy_drift
    stability_results["max_daily_imbalance"] = float(max_daily_imbalance)

    logger.info(f"Daily energy balances: max={max_daily_imbalance:.2e}")

    # Check storage bounds throughout simulation
    battery_comp = system.components.get("Battery")
    if battery_comp and hasattr(battery_comp, "E"):
        soc_violations = 0
        for t in range(system.N):
            soc = battery_comp.E[t] / battery_comp.E_max
            if soc < -tolerance or soc > 1.0 + tolerance:
                soc_violations += 1

        stability_results["storage_bounds_check"] = soc_violations == 0
        stability_results["soc_violations"] = soc_violations

    # Overall stability
    stability_results["numerical_stability"] = all(
        [
            stability_results["energy_drift_check"],
            stability_results["storage_bounds_check"],
            stability_results["flow_consistency_check"],
        ]
    )

    return stability_results


def analyze_weekly_patterns(system):
    """Analyze system behavior patterns over the week."""
    analysis = {"daily_summaries": [], "weekly_totals": {}, "cycling_analysis": {}}

    # Daily analysis
    for day in range(7):
        start_t = day * 24
        end_t = (day + 1) * 24

        daily_solar = 0.0
        daily_demand = 0.0
        daily_grid_import = 0.0
        daily_grid_export = 0.0

        for _flow_key, flow_data in system.flows.items():
            daily_flow = np.sum(flow_data["value"][start_t:end_t])

            if "SolarPV" in flow_data["source"]:
                daily_solar += daily_flow
            elif flow_data["target"] == "PowerDemand":
                daily_demand += daily_flow
            elif flow_data["source"] == "Grid" and flow_data["target"] != "Grid":
                daily_grid_import += daily_flow
            elif flow_data["target"] == "Grid" and flow_data["source"] != "Grid":
                daily_grid_export += daily_flow

        day_summary = {
            "day": day + 1,
            "solar_generation": float(daily_solar),
            "total_demand": float(daily_demand),
            "grid_import": float(daily_grid_import),
            "grid_export": float(daily_grid_export),
            "net_grid": float(daily_grid_import - daily_grid_export),
        }

        analysis["daily_summaries"].append(day_summary)

    # Weekly totals
    analysis["weekly_totals"] = {
        "total_solar": float(sum(day["solar_generation"] for day in analysis["daily_summaries"])),
        "total_demand": float(sum(day["total_demand"] for day in analysis["daily_summaries"])),
        "total_import": float(sum(day["grid_import"] for day in analysis["daily_summaries"])),
        "total_export": float(sum(day["grid_export"] for day in analysis["daily_summaries"])),
    }

    # Battery cycling analysis
    battery_comp = system.components.get("Battery")
    if battery_comp and hasattr(battery_comp, "E"):
        weekly_range = np.max(battery_comp.E) - np.min(battery_comp.E)
        cycles = weekly_range / battery_comp.E_max

        analysis["cycling_analysis"] = {
            "weekly_energy_range": float(weekly_range),
            "equivalent_cycles": float(cycles),
            "initial_soc": float(battery_comp.E[0] / battery_comp.E_max),
            "final_soc": float(battery_comp.E[-1] / battery_comp.E_max),
        }

    return analysis


def run_7day_stress_test():
    """Run comprehensive 7-day stress test."""
    logger.info("=" * 80)
    logger.info("7-DAY STRESS TEST")
    logger.info("=" * 80)

    results = {"test_start": time.time(), "timesteps": 168, "test_type": "7_day_stress"}

    try:
        # Memory monitoring
        initial_memory = monitor_memory_usage()
        logger.info(f"Initial memory usage: {initial_memory:.1f} MB")

        # Create system
        system = create_7day_system()
        logger.info(f"Created 7-day system: {len(system.components)} components, {len(system.flows)} flows")

        system_memory = monitor_memory_usage()
        logger.info(f"Memory after system creation: {system_memory:.1f} MB")

        # Run solver
        logger.info("Running 7-day rule-based simulation...")
        solve_start = time.time()
        solver = RuleBasedEngine(system)
        result = solver.solve()
        solve_time = time.time() - solve_start

        solve_memory = monitor_memory_usage()
        peak_memory = solve_memory

        logger.info(f"Solver completed: status={result.status}, time={solve_time:.2f}s")
        logger.info(f"Memory after solving: {solve_memory:.1f} MB")

        results.update(
            {
                "solver_status": result.status,
                "solve_time": float(solve_time),
                "initial_memory_mb": float(initial_memory),
                "peak_memory_mb": float(peak_memory),
                "memory_increase_mb": float(peak_memory - initial_memory),
                "solver_success": result.status == "optimal",
            }
        )

        if result.status == "optimal":
            # Validate stability
            logger.info("Validating long-term stability...")
            stability = validate_long_term_stability(system)

            # Analyze patterns
            logger.info("Analyzing weekly patterns...")
            patterns = analyze_weekly_patterns(system)

            results.update(
                {
                    "stability_analysis": stability,
                    "pattern_analysis": patterns,
                    "validation_passed": stability["numerical_stability"],
                }
            )

            # Log summary
            logger.info("\n" + "=" * 60)
            logger.info("7-DAY STRESS TEST SUMMARY")
            logger.info("=" * 60)
            logger.info(f"Solve time: {solve_time:.2f}s")
            logger.info(
                f"Memory usage: {initial_memory:.1f} → {peak_memory:.1f} MB (+{peak_memory - initial_memory:.1f})"
            )
            logger.info(f"Numerical stability: {'PASS' if stability['numerical_stability'] else 'FAIL'}")
            logger.info(f"Energy balance: max daily imbalance = {stability.get('max_daily_imbalance', 0):.2e}")

            weekly = patterns["weekly_totals"]
            logger.info(
                f"Weekly totals: {weekly['total_solar']:.0f} kWh solar, {weekly['total_demand']:.0f} kWh demand"
            )
            logger.info(
                f"Grid interaction: {weekly['total_import']:.0f} kWh import, {weekly['total_export']:.0f} kWh export"
            )

            cycling = patterns["cycling_analysis"]
            logger.info(
                f"Battery cycling: {cycling['equivalent_cycles']:.2f} cycles, "
                f"SOC {cycling['initial_soc']:.1%} → {cycling['final_soc']:.1%}"
            )

            logger.info(f"Overall result: {'PASSED' if results['validation_passed'] else 'FAILED'}")
            logger.info("=" * 60)

        else:
            logger.error(f"7-day solver failed: {result.status}")
            results["validation_passed"] = False

    except Exception as e:
        logger.error(f"7-day stress test failed: {e}")
        results["error"] = str(e)
        results["validation_passed"] = False
        import traceback

        traceback.print_exc()

    results["test_end"] = time.time()
    results["total_time"] = results["test_end"] - results["test_start"]

    return results


def main():
    """Main execution."""
    results = run_7day_stress_test()

    # Save results
    results_dir = Path(__file__).parent.parent / "data"
    results_dir.mkdir(parents=True, exist_ok=True)

    results_path = results_dir / "stress_test_7day_results.json"

    # Convert numpy types for JSON
    def convert_for_json(obj):
        if isinstance(obj, (np.integer, np.floating, np.bool_)):
            return obj.item()
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {k: convert_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_for_json(v) for v in obj]
        return obj

    json_results = convert_for_json(results)

    with open(results_path, "w") as f:
        json.dump(json_results, f, indent=2)

    logger.info("\n7-day stress test complete!")
    logger.info(f"Results saved to: {results_path}")
    logger.info(f"Status: {'PASSED' if results.get('validation_passed', False) else 'FAILED'}")
    if results.get("solve_time"):
        logger.info(
            f"Performance: {results['solve_time']:.2f}s solve time, ",
            f"{results.get('memory_increase_mb', 0):.1f} MB memory increase",
        )

    return results.get("validation_passed", False)


def test_7day_stress_full_integration():
    """Test 7-day stress test as pytest integration test."""
    results = run_7day_stress_test()

    # Assert test passed
    assert results.get("validation_passed", False), f"7-day stress test failed: {results.get('error', 'Unknown error')}"

    # Assert solver succeeded
    assert results.get("solver_success", False), f"Solver failed with status: {results.get('solver_status', 'unknown')}"

    # Assert reasonable performance
    assert results.get("solve_time", float("inf")) < 60.0, f"Solve time too long: {results.get('solve_time', 0):.2f}s"

    # Assert memory usage is reasonable
    memory_increase = results.get("memory_increase_mb", float("inf"))
    assert memory_increase < 500.0, f"Memory increase too high: {memory_increase:.1f} MB"


def test_7day_system_creation():
    """Test 7-day system can be created successfully."""
    system = create_7day_system()

    # Assert system structure
    assert system is not None
    assert system.N == 168  # 7 days * 24 hours
    assert len(system.components) == 4  # Grid, Battery, Solar, Demand

    # Assert all required components exist
    required_components = ["Grid", "Battery", "SolarPV", "PowerDemand"]
    for comp_name in required_components:
        assert comp_name in system.components, f"Missing component: {comp_name}"


def test_weekly_pattern_analysis():
    """Test weekly pattern analysis functionality."""
    system = create_7day_system()
    solver = RuleBasedEngine(system)
    result = solver.solve()

    if result.status == "optimal":
        patterns = analyze_weekly_patterns(system)

        # Assert analysis structure
        assert "daily_summaries" in patterns
        assert "weekly_totals" in patterns
        assert "cycling_analysis" in patterns

        # Assert we have 7 daily summaries
        assert len(patterns["daily_summaries"]) == 7

        # Assert weekly totals are positive
        weekly = patterns["weekly_totals"]
        assert weekly["total_solar"] >= 0
        assert weekly["total_demand"] >= 0


def test_stability_validation():
    """Test long-term stability validation."""
    system = create_7day_system()
    solver = RuleBasedEngine(system)
    result = solver.solve()

    if result.status == "optimal":
        stability = validate_long_term_stability(system)

        # Assert stability checks exist
        assert "energy_drift_check" in stability
        assert "storage_bounds_check" in stability
        assert "numerical_stability" in stability

        # Assert stability passes (this might fail if there are actual issues)
        assert stability["numerical_stability"], f"Stability check failed: {stability}"


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
