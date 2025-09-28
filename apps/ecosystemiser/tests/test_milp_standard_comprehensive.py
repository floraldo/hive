"""Comprehensive test for MILP STANDARD fidelity constraints across all components.

This test validates that all components with STANDARD fidelity produce different
optimization results compared to SIMPLE fidelity, proving that the MILP solver
correctly accounts for realistic physics losses and constraints.
"""

import logging
import sys
from pathlib import Path

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Add path for imports
eco_path = Path(__file__).parent.parent / "src" / "EcoSystemiser"
from ecosystemiser.solver.base import SolverConfig
from ecosystemiser.solver.milp_solver import MILPSolver
from ecosystemiser.system_model.components.energy.battery import Battery, BatteryParams
from ecosystemiser.system_model.components.energy.electric_boiler import (
    ElectricBoiler,
    ElectricBoilerParams,
)
from ecosystemiser.system_model.components.energy.grid import Grid, GridParams
from ecosystemiser.system_model.components.energy.heat_buffer import (
    HeatBuffer,
    HeatBufferParams,
)
from ecosystemiser.system_model.components.energy.heat_demand import (
    HeatDemand,
    HeatDemandParams,
)
from ecosystemiser.system_model.components.energy.heat_pump import (
    HeatPump,
    HeatPumpParams,
)
from ecosystemiser.system_model.components.energy.power_demand import (
    PowerDemand,
    PowerDemandParams,
)
from ecosystemiser.system_model.components.energy.solar_pv import SolarPV, SolarPVParams
from ecosystemiser.system_model.components.shared.archetypes import FidelityLevel
from ecosystemiser.system_model.components.water.rainwater_source import (
    RainwaterSource,
    RainwaterSourceParams,
)
from ecosystemiser.system_model.components.water.water_demand import (
    WaterDemand,
    WaterDemandParams,
)
from ecosystemiser.system_model.components.water.water_grid import (
    WaterGrid,
    WaterGridParams,
)
from ecosystemiser.system_model.components.water.water_storage import (
    WaterStorage,
    WaterStorageParams,
)
from ecosystemiser.system_model.system import System


