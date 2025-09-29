from hive_logging import get_logger

logger = get_logger(__name__)

#!/usr/bin/env python3
"""
Example: Parametric Sweep for Battery and Solar Capacity Optimization

This example demonstrates how to use StudyService to explore a design space
and find optimal configurations for a renewable energy system.
"""

from datetime import datetime
from typing import Any

from ecosystemiser.services.study_service import ParameterSweepSpec, SimulationConfig, StudyConfig, StudyService
from ecosystemiser.services.study_service_enhanced import ParametricSweepEnhancement


def create_example_system_config() -> dict[str, Any]:
    """Create a simple renewable energy system configuration."""
    return {
        "name": "renewable_energy_system",
        "components": [
            {
                "name": "battery",
                "type": "storage",
                "subtype": "battery",
                "technical": {
                    "capacity_nominal": 100.0,  # kWh,
                    "power_charge_max": 50.0,  # kW,
                    "power_discharge_max": 50.0,  # kW,
                    "efficiency_charge": 0.95,
                    "efficiency_discharge": 0.95,
                    "soc_min": 0.1,
                    "soc_max": 0.9,
                },
                "economic": {"capex_per_kwh": 500, "opex_per_kwh_year": 10},
            },
            {
                "name": "solar_pv",
                "type": "generator",
                "subtype": "solar_pv",
                "technical": {
                    "capacity_nominal": 50.0,  # kW,
                    "efficiency": 0.18,
                    "degradation_rate": 0.005,
                },
                "economic": {"capex_per_kw": 1200, "opex_per_kw_year": 20},
            },
            {
                "name": "grid",
                "type": "grid",
                "technical": {
                    "power_import_max": 100.0,  # kW,
                    "power_export_max": 50.0,  # kW
                },
                "economic": {
                    "price_import": 0.25,  # $/kWh,
                    "price_export": 0.10,  # $/kWh
                },
            },
            {"name": "load", "type": "demand", "subtype": "electrical", "profile": "residential_typical"},
        ],
        "constraints": {"renewable_fraction_min": 0.5, "grid_independence_hours": 4},
    }


def run_battery_capacity_sweep() -> Any:
    """Run a sweep of battery capacity values to find optimal size."""
    logger.info("=" * 60)
    logger.info("BATTERY CAPACITY OPTIMIZATION")
    logger.info("=" * 60)

    # Create base configuration
    system_config = create_example_system_config()

    base_sim_config = SimulationConfig(
        simulation_id="battery_sweep_base",
        system_config=system_config,
        profile_config={"location": "Berlin", "year": 2023, "resolution": "1H"},
        solver_config={
            "solver_type": "milp",
            "objective": "minimize_cost",
            "horizon_hours": 24 * 7,  # One week
        },
        output_config={"save_results": True, "directory": "parametric_studies/battery_capacity"},
    )

    # Create battery capacity sweep
    battery_values = ParametricSweepEnhancement.create_battery_capacity_sweep(
        base_capacity=100, num_points=7, range_factor=3.0,
    )

    battery_sweep = ParameterSweepSpec(
        component_name="battery", parameter_path="technical.capacity_nominal", values=battery_values,
    )

    # Configure study
    study_config = StudyConfig(
        study_id=f"battery_capacity_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        study_type="parametric",
        base_config=base_sim_config,
        parameter_sweeps=[battery_sweep],
        parallel_execution=True,
        max_workers=4,
        save_all_results=True,
    )

    # Run study
    logger.info(f"\nRunning parametric sweep with {len(battery_values)} battery capacity values:")
    logger.info(f"Values: {[f'{v:.1f} kWh' for v in battery_values]}")

    study_service = StudyService()
    result = study_service.run_study(study_config)

    # Analyze results
    logger.info(f"\n{'=' * 40}")
    logger.info("RESULTS SUMMARY")
    logger.info(f"{'=' * 40}")
    logger.info(f"Total simulations: {result.num_simulations}")
    logger.info(f"Successful: {result.successful_simulations}")
    logger.info(f"Failed: {result.failed_simulations}")
    logger.info(f"Execution time: {result.execution_time:.1f} seconds")

    if result.best_result:
        best_params = result.best_result.get("output_config", {}).get("parameter_settings", {})
        best_kpis = result.best_result.get("kpis", {})

        logger.info("\nOPTIMAL CONFIGURATION:")
        logger.info(f"Battery capacity: {best_params.get('battery.technical.capacity_nominal', 'N/A')} kWh")
        logger.info(f"Total cost: ${best_kpis.get('total_cost', 'N/A'):,.0f}")
        logger.info(f"Renewable fraction: {best_kpis.get('renewable_fraction', 0) * 100:.1f}%")

    # Perform influence analysis
    analysis = ParametricSweepEnhancement.analyze_parameter_influence(result.model_dump())

    if analysis["recommendations"]:
        logger.info("\nRECOMMENDATIONS:")
        for rec in analysis["recommendations"]:
            logger.info(f"- {rec}")

    return result


