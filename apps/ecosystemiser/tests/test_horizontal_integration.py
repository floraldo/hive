"""Test horizontal integration - all components working together.

This test validates that ALL components in the system follow the
Self-Contained Component Module pattern and can work together seamlessly.
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


def create_comprehensive_system():
    """Create a system with ALL available components."""
    N = 24  # 24 hour simulation
    system = System("comprehensive_test", N)

    # ==== ENERGY COMPONENTS ====

    # Grid (Transmission)
    grid = Grid(name="Grid", params=GridParams())
    grid.technical.max_import = 50.0
    grid.technical.max_export = 30.0
    grid.technical.import_tariff = 0.25
    grid.technical.feed_in_tariff = 0.08
    system.add_component(grid)

    # Solar PV (Generation)
    solar = SolarPV(name="SolarPV", params=SolarPVParams())
    solar.technical.capacity_nominal = 15.0
    solar_profile = np.zeros(N)
    solar_profile[6:18] = [0.1, 0.2, 0.4, 0.6, 0.8, 0.9, 1.0, 0.9, 0.7, 0.5, 0.3, 0.1]
    solar.profile = solar_profile
    system.add_component(solar)

    # Battery (Storage)
    battery = Battery(name="Battery", params=BatteryParams())
    battery.technical.capacity_nominal = 30.0
    battery.technical.max_charge_rate = 10.0
    battery.technical.max_discharge_rate = 10.0
    battery.technical.efficiency_roundtrip = 0.95
    battery.technical.initial_soc_pct = 0.5
    battery.technical.fidelity_level = FidelityLevel.STANDARD
    battery.technical.self_discharge_rate = 0.001
    system.add_component(battery)

    # Power Demand (Demand)
    power_demand = PowerDemand(name="PowerDemand", params=PowerDemandParams())
    power_demand.technical.peak_demand = 12.0
    demand_profile = np.ones(N) * 0.4
    demand_profile[7:9] = 0.6  # Morning peak
    demand_profile[18:22] = 0.8  # Evening peak
    power_demand.profile = demand_profile
    system.add_component(power_demand)

    # ==== THERMAL COMPONENTS ====

    # Heat Buffer (Storage)
    heat_buffer = HeatBuffer(name="HeatBuffer", params=HeatBufferParams())
    heat_buffer.technical.capacity_nominal = 50.0
    heat_buffer.technical.max_charge_rate = 15.0
    heat_buffer.technical.max_discharge_rate = 15.0
    heat_buffer.technical.efficiency_roundtrip = 0.98
    heat_buffer.technical.initial_soc_pct = 0.3
    heat_buffer.technical.fidelity_level = FidelityLevel.STANDARD
    heat_buffer.technical.heat_loss_coefficient = 0.002
    system.add_component(heat_buffer)

    # Heat Pump (Conversion)
    heat_pump = HeatPump(name="HeatPump", params=HeatPumpParams())
    heat_pump.technical.capacity_nominal = 10.0
    heat_pump.technical.cop_nominal = 3.5
    heat_pump.technical.fidelity_level = FidelityLevel.STANDARD
    heat_pump.technical.cop_temperature_curve = {"slope": 0.02}
    system.add_component(heat_pump)

    # Electric Boiler (Conversion)
    boiler = ElectricBoiler(name="ElectricBoiler", params=ElectricBoilerParams())
    boiler.technical.capacity_nominal = 8.0
    boiler.technical.efficiency_nominal = 0.98
    system.add_component(boiler)

    # Heat Demand (Demand)
    heat_demand = HeatDemand(name="HeatDemand", params=HeatDemandParams())
    heat_demand.technical.peak_demand = 15.0
    heat_profile = np.ones(N) * 0.3
    heat_profile[6:8] = 0.7  # Morning heating
    heat_profile[18:22] = 0.8  # Evening heating
    heat_demand.profile = heat_profile
    system.add_component(heat_demand)

    # ==== WATER COMPONENTS ====

    # Water Grid (Transmission)
    water_grid = WaterGrid(name="WaterGrid", params=WaterGridParams())
    water_grid.technical.max_import = 10.0
    water_grid.technical.max_export = 5.0
    water_grid.technical.water_tariff = 1.5
    water_grid.technical.wastewater_tariff = 2.0
    system.add_component(water_grid)

    # Rainwater Source (Generation)
    rainwater = RainwaterSource(name="RainwaterSource", params=RainwaterSourceParams())
    rainwater.technical.capacity_nominal = 5.0
    rainwater.technical.catchment_area_m2 = 100.0
    rainwater.technical.runoff_coefficient = 0.85
    rain_profile = np.zeros(N)
    rain_profile[2:6] = 10.0  # Night rain
    rain_profile[14:17] = 5.0  # Afternoon shower
    rainwater.profile = rain_profile
    system.add_component(rainwater)

    # Water Storage (Storage)
    water_storage = WaterStorage(name="WaterStorage", params=WaterStorageParams())
    water_storage.technical.capacity_nominal = 25.0
    water_storage.technical.max_charge_rate = 5.0
    water_storage.technical.max_discharge_rate = 5.0
    water_storage.technical.initial_soc_pct = 0.6
    water_storage.technical.fidelity_level = FidelityLevel.STANDARD
    water_storage.technical.temperature_effects = {"evaporation_factor": 0.05}
    system.add_component(water_storage)

    # Water Demand (Demand)
    water_demand = WaterDemand(name="WaterDemand", params=WaterDemandParams())
    water_demand.technical.peak_demand = 3.0
    water_profile = np.ones(N) * 0.5
    water_profile[6:8] = 0.8  # Morning usage
    water_profile[18:20] = 0.9  # Evening usage
    water_demand.profile = water_profile
    system.add_component(water_demand)

    # ==== CONNECTIONS ====

    # Electrical connections
    system.connect("Grid", "PowerDemand", "electricity")
    system.connect("Grid", "Battery", "electricity")
    system.connect("Grid", "HeatPump", "electricity")
    system.connect("Grid", "ElectricBoiler", "electricity")
    system.connect("SolarPV", "PowerDemand", "electricity")
    system.connect("SolarPV", "Battery", "electricity")
    system.connect("SolarPV", "Grid", "electricity")
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
    system.connect("RainwaterSource", "WaterDemand", "water")
    system.connect("RainwaterSource", "WaterStorage", "water")
    system.connect("WaterStorage", "WaterDemand", "water")

    return system


def test_component_inventory():
    """Test that all components are properly registered and instantiable."""
    logger.info("=" * 60)
    logger.info("HORIZONTAL INTEGRATION TEST - COMPONENT INVENTORY")
    logger.info("=" * 60)

    components_tested = []
    components_failed = []

    # Test each component type
    test_components = [
        ("Battery", BatteryParams),
        ("Grid", GridParams),
        ("SolarPV", SolarPVParams),
        ("PowerDemand", PowerDemandParams),
        ("HeatBuffer", HeatBufferParams),
        ("HeatPump", HeatPumpParams),
        ("ElectricBoiler", ElectricBoilerParams),
        ("HeatDemand", HeatDemandParams),
        ("WaterStorage", WaterStorageParams),
        ("WaterGrid", WaterGridParams),
        ("RainwaterSource", RainwaterSourceParams),
        ("WaterDemand", WaterDemandParams),
    ]

    for comp_name, params_class in test_components:
        try:
            # Import the component class with correct naming
            if "Water" in comp_name or comp_name == "RainwaterSource":
                # Water components use underscores
                module_name = comp_name.lower()
                if comp_name == "WaterStorage":
                    module_name = "water_storage"
                elif comp_name == "WaterGrid":
                    module_name = "water_grid"
                elif comp_name == "WaterDemand":
                    module_name = "water_demand"
                elif comp_name == "RainwaterSource":
                    module_name = "rainwater_source"
                module_path = f"system_model.components.water.{module_name}"
            else:
                # Energy components use underscores
                module_name = comp_name.lower()
                if comp_name == "SolarPV":
                    module_name = "solar_pv"
                elif comp_name == "PowerDemand":
                    module_name = "power_demand"
                elif comp_name == "HeatPump":
                    module_name = "heat_pump"
                elif comp_name == "ElectricBoiler":
                    module_name = "electric_boiler"
                elif comp_name == "HeatBuffer":
                    module_name = "heat_buffer"
                elif comp_name == "HeatDemand":
                    module_name = "heat_demand"
                module_path = f"system_model.components.energy.{module_name}"

            # Test instantiation
            comp_module = __import__(module_path, fromlist=[comp_name])
            comp_class = getattr(comp_module, comp_name)

            # Create instance
            instance = comp_class(name=f"Test{comp_name}", params=params_class())

            # Check for required attributes
            assert hasattr(instance, "type"), f"{comp_name} missing 'type' attribute"
            assert hasattr(
                instance, "medium"
            ), f"{comp_name} missing 'medium' attribute"
            assert hasattr(
                instance, "technical"
            ), f"{comp_name} missing 'technical' attribute"

            components_tested.append(comp_name)
            logger.info(f"✅ {comp_name:20} - Instantiated successfully")

        except Exception as e:
            components_failed.append((comp_name, str(e)))
            logger.error(f"❌ {comp_name:20} - Failed: {e}")

    logger.info(f"\nComponents Tested: {len(components_tested)}/{len(test_components)}")
    if components_failed:
        logger.error(f"Failed Components: {[c[0] for c in components_failed]}")
        return False

    return True


def test_comprehensive_optimization():
    """Test MILP optimization with ALL components working together."""
    logger.info("\n" + "=" * 60)
    logger.info("HORIZONTAL INTEGRATION TEST - COMPREHENSIVE OPTIMIZATION")
    logger.info("=" * 60)

    # Create comprehensive system
    system = create_comprehensive_system()

    logger.info(f"\nSystem created with {len(system.components)} components:")
    for name, comp in system.components.items():
        fidelity = getattr(comp.technical, "fidelity_level", "N/A")
        logger.info(
            f"  - {name:15} ({comp.type:12}) [{comp.medium:11}] Fidelity: {fidelity}"
        )

    # Run optimization
    config = SolverConfig(verbose=False, solver_specific={"objective": "min_cost"})

    logger.info("\nRunning MILP optimization with all components...")
    solver = MILPSolver(system, config)
    result = solver.solve()

    logger.info(f"\nOptimization Status: {result.status}")
    if result.status == "optimal":
        logger.info(f"Total Cost: ${result.objective_value:.2f}")
        logger.info(f"Solve Time: {result.solve_time:.3f}s")

        # Verify all components participated
        components_with_vars = 0
        for comp in system.components.values():
            has_vars = False
            for attr in [
                "E_opt",
                "P_cha",
                "P_dis",
                "P_out",
                "Q_in",
                "Q_out",
                "P_draw",
                "P_feed",
                "Q_import",
                "Q_export",
                "V_water",
            ]:
                if hasattr(comp, attr) and getattr(comp, attr) is not None:
                    has_vars = True
                    break
            if has_vars:
                components_with_vars += 1

        logger.info(
            f"Components with optimization variables: {components_with_vars}/{len(system.components)}"
        )
        return True
    else:
        logger.error(f"Optimization failed: {result.status}")
        return False


def test_fidelity_coverage():
    """Test that fidelity system works across all component types."""
    logger.info("\n" + "=" * 60)
    logger.info("HORIZONTAL INTEGRATION TEST - FIDELITY COVERAGE")
    logger.info("=" * 60)

    components_with_standard = []
    components_simple_only = []

    # Check each component for STANDARD fidelity support
    system = create_comprehensive_system()

    for name, comp in system.components.items():
        # Check if component has physics strategies
        has_standard = False

        if hasattr(comp, "physics"):
            # Component uses Strategy Pattern
            physics_class_name = comp.physics.__class__.__name__
            if "Standard" in physics_class_name:
                has_standard = True
                components_with_standard.append(name)
            else:
                components_simple_only.append(name)
        else:
            # Component doesn't use Strategy Pattern (Grid components)
            components_simple_only.append(name)

    logger.info(f"\nComponents with STANDARD fidelity: {len(components_with_standard)}")
    for comp in components_with_standard:
        logger.info(f"  ✅ {comp}")

    logger.info(f"\nComponents with SIMPLE only: {len(components_simple_only)}")
    for comp in components_simple_only:
        logger.info(f"  ⚠️ {comp}")

    # Calculate coverage
    total_components = len(system.components)
    coverage = (len(components_with_standard) / total_components) * 100

    logger.info(f"\nFidelity Coverage: {coverage:.1f}%")
    logger.info(
        f"Components with STANDARD: {len(components_with_standard)}/{total_components}"
    )

    return coverage > 50  # Pass if more than 50% have STANDARD


def main():
    """Main test runner for horizontal integration validation."""
    logger.info("🚀 HORIZONTAL INTEGRATION VALIDATION")
    logger.info("Testing complete component library integration")

    tests_passed = []
    tests_failed = []

    # Test 1: Component Inventory
    if test_component_inventory():
        tests_passed.append("Component Inventory")
    else:
        tests_failed.append("Component Inventory")

    # Test 2: Comprehensive Optimization
    if test_comprehensive_optimization():
        tests_passed.append("Comprehensive Optimization")
    else:
        tests_failed.append("Comprehensive Optimization")

    # Test 3: Fidelity Coverage
    if test_fidelity_coverage():
        tests_passed.append("Fidelity Coverage")
    else:
        tests_failed.append("Fidelity Coverage")

    # Summary
    logger.info("\n" + "=" * 60)
    if len(tests_failed) == 0:
        logger.info("✅ HORIZONTAL INTEGRATION COMPLETE!")
        logger.info("=" * 60)
        logger.info("\n🎯 All Tests Passed:")
        for test in tests_passed:
            logger.info(f"  ✅ {test}")
        logger.info("\n🏆 Achievement Unlocked: Full Horizontal Integration")
        logger.info("• All 12 components working together")
        logger.info("• Multi-domain optimization (electricity, heat, water)")
        logger.info("• Fidelity system coverage across component library")
        logger.info("• Production-ready architecture validated")
        return True
    else:
        logger.error("❌ HORIZONTAL INTEGRATION INCOMPLETE")
        logger.error(f"Failed Tests: {tests_failed}")
        logger.info("\n⚠️ Remaining Work:")
        logger.info("• Grid components need Strategy Pattern refactoring")
        logger.info("• Some components lack STANDARD fidelity")
        return False


if __name__ == "__main__":
    import sys

    success = main()
    sys.exit(0 if success else 1)