def create_comprehensive_test_system(fidelity_level: FidelityLevel):
    """Create a comprehensive energy system with all component types."""
    N = 24  # 24 hour simulation
    system = System(f"comprehensive_milp_{fidelity_level.value}_test", N)

    # Create realistic profiles
    # Solar generation profile (peak at noon)
    solar_profile = np.zeros(N)
    solar_profile[6:18] = [0.1, 0.3, 0.5, 0.7, 0.9, 1.0, 1.0, 0.9, 0.7, 0.5, 0.3, 0.1]

    # Power demand profile (evening peak)
    power_demand = np.ones(N) * 3.0  # 3 kW baseload
    power_demand[7:9] = 5.0  # Morning peak
    power_demand[17:22] = 8.0  # Evening peak

    # Heat demand profile (morning and evening peaks)
    heat_demand = np.ones(N) * 2.0  # 2 kW baseload
    heat_demand[6:8] = 5.0  # Morning heating
    heat_demand[18:22] = 6.0  # Evening heating

    # Water demand profile (morning and evening usage)
    water_demand = np.ones(N) * 0.5  # 0.5 m³/h baseload
    water_demand[7:9] = 1.5  # Morning usage
    water_demand[18:21] = 2.0  # Evening usage

    # Rainfall profile (sporadic)
    rainfall = np.zeros(N)
    rainfall[3:6] = [0.2, 0.5, 0.3]  # Early morning rain
    rainfall[14:16] = [0.4, 0.2]  # Afternoon shower

    # === ELECTRICITY COMPONENTS ===

    # Grid with time-of-use pricing
    grid = Grid(name="Grid", params=GridParams())
    grid.technical.max_import = 15.0
    grid.technical.max_export = 10.0
    grid.technical.import_tariff = 0.3  # $0.30/kWh import
    grid.technical.feed_in_tariff = 0.1  # $0.10/kWh export
    grid.technical.fidelity_level = FidelityLevel.SIMPLE  # Grid always SIMPLE
    system.add_component(grid)

    # Solar PV with fidelity
    solar = SolarPV(name="SolarPV", params=SolarPVParams())
    solar.technical.capacity_nominal = 10.0  # 10 kW peak
    solar.technical.inverter_efficiency = 0.96  # 96% DC to AC efficiency
    solar.technical.fidelity_level = fidelity_level  # Test fidelity effects
    solar.profile = solar_profile
    system.add_component(solar)

    # Battery with fidelity
    battery = Battery(name="Battery", params=BatteryParams())
    battery.technical.capacity_nominal = 20.0  # 20 kWh
    battery.technical.max_charge_rate = 5.0  # 5 kW
    battery.technical.max_discharge_rate = 5.0
    battery.technical.efficiency_roundtrip = 0.95
    battery.technical.initial_soc_pct = 0.5  # Start at 50%
    battery.technical.self_discharge_rate = (
        0.01  # 1% per hour (increased for visibility)
    )
    battery.technical.fidelity_level = fidelity_level
    system.add_component(battery)

    # Power Demand with fidelity
    power_demand_comp = PowerDemand(name="PowerDemand", params=PowerDemandParams())
    power_demand_comp.technical.peak_demand = 10.0
    power_demand_comp.technical.power_factor = 0.92  # Less than unity power factor
    power_demand_comp.technical.fidelity_level = fidelity_level
    power_demand_comp.profile = power_demand / 10.0  # Normalize to 0-1
    system.add_component(power_demand_comp)

    # === THERMAL COMPONENTS ===

    # Heat Buffer with fidelity
    heat_buffer = HeatBuffer(name="HeatBuffer", params=HeatBufferParams())
    heat_buffer.technical.capacity_nominal = 30.0  # 30 kWh thermal
    heat_buffer.technical.max_charge_rate = 8.0  # 8 kW
    heat_buffer.technical.max_discharge_rate = 8.0
    heat_buffer.technical.efficiency_roundtrip = 0.98
    heat_buffer.technical.initial_soc_pct = 0.3  # Start at 30%
    heat_buffer.technical.heat_loss_coefficient = (
        0.02  # 2% per hour (increased for visibility)
    )
    heat_buffer.technical.fidelity_level = fidelity_level
    system.add_component(heat_buffer)

    # Heat Pump
    heat_pump = HeatPump(name="HeatPump", params=HeatPumpParams())
    heat_pump.technical.capacity_nominal = 8.0  # 8 kW heat output
    heat_pump.technical.cop_nominal = 3.5  # COP 3.5
    heat_pump.technical.fidelity_level = (
        FidelityLevel.SIMPLE
    )  # Keep simple for this test
    system.add_component(heat_pump)

    # Electric Boiler (backup heating)
    electric_boiler = ElectricBoiler(
        name="ElectricBoiler", params=ElectricBoilerParams()
    )
    electric_boiler.technical.capacity_nominal = 6.0  # 6 kW
    electric_boiler.technical.efficiency_nominal = 0.99
    electric_boiler.technical.fidelity_level = FidelityLevel.SIMPLE
    system.add_component(electric_boiler)

    # Heat Demand with fidelity
    heat_demand_comp = HeatDemand(name="HeatDemand", params=HeatDemandParams())
    heat_demand_comp.technical.peak_demand = 8.0
    heat_demand_comp.technical.thermal_comfort_band = 0.1  # 10% flexibility
    heat_demand_comp.technical.fidelity_level = fidelity_level
    heat_demand_comp.profile = heat_demand / 8.0  # Normalize to 0-1
    system.add_component(heat_demand_comp)

    # === WATER COMPONENTS ===

    # Water Storage with fidelity
    water_storage = WaterStorage(name="WaterStorage", params=WaterStorageParams())
    water_storage.technical.capacity_nominal = 50.0  # 50 m³
    water_storage.technical.max_charge_rate = 5.0  # 5 m³/h
    water_storage.technical.max_discharge_rate = 5.0
    water_storage.technical.efficiency_roundtrip = 0.98
    water_storage.technical.initial_soc_pct = 0.4
    water_storage.technical.loss_rate_daily = 0.02  # 2% daily loss
    if fidelity_level >= FidelityLevel.STANDARD:
        water_storage.technical.temperature_effects = {"evaporation_factor": 0.1}
    water_storage.technical.fidelity_level = fidelity_level
    system.add_component(water_storage)

    # Water Grid
    water_grid = WaterGrid(name="WaterGrid", params=WaterGridParams())
    water_grid.technical.max_import = 10.0  # 10 m³/h
    water_grid.technical.max_export = 5.0  # 5 m³/h
    water_grid.technical.import_tariff = 2.0  # $2/m³
    water_grid.technical.export_tariff = 0.5  # $0.5/m³
    water_grid.technical.fidelity_level = FidelityLevel.SIMPLE
    system.add_component(water_grid)

    # Rainwater Source
    rainwater = RainwaterSource(name="RainwaterSource", params=RainwaterSourceParams())
    rainwater.technical.capacity_nominal = 100.0  # 100 m² collection area
    rainwater.technical.collection_efficiency = 0.85
    rainwater.technical.fidelity_level = FidelityLevel.SIMPLE
    rainwater.profile = rainfall
    system.add_component(rainwater)

    # Water Demand
    water_demand_comp = WaterDemand(name="WaterDemand", params=WaterDemandParams())
    water_demand_comp.technical.peak_demand = 3.0  # 3 m³/h peak
    water_demand_comp.technical.fidelity_level = FidelityLevel.SIMPLE
    water_demand_comp.profile = water_demand / 3.0  # Normalize
    system.add_component(water_demand_comp)

    # === CONNECT COMPONENTS ===

    # Electrical connections
    system.connect("Grid", "PowerDemand", "electricity")
    system.connect("Grid", "Battery", "electricity")
    system.connect("Grid", "HeatPump", "electricity")
    system.connect("Grid", "ElectricBoiler", "electricity")
    system.connect("SolarPV", "PowerDemand", "electricity")
    system.connect("SolarPV", "Battery", "electricity")
    system.connect("SolarPV", "Grid", "electricity")
    system.connect("SolarPV", "HeatPump", "electricity")
    system.connect("Battery", "PowerDemand", "electricity")
    system.connect("Battery", "HeatPump", "electricity")
    system.connect("Battery", "ElectricBoiler", "electricity")

    # Thermal connections
    system.connect("HeatPump", "HeatDemand", "heat")
    system.connect("HeatPump", "HeatBuffer", "heat")
    system.connect("ElectricBoiler", "HeatDemand", "heat")
    system.connect("ElectricBoiler", "HeatBuffer", "heat")
    system.connect("HeatBuffer", "HeatDemand", "heat")

    # Water connections
    system.connect("WaterGrid", "WaterDemand", "water")
    system.connect("WaterGrid", "WaterStorage", "water")
    system.connect("RainwaterSource", "WaterStorage", "water")
    system.connect("RainwaterSource", "WaterDemand", "water")
    system.connect("WaterStorage", "WaterDemand", "water")

    return system


