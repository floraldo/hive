#!/usr/bin/env python3
"""Real integration tests for SimpleResultsIO - validates Single Artifact, Two Formats pattern."""

import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Add src to path for imports
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ecosystemiser.services.simple_results_io import SimpleResultsIO
from ecosystemiser.system_model.system import System
from ecosystemiser.system_model.components.energy.grid import Grid
from ecosystemiser.system_model.components.energy.power_demand import PowerDemand
from ecosystemiser.system_model.components.energy.solar_pv import SolarPV
from ecosystemiser.system_model.components.energy.battery import Battery
from ecosystemiser.solver.milp_solver import MILPSolver
from ecosystemiser.solver.rule_based_engine import RuleBasedEngine


class TestSimpleResultsIO:
    """Integration tests for SimpleResultsIO persistence pattern."""

    def test_directory_structure_created(self):
        """Test that correct directory structure is created for simulation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Create a simple system
            system = self._create_simple_system()

            # Solve it with rule-based solver (faster)
            solver = RuleBasedEngine()
            result = solver.solve(system)

            # Save results
            results_io = SimpleResultsIO()
            run_dir = results_io.save_results(
                system,
                "test_sim_001",
                output_dir
            )

            # Validate directory was created
            assert run_dir.exists(), f"Run directory not created: {run_dir}"
            assert run_dir.is_dir(), "Run path is not a directory"

            # Validate exactly two files exist
            files = list(run_dir.iterdir())
            assert len(files) == 2, f"Expected 2 files, found {len(files)}: {files}"

            # Validate file names
            file_names = {f.name for f in files}
            assert "summary.json" in file_names, "summary.json not found"
            assert "timeseries.parquet" in file_names, "timeseries.parquet not found"

    def test_summary_json_content(self):
        """Test that summary.json contains correct metadata and KPIs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Create and solve system
            system = self._create_simple_system()
            solver = RuleBasedEngine()
            result = solver.solve(system)

            # Save results
            results_io = SimpleResultsIO()
            run_dir = results_io.save_results(
                system,
                "test_sim_002",
                output_dir,
                metadata={"test_key": "test_value"}
            )

            # Load and validate summary.json
            summary_path = run_dir / "summary.json"
            with open(summary_path, 'r') as f:
                summary = json.load(f)

            # Check required fields
            assert "simulation_id" in summary
            assert "timestamp" in summary
            assert "timesteps" in summary
            assert summary["timesteps"] == 24
            assert "solver" in summary
            assert "metadata" in summary
            assert summary["metadata"]["test_key"] == "test_value"

            # Check KPIs exist
            assert "kpis" in summary
            kpis = summary["kpis"]

            # Check some KPIs have reasonable values
            assert "total_energy_flow" in kpis
            assert kpis["total_energy_flow"] > 0

            # Check statistics
            assert "statistics" in summary
            stats = summary["statistics"]
            assert "total_variables" in stats
            assert "total_datapoints" in stats
            assert stats["total_datapoints"] > 0

    def test_timeseries_parquet_content(self):
        """Test that timeseries.parquet contains correct time-series data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Create and solve system
            system = self._create_simple_system()
            solver = RuleBasedEngine()
            result = solver.solve(system)

            # Save results
            results_io = SimpleResultsIO()
            run_dir = results_io.save_results(
                system,
                "test_sim_003",
                output_dir
            )

            # Load and validate timeseries.parquet
            timeseries_path = run_dir / "timeseries.parquet"
            df = pd.read_parquet(timeseries_path)

            # Check DataFrame structure
            assert not df.empty, "Timeseries DataFrame is empty"
            assert "timestep" in df.columns
            assert "variable" in df.columns
            assert "value" in df.columns

            # Check data types (should be optimized)
            assert df["timestep"].dtype == np.uint16
            assert df["variable"].dtype.name == 'category'
            assert df["value"].dtype == np.float32

            # Check we have data for all timesteps
            unique_timesteps = df["timestep"].unique()
            assert len(unique_timesteps) == 24
            assert min(unique_timesteps) == 0
            assert max(unique_timesteps) == 23

            # Check we have flow variables
            flow_vars = df[df["variable"].str.startswith("flow.")]
            assert not flow_vars.empty, "No flow variables found"

            # Check values are non-zero
            non_zero_values = df[df["value"] != 0.0]
            assert not non_zero_values.empty, "All values are zero"

    def test_milp_solver_integration(self):
        """Test with MILP solver to ensure non-zero flows are captured."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Create system with solar and battery
            system = self._create_solar_battery_system()

            # Solve with MILP
            solver = MILPSolver()
            result = solver.solve(system)

            assert result["status"] == "optimal", f"MILP failed: {result['status']}"

            # Save results
            results_io = SimpleResultsIO()
            run_dir = results_io.save_results(
                system,
                "test_milp_sim",
                output_dir
            )

            # Load timeseries and check for non-zero flows
            df = pd.read_parquet(run_dir / "timeseries.parquet")

            # Check grid flow exists and has non-zero values
            grid_flows = df[df["variable"] == "flow.grid_import"]
            assert not grid_flows.empty, "No grid import flow found"
            assert grid_flows["value"].sum() > 0, "Grid import is all zeros"

            # Check battery state exists
            battery_states = df[df["variable"].str.contains("battery")]
            if not battery_states.empty:
                assert battery_states["value"].any(), "Battery never used"

    def test_load_results_roundtrip(self):
        """Test saving and loading results maintains data integrity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Create and solve system
            system = self._create_simple_system()
            solver = RuleBasedEngine()
            result = solver.solve(system)

            # Save results
            results_io = SimpleResultsIO()
            run_dir = results_io.save_results(
                system,
                "test_roundtrip",
                output_dir,
                metadata={"version": "1.0"}
            )

            # Load results back
            loaded = results_io.load_results(run_dir)

            # Validate loaded structure
            assert "summary" in loaded
            assert "timeseries" in loaded

            # Validate summary
            summary = loaded["summary"]
            assert summary["simulation_id"] == "test_roundtrip"
            assert summary["metadata"]["version"] == "1.0"
            assert summary["timesteps"] == 24

            # Validate timeseries
            df = loaded["timeseries"]
            assert isinstance(df, pd.DataFrame)
            assert not df.empty
            assert len(df["timestep"].unique()) == 24

    def test_multiple_simulations(self):
        """Test that multiple simulations create separate directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            system = self._create_simple_system()
            solver = RuleBasedEngine()
            results_io = SimpleResultsIO()

            run_dirs = []
            for i in range(3):
                result = solver.solve(system)
                run_dir = results_io.save_results(
                    system,
                    f"sim_{i:03d}",
                    output_dir
                )
                run_dirs.append(run_dir)

            # Check all directories exist and are unique
            assert len(run_dirs) == 3
            assert len(set(run_dirs)) == 3, "Directories are not unique"

            for run_dir in run_dirs:
                assert run_dir.exists()
                assert (run_dir / "summary.json").exists()
                assert (run_dir / "timeseries.parquet").exists()

    def test_error_handling(self):
        """Test error handling for invalid inputs."""
        results_io = SimpleResultsIO()

        # Test loading non-existent directory
        with pytest.raises(FileNotFoundError):
            results_io.load_results(Path("/non/existent/path"))

        # Test loading directory without required files
        with tempfile.TemporaryDirectory() as tmpdir:
            empty_dir = Path(tmpdir) / "empty"
            empty_dir.mkdir()

            with pytest.raises(FileNotFoundError):
                results_io.load_results(empty_dir)

    def _create_simple_system(self) -> System:
        """Create a simple test system with grid and demand."""
        system = System(system_id="test_system", N=24)

        # Add grid
        grid = Grid(
            name="GRID",
            import_price=np.ones(24) * 0.3,
            export_price=np.ones(24) * 0.1
        )
        system.add_component(grid)

        # Add demand
        demand = PowerDemand(
            name="DEMAND",
            profile=np.ones(24) * 2.0  # 2 kW constant
        )
        system.add_component(demand)

        # Add flow
        system.add_flow("grid_import", "GRID", "DEMAND")

        return system

    def _create_solar_battery_system(self) -> System:
        """Create a system with solar and battery for MILP testing."""
        system = System(system_id="solar_battery_system", N=24)

        # Add grid
        grid = Grid(
            name="GRID",
            import_price=np.ones(24) * 0.3,
            export_price=np.ones(24) * 0.1
        )
        system.add_component(grid)

        # Add solar
        solar_profile = np.array([
            0, 0, 0, 0, 0, 0.5, 1, 2, 3, 4, 4.5, 5,
            5, 4.5, 4, 3, 2, 1, 0.5, 0, 0, 0, 0, 0
        ])
        solar = SolarPV(
            name="SOLAR",
            capacity_kWp=5.0,
            profile=solar_profile
        )
        system.add_component(solar)

        # Add battery
        battery = Battery(
            name="BATTERY",
            capacity_kWh=10.0,
            power_kW=5.0,
            efficiency=0.9,
            initial_soc=0.5
        )
        system.add_component(battery)

        # Add demand
        demand = PowerDemand(
            name="DEMAND",
            profile=np.ones(24) * 2.0
        )
        system.add_component(demand)

        # Add flows
        system.add_flow("grid_import", "GRID", "DEMAND")
        system.add_flow("grid_export", "SOLAR", "GRID")
        system.add_flow("solar_to_demand", "SOLAR", "DEMAND")
        system.add_flow("solar_to_battery", "SOLAR", "BATTERY")
        system.add_flow("battery_to_demand", "BATTERY", "DEMAND")
        system.add_flow("grid_to_battery", "GRID", "BATTERY")

        return system


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])