def run_multi_parameter_sweep() -> Any:
    """Run a sweep of both battery and solar capacity."""
    logger.info("\n" + "=" * 60)
    logger.info("MULTI-PARAMETER OPTIMIZATION (Battery + Solar)")
    logger.info("=" * 60)

    system_config = create_example_system_config()

    base_sim_config = SimulationConfig(
        simulation_id="multi_sweep_base",
        system_config=system_config,
        profile_config={
            "location": "Madrid",  # Sunnier location,
            "year": 2023,
            "resolution": "1H",
        },
        solver_config={"solver_type": "milp", "objective": "minimize_cost", "horizon_hours": 24 * 7},
        output_config={"save_results": True, "directory": "parametric_studies/multi_parameter"},
    )

    # Create parameter sweeps
    battery_sweep = ParameterSweepSpec(
        component_name="battery",
        parameter_path="technical.capacity_nominal",
        values=[50, 100, 150, 200],  # kWh
    )

    solar_sweep = ParameterSweepSpec(
        component_name="solar_pv",
        parameter_path="technical.capacity_nominal",
        values=[25, 50, 75, 100],  # kW
    )

    # Configure study
    study_config = StudyConfig(
        study_id=f"multi_param_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        study_type="parametric",
        base_config=base_sim_config,
        parameter_sweeps=[battery_sweep, solar_sweep],
        parallel_execution=True,
        max_workers=4,
        save_all_results=True,
    )

    logger.info("\nRunning parametric sweep:")
    logger.info(f"Battery capacity values: {battery_sweep.values} kWh")
    logger.info(f"Solar capacity values: {solar_sweep.values} kW")
    logger.info(f"Total combinations: {len(battery_sweep.values) * len(solar_sweep.values)}")

    study_service = StudyService()
    result = study_service.run_study(study_config)

    logger.info(f"\n{'=' * 40}")
    logger.info("RESULTS SUMMARY")
    logger.info(f"{'=' * 40}")
    logger.info(f"Total simulations: {result.num_simulations}")
    logger.info(f"Successful: {result.successful_simulations}")
    logger.info(f"Execution time: {result.execution_time:.1f} seconds")

    if result.best_result:
        best_params = result.best_result.get("output_config", {}).get("parameter_settings", {})
        best_kpis = result.best_result.get("kpis", {})

        logger.info("\nOPTIMAL CONFIGURATION:")
        logger.info(f"Battery capacity: {best_params.get('battery.technical.capacity_nominal', 'N/A')} kWh")
        logger.info(f"Solar capacity: {best_params.get('solar_pv.technical.capacity_nominal', 'N/A')} kW")
        logger.info(f"Total cost: ${best_kpis.get('total_cost', 'N/A'):,.0f}")
        logger.info(f"Renewable fraction: {best_kpis.get('renewable_fraction', 0) * 100:.1f}%")

    # Create a simple visualization of the results
    if result.all_results:
        logger.info("\nPARAMETER SPACE EXPLORATION:")
        logger.info(f"{'Battery (kWh)':<15} {'Solar (kW)':<12} {'Cost ($)':<12} {'Renewable %':<12}")
        logger.info("-" * 51)

        for sim_result in result.all_results[:10]:  # Show first 10
            if sim_result.get("status") in ["optimal", "feasible"]:
                params = sim_result.get("output_config", {}).get("parameter_settings", {})
                kpis = sim_result.get("kpis", {})

                battery = params.get("battery.technical.capacity_nominal", 0)
                solar = params.get("solar_pv.technical.capacity_nominal", 0)
                cost = kpis.get("total_cost", 0)
                renewable = kpis.get("renewable_fraction", 0) * 100

                logger.info(f"{battery:<15.0f} {solar:<12.0f} {cost:<12,.0f} {renewable:<12.1f}")

    return result


def main() -> None:
    """Run parametric sweep examples."""
    logger.info("EcoSystemiser Parametric Sweep Examples")
    logger.info("========================================")
    logger.info("Demonstrating the intelligent co-pilot capability")
    logger.info("for exploring energy system design spaces.\n")

    # Example 1: Single parameter sweep
    run_battery_capacity_sweep()

    # Example 2: Multi-parameter sweep
    run_multi_parameter_sweep()

    logger.info("\n" + "=" * 60)
    logger.info("PARAMETRIC SWEEP EXAMPLES COMPLETE")
    logger.info("=" * 60)
    logger.info("\nThe StudyService enables systematic exploration of design")
    logger.info("parameters to find optimal configurations automatically.")
    logger.info("\nKey capabilities demonstrated:")
    logger.info("- Single parameter sweeps (battery capacity)")
    logger.info("- Multi-parameter sweeps (battery + solar)")
    logger.info("- Parallel execution for performance")
    logger.info("- Automatic identification of optimal configurations")
    logger.info("- Parameter influence analysis")


if __name__ == "__main__":
    main()