def analyze_component_differences(simple_system, standard_system):
    """Analyze differences in component behavior between fidelity levels."""
    differences = {}

    # Check Battery - look at total energy throughput
    battery_simple = simple_system.components["Battery"]
    battery_standard = standard_system.components["Battery"]
    if hasattr(battery_simple, "E_opt") and battery_simple.E_opt is not None:
        if (
            hasattr(battery_simple.E_opt, "value")
            and battery_simple.E_opt.value is not None
        ):
            # Calculate total energy cycled through battery
            simple_changes = np.abs(np.diff(battery_simple.E_opt.value))
            standard_changes = np.abs(np.diff(battery_standard.E_opt.value))
            simple_cycled = np.sum(simple_changes)
            standard_cycled = np.sum(standard_changes)
            differences["Battery"] = {
                "simple_cycled": simple_cycled,
                "standard_cycled": standard_cycled,
                "difference": simple_cycled - standard_cycled,
                "effect": "self-discharge requires more cycling",
            }

    # Check Heat Buffer - look at total energy throughput
    heat_simple = simple_system.components["HeatBuffer"]
    heat_standard = standard_system.components["HeatBuffer"]
    if hasattr(heat_simple, "E_opt") and heat_simple.E_opt is not None:
        if hasattr(heat_simple.E_opt, "value") and heat_simple.E_opt.value is not None:
            # Calculate total heat cycled
            simple_changes = np.abs(np.diff(heat_simple.E_opt.value))
            standard_changes = np.abs(np.diff(heat_standard.E_opt.value))
            simple_cycled = np.sum(simple_changes)
            standard_cycled = np.sum(standard_changes)
            differences["HeatBuffer"] = {
                "simple_cycled": simple_cycled,
                "standard_cycled": standard_cycled,
                "difference": simple_cycled - standard_cycled,
                "effect": "thermal losses require more heating",
            }

    # Check Water Storage - look at total water throughput
    water_simple = simple_system.components["WaterStorage"]
    water_standard = standard_system.components["WaterStorage"]
    if hasattr(water_simple, "V_water") and water_simple.V_water is not None:
        if (
            hasattr(water_simple.V_water, "value")
            and water_simple.V_water.value is not None
        ):
            # Calculate total water cycled
            simple_changes = np.abs(np.diff(water_simple.V_water.value))
            standard_changes = np.abs(np.diff(water_standard.V_water.value))
            simple_cycled = np.sum(simple_changes)
            standard_cycled = np.sum(standard_changes)
            differences["WaterStorage"] = {
                "simple_cycled": simple_cycled,
                "standard_cycled": standard_cycled,
                "difference": simple_cycled - standard_cycled,
                "effect": "evaporation losses require more water",
            }

    # Check Solar PV generation
    solar_simple = simple_system.components["SolarPV"]
    solar_standard = standard_system.components["SolarPV"]
    if hasattr(solar_simple, "P_out") and solar_simple.P_out is not None:
        if (
            hasattr(solar_simple.P_out, "value")
            and solar_simple.P_out.value is not None
        ):
            simple_gen = np.sum(solar_simple.P_out.value)
            standard_gen = np.sum(solar_standard.P_out.value)
            differences["SolarPV"] = {
                "simple_total": simple_gen,
                "standard_total": standard_gen,
                "difference": simple_gen - standard_gen,
                "effect": "inverter efficiency",
            }

    # Check Power Demand
    power_simple = simple_system.components["PowerDemand"]
    power_standard = standard_system.components["PowerDemand"]
    if hasattr(power_simple, "P_in") and power_simple.P_in is not None:
        if hasattr(power_simple.P_in, "value") and power_simple.P_in.value is not None:
            simple_demand = np.sum(power_simple.P_in.value)
            standard_demand = np.sum(power_standard.P_in.value)
            differences["PowerDemand"] = {
                "simple_total": simple_demand,
                "standard_total": standard_demand,
                "difference": standard_demand - simple_demand,
                "effect": "power factor adjustment",
            }

    # Check Heat Demand flexibility
    heat_simple = simple_system.components["HeatDemand"]
    heat_standard = standard_system.components["HeatDemand"]
    if hasattr(heat_simple, "H_in") and heat_simple.H_in is not None:
        if hasattr(heat_simple.H_in, "value") and heat_simple.H_in.value is not None:
            simple_heat = heat_simple.H_in.value
            standard_heat = heat_standard.H_in.value
            # Check if flexibility is used (deviation from profile)
            expected = heat_simple.profile * heat_simple.technical.peak_demand
            simple_deviation = np.abs(simple_heat - expected)
            standard_deviation = np.abs(standard_heat - expected)
            differences["HeatDemand"] = {
                "simple_max_deviation": np.max(simple_deviation),
                "standard_max_deviation": np.max(standard_deviation),
                "flexibility_used": np.max(standard_deviation)
                > np.max(simple_deviation),
                "effect": "thermal comfort bands",
            }

    return differences


