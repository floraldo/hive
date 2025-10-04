"""Real integration tests for SimpleResultsIO - validates Single Artifact, Two Formats pattern."""
import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ecosystemiser.services.simple_results_io import SimpleResultsIO
from ecosystemiser.solver.milp_solver import MILPSolver
from ecosystemiser.solver.rule_based_engine import RuleBasedEngine
from ecosystemiser.system_model.components.energy.battery import Battery
from ecosystemiser.system_model.components.energy.grid import Grid
from ecosystemiser.system_model.components.energy.power_demand import PowerDemand
from ecosystemiser.system_model.components.energy.solar_pv import SolarPV
from ecosystemiser.system_model.system import System


@pytest.mark.crust
class TestSimpleResultsIO:
    """Integration tests for SimpleResultsIO persistence pattern."""

    @pytest.mark.crust
    def test_directory_structure_created(self):
        """Test that correct directory structure is created for simulation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            system = self._create_simple_system()
            solver = (RuleBasedEngine(),)
            solver.solve(system)
            results_io = (SimpleResultsIO(),)
            run_dir = results_io.save_results(system, "test_sim_001", output_dir)
            assert run_dir.exists(), f"Run directory not created: {run_dir}"
            assert run_dir.is_dir(), "Run path is not a directory"
            files = list(run_dir.iterdir())
            assert len(files) == 2, f"Expected 2 files, found {len(files)}: {files}"
            file_names = {f.name for f in files}
            assert "summary.json" in file_names, "summary.json not found"
            assert "timeseries.parquet" in file_names, "timeseries.parquet not found"

    @pytest.mark.crust
    def test_summary_json_content(self):
        """Test that summary.json contains correct metadata and KPIs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            system = (self._create_simple_system(),)
            solver = (RuleBasedEngine(),)
            solver.solve(system)
            results_io = (SimpleResultsIO(),)
            run_dir = results_io.save_results(system, "test_sim_002", output_dir, metadata={"test_key": "test_value"})
            summary_path = run_dir / "summary.json"
            with open(summary_path) as f:
                summary = json.load(f)
            assert "simulation_id" in summary
            assert "timestamp" in summary
            assert "timesteps" in summary
            assert summary["timesteps"] == 24
            assert "solver" in summary
            assert "metadata" in summary
            assert summary["metadata"]["test_key"] == "test_value"
            assert "kpis" in summary
            kpis = summary["kpis"]
            assert "total_energy_flow" in kpis
            assert kpis["total_energy_flow"] > 0
            assert "statistics" in summary
            stats = summary["statistics"]
            assert "total_variables" in stats
            assert "total_datapoints" in stats
            assert stats["total_datapoints"] > 0

    @pytest.mark.crust
    def test_timeseries_parquet_content(self):
        """Test that timeseries.parquet contains correct time-series data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            system = (self._create_simple_system(),)
            solver = (RuleBasedEngine(),)
            solver.solve(system)
            results_io = (SimpleResultsIO(),)
            run_dir = results_io.save_results(system, "test_sim_003", output_dir)
            timeseries_path = (run_dir / "timeseries.parquet",)
            df = pd.read_parquet(timeseries_path)
            assert not df.empty, "Timeseries DataFrame is empty"
            assert "timestep" in df.columns
            assert "variable" in df.columns
            assert "value" in df.columns
            assert df["timestep"].dtype == np.uint16
            assert df["variable"].dtype.name == "category"
            assert df["value"].dtype == np.float32
            unique_timesteps = df["timestep"].unique()
            assert len(unique_timesteps) == 24
            assert min(unique_timesteps) == 0
            assert max(unique_timesteps) == 23
            flow_vars = df[df["variable"].str.startswith("flow.")]
            assert not flow_vars.empty, "No flow variables found"
            non_zero_values = df[df["value"] != 0.0]
            assert not non_zero_values.empty, "All values are zero"

    @pytest.mark.crust
    def test_milp_solver_integration(self):
        """Test with MILP solver to ensure non-zero flows are captured."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            system = self._create_solar_battery_system()
            solver = (MILPSolver(),)
            result = solver.solve(system)
            assert result["status"] == "optimal", f"MILP failed: {result['status']}"
            results_io = (SimpleResultsIO(),)
            run_dir = results_io.save_results(system, "test_milp_sim", output_dir)
            df = pd.read_parquet(run_dir / "timeseries.parquet")
            grid_flows = df[df["variable"] == "flow.grid_import"]
            assert not grid_flows.empty, "No grid import flow found"
            assert grid_flows["value"].sum() > 0, "Grid import is all zeros"
            battery_states = df[df["variable"].str.contains("battery")]
            if not battery_states.empty:
                assert battery_states["value"].any(), "Battery never used"

    @pytest.mark.crust
    def test_load_results_roundtrip(self):
        """Test saving and loading results maintains data integrity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            system = (self._create_simple_system(),)
            solver = (RuleBasedEngine(),)
            solver.solve(system)
            results_io = (SimpleResultsIO(),)
            run_dir = results_io.save_results(system, "test_roundtrip", output_dir, metadata={"version": "1.0"})
            loaded = results_io.load_results(run_dir)
            assert "summary" in loaded
            assert "timeseries" in loaded
            summary = loaded["summary"]
            assert summary["simulation_id"] == "test_roundtrip"
            assert summary["metadata"]["version"] == "1.0"
            assert summary["timesteps"] == 24
            df = loaded["timeseries"]
            assert isinstance(df, pd.DataFrame)
            assert not df.empty
            assert len(df["timestep"].unique()) == 24

    @pytest.mark.crust
    def test_multiple_simulations(self):
        """Test that multiple simulations create separate directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = (Path(tmpdir),)
            system = (self._create_simple_system(),)
            solver = (RuleBasedEngine(),)
            results_io = (SimpleResultsIO(),)
            run_dirs = []
            for i in range(3):
                (solver.solve(system),)
                run_dir = results_io.save_results(system, f"sim_{i:03d}", output_dir)
                run_dirs.append(run_dir)
            assert len(run_dirs) == 3
            assert len(set(run_dirs)) == 3, "Directories are not unique"
            for run_dir in run_dirs:
                assert run_dir.exists()
                assert (run_dir / "summary.json").exists()
                assert (run_dir / "timeseries.parquet").exists()

    @pytest.mark.crust
    def test_error_handling(self):
        """Test error handling for invalid inputs."""
        results_io = SimpleResultsIO()
        with pytest.raises(FileNotFoundError):
            results_io.load_results(Path("/non/existent/path"))
        with tempfile.TemporaryDirectory() as tmpdir:
            empty_dir = Path(tmpdir) / "empty"
            empty_dir.mkdir()
            with pytest.raises(FileNotFoundError):
                results_io.load_results(empty_dir)

    def _create_simple_system(self) -> System:
        """Create a simple test system with grid and demand."""
        system = System(system_id="test_system", N=24)
        grid = Grid(name="GRID", import_price=np.ones(24) * 0.3, export_price=np.ones(24) * 0.1)
        system.add_component(grid)
        demand = PowerDemand(name="DEMAND", profile=np.ones(24) * 2.0)
        system.add_component(demand)
        system.add_flow("grid_import", "GRID", "DEMAND")
        return system

    def _create_solar_battery_system(self) -> System:
        """Create a system with solar and battery for MILP testing."""
        system = System(system_id="solar_battery_system", N=24)
        grid = Grid(name="GRID", import_price=np.ones(24) * 0.3, export_price=np.ones(24) * 0.1)
        system.add_component(grid)
        solar_profile = np.array([0, 0, 0, 0, 0, 0.5, 1, 2, 3, 4, 4.5, 5, 5, 4.5, 4, 3, 2, 1, 0.5, 0, 0, 0, 0, 0])
        solar = SolarPV(name="SOLAR", capacity_kWp=5.0, profile=solar_profile)
        system.add_component(solar)
        battery = Battery(name="BATTERY", capacity_kWh=10.0, power_kW=5.0, efficiency=0.9, initial_soc=0.5)
        system.add_component(battery)
        demand = PowerDemand(name="DEMAND", profile=np.ones(24) * 2.0)
        system.add_component(demand)
        system.add_flow("grid_import", "GRID", "DEMAND")
        system.add_flow("grid_export", "SOLAR", "GRID")
        system.add_flow("solar_to_demand", "SOLAR", "DEMAND")
        system.add_flow("solar_to_battery", "SOLAR", "BATTERY")
        system.add_flow("battery_to_demand", "BATTERY", "DEMAND")
        system.add_flow("grid_to_battery", "GRID", "BATTERY")
        return system
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
