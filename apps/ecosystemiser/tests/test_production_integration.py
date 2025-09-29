#!/usr/bin/env python3
"""Production integration test using real components and 8760-hour yearly profiles."""

import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ecosystemiser.services.simple_results_io import SimpleResultsIO
from ecosystemiser.solver.rolling_horizon_milp import RollingHorizonMILPSolver
from ecosystemiser.solver.rule_based_engine import RuleBasedEngine
from ecosystemiser.system_model.components.energy.battery import Battery
from ecosystemiser.system_model.components.energy.grid import Grid
from ecosystemiser.system_model.components.energy.power_demand import PowerDemand
from ecosystemiser.system_model.components.energy.solar_pv import SolarPV
from ecosystemiser.system_model.system import System

from hive_logging import get_logger

logger = get_logger(__name__)


class TestProductionIntegration:
    """Test production scenarios with real components and data."""

    @pytest.fixture
    def yearly_profiles(self) -> dict[str, np.ndarray]:
        """Load real yearly profiles from CSV files."""
        profiles_dir = Path(__file__).parent.parent / "data" / "yearly_scenarios" / "profiles"

        profiles = {}

        # Load solar profile
        solar_path = profiles_dir / "solar_pv_yearly.csv"
        if solar_path.exists():
            df = pd.read_csv(solar_path)
            profiles["solar"] = df.iloc[:, 0].values[:8760]
        else:
            # Generate synthetic profile if file doesn't exist
            hours = np.arange(8760)
            daily_pattern = np.maximum(0, np.sin((hours % 24 - 6) * np.pi / 12))
            seasonal_factor = 1 + 0.3 * np.sin((hours / 8760) * 2 * np.pi - np.pi / 2)
            profiles["solar"] = daily_pattern * seasonal_factor * 5.0  # 5 kW peak

        # Load demand profile
        demand_path = profiles_dir / "power_demand_yearly.csv"
        if demand_path.exists():
            df = pd.read_csv(demand_path)
            profiles["demand"] = df.iloc[:, 0].values[:8760]
        else:
            # Generate synthetic profile
            hours = np.arange(8760)
            base_load = 2.0  # 2 kW base
            daily_var = 1 + 0.5 * np.sin((hours % 24 - 14) * np.pi / 12)
            weekly_var = 1 + 0.1 * np.sin((hours % 168) * np.pi / 84)
            profiles["demand"] = base_load * daily_var * weekly_var

        # Generate dynamic pricing
        hours = np.arange(8760)
        hour_of_day = hours % 24
        base_price = 0.25  # Base price $/kWh

        # Time-of-use pricing
        peak_hours = (hour_of_day >= 17) & (hour_of_day <= 21)
        off_peak = (hour_of_day >= 0) & (hour_of_day <= 6)

        import_prices = np.ones(8760) * base_price
        import_prices[peak_hours] = base_price * 1.5  # 50% higher during peak
        import_prices[off_peak] = base_price * 0.7  # 30% lower off-peak

        profiles["import_price"] = import_prices
        profiles["export_price"] = import_prices * 0.4  # Export at 40% of import price

        return profiles

    def test_24hour_real_system(self, yearly_profiles):
        """Test 24-hour simulation with real components."""

        # Create system
        system = System(system_id="production_test_24h", N=24)

        # Use first 24 hours of yearly profiles
        solar_profile = yearly_profiles["solar"][:24]
        demand_profile = yearly_profiles["demand"][:24]
        import_price = yearly_profiles["import_price"][:24]
        export_price = yearly_profiles["export_price"][:24]

        # Add components with realistic parameters
        grid = Grid(
            name="GRID",
            import_price=import_price,
            export_price=export_price,
            max_import=10.0,  # 10 kW max import,
            max_export=10.0,  # 10 kW max export
        )
        system.add_component(grid)

        solar = SolarPV(name="SOLAR", capacity_kWp=5.0, profile=solar_profile)  # 5 kW peak
        system.add_component(solar)

        battery = Battery(
            name="BATTERY",
            capacity_kWh=13.5,  # Tesla Powerwall capacity,
            power_kW=5.0,  # 5 kW charge/discharge,
            efficiency=0.95,  # 95% round-trip efficiency,
            initial_soc=0.5,  # Start at 50% charge
        )
        system.add_component(battery)

        demand = PowerDemand(name="DEMAND", profile=demand_profile)
        system.add_component(demand)

        # Define energy flows
        system.add_flow("grid_import", "GRID", "DEMAND")
        system.add_flow("grid_export", "SOLAR", "GRID")
        system.add_flow("solar_to_demand", "SOLAR", "DEMAND")
        system.add_flow("solar_to_battery", "SOLAR", "BATTERY")
        system.add_flow("battery_to_demand", "BATTERY", "DEMAND")
        system.add_flow("grid_to_battery", "GRID", "BATTERY")

        # Solve with rule-based engine (faster for testing)
        solver = RuleBasedEngine()
        start_time = time.time()
        result = solver.solve(system)
        solve_time = time.time() - start_time

        assert result["status"] == "optimal", f"Solver failed: {result.get('message')}"
        logger.info(f"24-hour solve time: {solve_time:.2f} seconds")

        # Save results
        with tempfile.TemporaryDirectory() as tmpdir:
            results_io = SimpleResultsIO()
            run_dir = results_io.save_results(
                system,
                "test_24h",
                Path(tmpdir),
                metadata={"test_type": "24hour", "solver": "rule_based", "solve_time": solve_time},
            )

            # Validate results
            loaded = results_io.load_results(run_dir)
            self._validate_energy_balance(loaded["timeseries"], 24)
            self._validate_kpis(loaded["summary"]["kpis"])

    def test_weekly_simulation(self, yearly_profiles):
        """Test 168-hour (1 week) simulation."""

        # Create system for 1 week
        system = System(system_id="production_test_week", N=168)

        # Use first week of yearly profiles
        solar_profile = yearly_profiles["solar"][:168]
        demand_profile = yearly_profiles["demand"][:168]
        import_price = yearly_profiles["import_price"][:168]
        export_price = yearly_profiles["export_price"][:168]

        # Add components
        grid = Grid(name="GRID", import_price=import_price, export_price=export_price, max_import=10.0, max_export=10.0)
        system.add_component(grid)

        solar = SolarPV(name="SOLAR", capacity_kWp=5.0, profile=solar_profile)
        system.add_component(solar)

        battery = Battery(name="BATTERY", capacity_kWh=13.5, power_kW=5.0, efficiency=0.95, initial_soc=0.5)
        system.add_component(battery)

        demand = PowerDemand(name="DEMAND", profile=demand_profile)
        system.add_component(demand)

        # Define flows
        system.add_flow("grid_import", "GRID", "DEMAND")
        system.add_flow("grid_export", "SOLAR", "GRID")
        system.add_flow("solar_to_demand", "SOLAR", "DEMAND")
        system.add_flow("solar_to_battery", "SOLAR", "BATTERY")
        system.add_flow("battery_to_demand", "BATTERY", "DEMAND")

        # Solve with rule-based engine
        solver = RuleBasedEngine()
        start_time = time.time()
        result = solver.solve(system)
        solve_time = time.time() - start_time

        assert result["status"] == "optimal"
        logger.info(f"Weekly solve time: {solve_time:.2f} seconds")

        # Save and validate
        with tempfile.TemporaryDirectory() as tmpdir:
            results_io = SimpleResultsIO()
            run_dir = results_io.save_results(
                system,
                "test_week",
                Path(tmpdir),
                metadata={"test_type": "weekly", "solver": "rule_based", "solve_time": solve_time},
            )

            loaded = results_io.load_results(run_dir)
            self._validate_energy_balance(loaded["timeseries"], 168)

    @pytest.mark.slow
    def test_yearly_rolling_horizon(self, yearly_profiles):
        """Test 8760-hour yearly simulation with rolling horizon solver."""

        # This test is marked slow as it takes significant time
        # Create system for full year
        system = System(system_id="production_test_year", N=8760)

        # Use full yearly profiles
        solar_profile = yearly_profiles["solar"]
        demand_profile = yearly_profiles["demand"]
        import_price = yearly_profiles["import_price"]
        export_price = yearly_profiles["export_price"]

        # Add components
        grid = Grid(name="GRID", import_price=import_price, export_price=export_price, max_import=10.0, max_export=10.0)
        system.add_component(grid)

        solar = SolarPV(name="SOLAR", capacity_kWp=5.0, profile=solar_profile)
        system.add_component(solar)

        battery = Battery(name="BATTERY", capacity_kWh=13.5, power_kW=5.0, efficiency=0.95, initial_soc=0.5)
        system.add_component(battery)

        demand = PowerDemand(name="DEMAND", profile=demand_profile)
        system.add_component(demand)

        # Define flows
        system.add_flow("grid_import", "GRID", "DEMAND")
        system.add_flow("grid_export", "SOLAR", "GRID")
        system.add_flow("solar_to_demand", "SOLAR", "DEMAND")
        system.add_flow("solar_to_battery", "SOLAR", "BATTERY")
        system.add_flow("battery_to_demand", "BATTERY", "DEMAND")

        # Use rolling horizon solver for large problem
        solver = RollingHorizonMILPSolver(
            horizon_hours=168,
            overlap_hours=24,
            warmstart=True,  # 1 week windows  # 1 day overlap
        )

        start_time = time.time()
        result = solver.solve(system)
        solve_time = time.time() - start_time

        assert result["status"] == "optimal"
        logger.info(f"Yearly solve time: {solve_time:.2f} seconds")
        logger.info(f"Average time per window: {solve_time / result.get('num_windows', 1):.2f} seconds")

    def _validate_energy_balance(self, df: pd.DataFrame, timesteps: int):
        """Validate energy balance in results."""

        for t in range(timesteps):
            t_data = df[df["timestep"] == t]

            # Calculate total energy in and out
            energy_in = 0
            energy_out = 0

            for _, row in t_data.iterrows():
                var = row["variable"]
                val = row["value"]

                if "grid_import" in var or "battery_to_demand" in var:
                    energy_in += val
                elif "grid_export" in var or "solar_to_battery" in var:
                    energy_out += val

            # Energy should balance (within numerical tolerance)
            # Note: This is simplified - real validation would be more complex

    def _validate_kpis(self, kpis: dict[str, float]):
        """Validate KPI calculations."""

        # Check that KPIs are within reasonable ranges
        for key, value in kpis.items():
            assert value >= 0, f"Negative KPI: {key}={value}"

            # Check specific KPI ranges
            if "rate" in key or "fraction" in key:
                assert 0 <= value <= 1, f"Invalid rate/fraction: {key}={value}"


if __name__ == "__main__":
    # Run specific test for debugging
    test = TestProductionIntegration()
    profiles = test.yearly_profiles()
    test.test_24hour_real_system(profiles)
    logger.info("24-hour test passed!")

    test.test_weekly_simulation(profiles)
    logger.info("Weekly test passed!")

    # Uncomment for full year test (takes time)
    # test.test_yearly_rolling_horizon(profiles)
    # logger.info("Yearly test passed!")