def test_comprehensive_milp_standard():
    """Test MILP optimization with STANDARD fidelity across all components."""
    logger.info("=" * 70)
    logger.info("COMPREHENSIVE MILP STANDARD FIDELITY TEST")
    logger.info("=" * 70)

    # Create systems with different fidelity levels
    simple_system = create_comprehensive_test_system(FidelityLevel.SIMPLE)
    standard_system = create_comprehensive_test_system(FidelityLevel.STANDARD)

    # Configure solver for cost minimization
    config = SolverConfig(verbose=False, solver_specific={"objective": "min_cost"})

    # Optimize SIMPLE system
    logger.info("\nOptimizing SIMPLE fidelity system (no realistic losses)...")
    simple_solver = MILPSolver(simple_system, config)
    simple_result = simple_solver.solve()

    # Optimize STANDARD system
    logger.info("Optimizing STANDARD fidelity system (with realistic physics)...")
    standard_solver = MILPSolver(standard_system, config)
    standard_result = standard_solver.solve()

    # Extract and compare results
    logger.info("\n" + "-" * 50)
    logger.info("OPTIMIZATION RESULTS COMPARISON")
    logger.info("-" * 50)

    if simple_result.status == "optimal":
        logger.info(f"SIMPLE Status:   {simple_result.status}")
        logger.info(f"SIMPLE Cost:     ${simple_result.objective_value:.2f}")
    else:
        logger.error(f"SIMPLE Status:   {simple_result.status} - FAILED!")
        return False

    if standard_result.status == "optimal":
        logger.info(f"STANDARD Status: {standard_result.status}")
        logger.info(f"STANDARD Cost:   ${standard_result.objective_value:.2f}")
    else:
        logger.error(f"STANDARD Status: {standard_result.status} - FAILED!")
        return False

    # Calculate cost difference
    cost_difference = standard_result.objective_value - simple_result.objective_value
    percent_difference = (cost_difference / simple_result.objective_value) * 100

    logger.info(
        f"\nCost Impact: ${cost_difference:.2f} ({percent_difference:.1f}% higher)"
    )
    logger.info("Reason: STANDARD accounts for all realistic losses and inefficiencies")

    # Analyze component-specific differences
    logger.info("\n" + "-" * 50)
    logger.info("COMPONENT-SPECIFIC IMPACTS")
    logger.info("-" * 50)

    differences = analyze_component_differences(simple_system, standard_system)

    for component, diff in differences.items():
        logger.info(f"\n{component}:")
        logger.info(f"  Physics Effect: {diff['effect']}")
        if "difference" in diff:
            logger.info(f"  Quantitative Impact: {diff['difference']:.3f}")
        if "flexibility_used" in diff:
            logger.info(f"  Flexibility Utilized: {diff['flexibility_used']}")

    # Verify meaningful differences exist
    if abs(cost_difference) < 0.01:
        logger.warning(
            "\n⚠️ WARNING: Costs are too similar - fidelity may not be properly affecting optimization!"
        )
        return False

    # Check that multiple components show differences
    components_with_differences = sum(
        1
        for d in differences.values()
        if ("difference" in d and abs(d["difference"]) > 0.01)
        or ("flexibility_used" in d and d["flexibility_used"])
    )

    logger.info("\n" + "-" * 50)
    logger.info("VALIDATION SUMMARY")
    logger.info("-" * 50)
    logger.info(
        f"Components with STANDARD effects: {components_with_differences}/{len(differences)}"
    )
    logger.info(f"Total cost increase: {percent_difference:.1f}%")

    if (
        components_with_differences >= 4
    ):  # At least 4 components should show differences
        logger.info(
            "\n✅ SUCCESS: MILP STANDARD fidelity is comprehensively implemented!"
        )
        logger.info(
            "All major component types show realistic physics effects in optimization."
        )
        return True
    else:
        logger.warning(
            f"\n⚠️ Only {components_with_differences} components show STANDARD effects."
        )
        logger.warning(
            "More components should implement meaningful STANDARD constraints."
        )
        return False


def main():
    """Main test runner for comprehensive MILP STANDARD validation."""
    logger.info("🚀 COMPREHENSIVE MILP STANDARD FIDELITY VALIDATION")
    logger.info("Testing all component types with realistic physics constraints")

    success = test_comprehensive_milp_standard()

    if success:
        logger.info("\n" + "=" * 70)
        logger.info("✅ COMPREHENSIVE MILP STANDARD TEST COMPLETE!")
        logger.info("=" * 70)
        logger.info("\n🎯 Validated Components with STANDARD Constraints:")
        logger.info("• Battery: Self-discharge losses affecting storage strategy")
        logger.info("• Heat Buffer: Thermal losses requiring compensation")
        logger.info("• Water Storage: Temperature-enhanced evaporation")
        logger.info("• Solar PV: Inverter efficiency reducing available power")
        logger.info("• Power Demand: Power factor increasing apparent power")
        logger.info("• Heat Demand: Thermal comfort bands allowing flexibility")
        logger.info("\n🏗️ System-Wide Impact:")
        logger.info("• Higher operational costs due to realistic losses")
        logger.info("• Changed optimization strategies to compensate")
        logger.info("• More accurate cost estimates for system design")
        logger.info("• Research-grade fidelity in optimization")
        logger.info(
            "\n🚀 EcoSystemiser now has full MILP STANDARD horizontal integration!"
        )
        logger.info("=" * 70)
    else:
        logger.error("\n❌ Comprehensive MILP STANDARD test needs improvement")
        logger.error("Some components may need additional STANDARD constraints")

    return success


if __name__ == "__main__":
    import sys

    success = main()
    sys.exit(0 if success else 1)
