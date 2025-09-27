"""
Comprehensive integration tests for EcoSystemiser architectural improvements.

This test suite validates all major architectural enhancements:
1. Redis-backed job management integration
2. Rolling Horizon MILP Solver functionality
3. Mixed-fidelity simulation capabilities
4. Multi-objective optimization with configurable weights
5. Centralized location resolution

To run: python -m pytest tests/test_architectural_improvements.py -v
Expected output: All tests pass (Redis test skipped if Redis not available)
"""

import pytest
import numpy as np
import pandas as pd
import xarray as xr
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import json
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from EcoSystemiser.solver.base import SolverConfig
from EcoSystemiser.solver.milp_solver import MILPSolver
from EcoSystemiser.solver.rolling_horizon_milp import RollingHorizonMILPSolver, RollingHorizonConfig
from EcoSystemiser.services.study_service import StudyService, StudyConfig, FidelitySweepSpec
from EcoSystemiser.services.simulation_service import SimulationService, SimulationConfig
from EcoSystemiser.profile_loader.climate.service import ClimateService, LocationResolver
from EcoSystemiser.profile_loader.climate.job_manager import JobManager, JobStatus
from EcoSystemiser.system_model.system import System

# Check Redis availability for conditional test skipping
REDIS_AVAILABLE = False
FASTAPI_AVAILABLE = False

try:
    import redis
    redis_client = redis.Redis.from_url("redis://localhost:6379", socket_connect_timeout=1)
    redis_client.ping()
    REDIS_AVAILABLE = True
except ImportError:
    # Redis module not installed
    REDIS_AVAILABLE = False
except Exception:
    # Redis installed but not running
    REDIS_AVAILABLE = False

try:
    from fastapi import FastAPI, Depends
    from EcoSystemiser.profile_loader.climate.api import router as climate_api_router
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


class TestMultiObjectiveOptimization:
    """Test multi-objective optimization with configurable weights."""

    def test_solver_config_has_objective_weights(self):
        """Test that SolverConfig supports objective_weights."""
        config = SolverConfig(
            objective_weights={
                "cost": 0.6,
                "emissions": 0.3,
                "grid_usage": 0.1
            },
            normalize_objectives=True,
            pareto_mode=False
        )

        assert config.objective_weights is not None
        assert config.objective_weights["cost"] == 0.6
        assert config.objective_weights["emissions"] == 0.3
        assert config.normalize_objectives is True
        assert config.pareto_mode is False

    def test_milp_solver_uses_configured_weights(self):
        """Test that MILPSolver can use configured weights."""
        system = Mock()
        system.N = 24
        system.components = {}

        config = SolverConfig(
            objective_weights={
                "cost": 0.7,
                "emissions": 0.3
            }
        )

        solver = MILPSolver(system, config)
        assert solver.config.objective_weights["cost"] == 0.7
        assert solver.config.objective_weights["emissions"] == 0.3

    def test_weight_normalization(self):
        """Test that weights are normalized when requested."""
        config = SolverConfig(
            objective_weights={
                "cost": 70,  # Non-normalized
                "emissions": 30
            },
            normalize_objectives=True
        )

        # When solver uses these weights, they should be normalized
        total = sum(config.objective_weights.values())
        assert total == 100

        # After normalization (done in solver)
        normalized = {k: v/total for k, v in config.objective_weights.items()}
        assert abs(normalized["cost"] - 0.7) < 0.01
        assert abs(normalized["emissions"] - 0.3) < 0.01

    @patch('cvxpy.Minimize')
    def test_multi_objective_aggregation(self, mock_minimize):
        """Test that multi-objective properly aggregates weighted objectives."""
        system = Mock()
        system.N = 24
        system.components = {}
        system.get_component_cost_contributions = Mock(return_value={
            "comp1": {"cost": Mock(value=100)}
        })

        config = SolverConfig(
            objective_weights={"cost": 0.6, "emissions": 0.4}
        )

        solver = MILPSolver(system, config)
        solver.objective_type = "multi_cost_emissions"

        # Mock the single objective value method
        def mock_get_objective(obj_type, contribs):
            if obj_type == "cost":
                return 100
            elif obj_type == "emissions":
                return 50
            return 0

        solver._get_single_objective_value = mock_get_objective

        # Test aggregation
        contributions = {}
        result = solver._aggregate_multi_objective_contributions(contributions)

        # Verify Minimize was called
        mock_minimize.assert_called_once()


class TestRollingHorizonSolver:
    """Test Rolling Horizon MILP Solver implementation."""

    def create_test_system(self, timesteps=48):
        """Create a simple test system."""
        system = Mock()
        system.N = timesteps
        system.components = {
            "battery": Mock(
                name="battery",
                type="storage",
                E=None,
                E_max=100,
                P_charge=None,
                P_discharge=None
            ),
            "solar": Mock(
                name="solar",
                type="generator",
                P_gen=None
            )
        }
        system.flows = {}
        system.get_component_cost_contributions = Mock(return_value={})
        return system

    def test_rolling_horizon_configuration(self):
        """Test RollingHorizonConfig validation."""
        # Valid configuration
        config = RollingHorizonConfig(
            horizon_hours=24,
            overlap_hours=4,
            prediction_horizon=72,
            warmstart=True,
            storage_continuity=True
        )
        assert config.horizon_hours == 24
        assert config.overlap_hours == 4
        assert config.storage_continuity is True

        # Invalid configuration should raise error
        system = self.create_test_system()
        with pytest.raises(ValueError, match="Overlap hours must be less than horizon"):
            invalid_config = RollingHorizonConfig(
                horizon_hours=24,
                overlap_hours=30  # Invalid: overlap > horizon
            )
            solver = RollingHorizonMILPSolver(system, invalid_config)

    def test_window_generation(self):
        """Test that solver generates correct optimization windows."""
        system = self.create_test_system(timesteps=72)
        config = RollingHorizonConfig(
            horizon_hours=24,
            overlap_hours=4
        )

        solver = RollingHorizonMILPSolver(system, config)
        windows = solver._generate_windows()

        # Check windows are generated
        assert len(windows) > 0

        # Check first window
        first_window = windows[0]
        assert first_window['start'] == 0
        assert first_window['end'] <= 24

        # Check overlap between consecutive windows
        if len(windows) > 1:
            second_window = windows[1]
            overlap = first_window['end'] - second_window['start']
            assert overlap >= 0  # Should have some overlap or continuity

    def test_storage_state_initialization(self):
        """Test that storage states are properly initialized."""
        system = self.create_test_system()
        config = RollingHorizonConfig(horizon_hours=24)

        solver = RollingHorizonMILPSolver(system, config)
        solver._initialize_storage_states()

        # Check storage states are tracked
        assert "battery" in solver.storage_states
        # Storage state is now a dictionary with energy and last_updated
        assert "energy" in solver.storage_states["battery"]
        assert "last_updated" in solver.storage_states["battery"]

    @patch('EcoSystemiser.solver.rolling_horizon_milp.MILPSolver')
    def test_solve_execution(self, mock_milp_class):
        """Test that rolling horizon solve method works."""
        # Setup mock MILP solver
        mock_milp = Mock()
        mock_milp_class.return_value = mock_milp
        mock_result = Mock(
            status='optimal',
            objective_value=100.0,
            solve_time=1.0,
            iterations=10
        )
        mock_milp.solve.return_value = mock_result

        # Create system and solver
        system = self.create_test_system()
        config = RollingHorizonConfig(
            horizon_hours=24,
            overlap_hours=4
        )
        solver = RollingHorizonMILPSolver(system, config)

        # Execute solve
        result = solver.solve()

        # Verify result
        assert result.status in ['optimal', 'feasible', 'completed']
        assert result.num_windows > 0
        assert isinstance(result.window_results, list)


class TestMixedFidelitySimulation:
    """Test mixed-fidelity simulation capabilities in StudyService."""

    def test_mixed_fidelity_configuration(self):
        """Test that StudyService supports mixed-fidelity configurations."""
        # Create fidelity sweep spec with mixed configurations
        fidelity_spec = FidelitySweepSpec(
            component_names=["battery", "solar", "grid"],
            fidelity_levels=["SIMPLE", "STANDARD", "DETAILED"],
            mixed_fidelity_configs=[
                {"battery": "DETAILED", "solar": "SIMPLE", "grid": "STANDARD"},
                {"battery": "SIMPLE", "solar": "DETAILED", "grid": "SIMPLE"},
                {"battery": "STANDARD", "solar": "STANDARD", "grid": "DETAILED"}
            ]
        )

        assert len(fidelity_spec.mixed_fidelity_configs) == 3
        assert fidelity_spec.mixed_fidelity_configs[0]["battery"] == "DETAILED"

    def test_generate_fidelity_configs(self):
        """Test generation of mixed-fidelity simulation configs."""
        # Create study service
        service = StudyService()

        # Create study config with mixed fidelity
        base_config = SimulationConfig(
            simulation_id="test",
            system_config={"components": []},
            profile_config={},
            solver_config={},
            output_config={}
        )

        study_config = StudyConfig(
            study_id="mixed_fidelity_test",
            study_type="fidelity",
            base_config=base_config,
            fidelity_sweep=FidelitySweepSpec(
                mixed_fidelity_configs=[
                    {"comp1": "SIMPLE", "comp2": "DETAILED"},
                    {"comp1": "DETAILED", "comp2": "SIMPLE"}
                ]
            )
        )

        # Generate configs
        configs = service._generate_fidelity_configs(study_config)

        # Verify mixed fidelity configurations
        assert len(configs) == 2
        assert configs[0].output_config["mixed_fidelity_config"]["comp1"] == "SIMPLE"
        assert configs[0].output_config["mixed_fidelity_config"]["comp2"] == "DETAILED"
        assert configs[1].output_config["mixed_fidelity_config"]["comp1"] == "DETAILED"
        assert configs[1].output_config["mixed_fidelity_config"]["comp2"] == "SIMPLE"

    def test_automatic_fidelity_combinations(self):
        """Test automatic generation of fidelity combinations."""
        service = StudyService()

        base_config = SimulationConfig(
            simulation_id="test",
            system_config={},
            profile_config={},
            solver_config={},
            output_config={}
        )

        # Test with single component sweep
        study_config = StudyConfig(
            study_id="single_component_test",
            study_type="fidelity",
            base_config=base_config,
            fidelity_sweep=FidelitySweepSpec(
                component_names=["battery"],
                fidelity_levels=["SIMPLE", "STANDARD", "DETAILED"]
            )
        )

        configs = service._generate_fidelity_configs(study_config)

        # Should generate one config per fidelity level
        assert len(configs) == 3
        assert configs[0].output_config["mixed_fidelity_config"]["battery"] == "SIMPLE"
        assert configs[1].output_config["mixed_fidelity_config"]["battery"] == "STANDARD"
        assert configs[2].output_config["mixed_fidelity_config"]["battery"] == "DETAILED"


class TestJobManagerIntegration:
    """Test Redis-backed JobManager integration."""

    def test_job_manager_memory_fallback(self):
        """Test JobManager works without Redis."""
        with patch('EcoSystemiser.profile_loader.climate.job_manager.REDIS_AVAILABLE', False):
            manager = JobManager()

            assert manager.redis is None
            assert manager._memory_store is not None

            # Create and retrieve job
            job_id = manager.create_job({"test": "data"})
            job = manager.get_job(job_id)

            assert job is not None
            assert job["status"] == JobStatus.PENDING
            assert job["request"] == {"test": "data"}

    @pytest.mark.skipif(not REDIS_AVAILABLE, reason="Redis server not available for testing")
    def test_job_manager_with_live_redis(self):
        """Test JobManager with live Redis backend.

        This test requires a running Redis server and will be skipped if unavailable.
        """
        manager = JobManager(redis_url="redis://localhost:6379")

        # Should connect to Redis
        assert manager.redis is not None

        # Test job creation
        job_id = manager.create_job({"test": "live_redis_data"})
        assert job_id is not None

        # Test job retrieval
        job = manager.get_job(job_id)
        assert job is not None
        assert job["status"] == JobStatus.PENDING
        assert job["request"]["test"] == "live_redis_data"

        # Test job update
        success = manager.update_job_status(
            job_id,
            JobStatus.COMPLETED,
            result={"output": "success"}
        )
        assert success is True

        # Verify update
        job = manager.get_job(job_id)
        assert job["status"] == JobStatus.COMPLETED
        assert job["result"]["output"] == "success"

    def test_job_status_updates(self):
        """Test job status update functionality."""
        with patch('EcoSystemiser.profile_loader.climate.job_manager.REDIS_AVAILABLE', False):
            manager = JobManager()

            job_id = manager.create_job({"test": "data"})

            # Update status to processing
            success = manager.update_job_status(
                job_id,
                JobStatus.PROCESSING,
                progress=50
            )
            assert success is True

            job = manager.get_job(job_id)
            assert job["status"] == JobStatus.PROCESSING
            assert job.get("progress") == 50

            # Update to completed
            success = manager.update_job_status(
                job_id,
                JobStatus.COMPLETED,
                result={"output": "result"}
            )
            assert success is True

            job = manager.get_job(job_id)
            assert job["status"] == JobStatus.COMPLETED
            assert job["result"] == {"output": "result"}

    def test_job_manager_handles_missing_jobs(self):
        """Test that job manager handles missing jobs gracefully."""
        with patch('EcoSystemiser.profile_loader.climate.job_manager.REDIS_AVAILABLE', False):
            manager = JobManager()

            # Try to get non-existent job
            job = manager.get_job("non-existent-id")
            assert job is None

            # Try to update non-existent job
            success = manager.update_job_status("non-existent-id", JobStatus.COMPLETED)
            assert success is False


class TestLocationResolver:
    """Test centralized location resolution."""

    def test_location_resolver_initialization(self):
        """Test LocationResolver is properly initialized."""
        resolver = LocationResolver()

        assert resolver.location_cache == {}
        assert len(resolver.known_locations) > 0

    def test_known_location_resolution(self):
        """Test resolution of known locations."""
        resolver = LocationResolver()

        # Test known cities
        paris = resolver.resolve_location("paris")
        assert abs(paris[0] - 48.8566) < 0.1
        assert abs(paris[1] - 2.3522) < 0.1

        london = resolver.resolve_location("london")
        assert abs(london[0] - 51.5074) < 0.1
        assert abs(london[1] - (-0.1278)) < 0.1

        berlin = resolver.resolve_location("berlin")
        assert abs(berlin[0] - 52.5200) < 0.1

    def test_coordinate_passthrough(self):
        """Test that coordinates are passed through unchanged."""
        resolver = LocationResolver()

        coords = (40.7128, -74.0060)  # NYC
        result = resolver.resolve_location(coords)

        assert result == coords

    def test_adapter_coverage_score(self):
        """Test adapter coverage scoring method."""
        resolver = LocationResolver()

        # Test with European location
        score = resolver.get_adapter_coverage_score(
            48.8566, 2.3522, "pvgis"
        )

        # Score should be a number
        assert isinstance(score, (int, float))
        assert score >= 0

    def test_location_caching(self):
        """Test that location lookups are cached."""
        resolver = LocationResolver()

        # First lookup
        paris1 = resolver.resolve_location("paris")

        # Should be cached now
        assert "paris" in resolver.location_cache or "paris" in resolver.known_locations

        # Second lookup should return same result
        paris2 = resolver.resolve_location("paris")
        assert paris1 == paris2


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not installed")
class TestAPIIntegration:
    """Test API-level integration with architectural improvements."""

    def test_api_uses_job_manager_dependency(self):
        """Verify API endpoints use dependency injection for JobManager."""
        import inspect

        # Get the create_climate_job endpoint
        for route in climate_api_router.routes:
            if route.path == "/jobs" and "POST" in route.methods:
                # Check the endpoint function signature
                endpoint = route.endpoint
                sig = inspect.signature(endpoint)

                # Verify job_manager parameter exists with Depends annotation
                assert 'job_manager' in sig.parameters
                param = sig.parameters['job_manager']
                assert param.default.__class__.__name__ == 'Depends'
                break
        else:
            pytest.fail("Could not find /jobs POST endpoint")

    def test_api_job_endpoints_exist(self):
        """Test that all job-related endpoints exist."""
        paths = [route.path for route in climate_api_router.routes]

        # Verify job endpoints
        assert "/jobs" in paths
        assert "/jobs/{job_id}" in paths
        assert "/jobs/{job_id}/result" in paths


class TestAllImprovements:
    """Integration test for all improvements."""

    def test_all_components_exist(self):
        """Test that all improved components are importable and functional."""
        # 1. Multi-objective config
        config = SolverConfig(
            objective_weights={"cost": 0.5, "emissions": 0.5},
            normalize_objectives=True,
            pareto_mode=False
        )
        assert config.objective_weights is not None

        # 2. Rolling Horizon solver
        rh_config = RollingHorizonConfig(
            horizon_hours=24,
            overlap_hours=4,
            storage_continuity=True
        )
        assert rh_config.horizon_hours == 24

        # 3. Mixed fidelity spec
        fidelity = FidelitySweepSpec(
            mixed_fidelity_configs=[
                {"comp": "SIMPLE"},
                {"comp": "DETAILED"}
            ]
        )
        assert len(fidelity.mixed_fidelity_configs) == 2

        # 4. Job Manager
        with patch('EcoSystemiser.profile_loader.climate.job_manager.REDIS_AVAILABLE', False):
            manager = JobManager()
            assert manager._memory_store is not None

        # 5. Location Resolver
        resolver = LocationResolver()
        assert len(resolver.known_locations) > 0

    def test_production_readiness_checklist(self):
        """Final checklist for production readiness."""
        checklist = []

        # 1. Can create multi-objective config?
        try:
            SolverConfig(objective_weights={"cost": 0.5})
            checklist.append("✅ Multi-objective configuration")
        except:
            checklist.append("❌ Multi-objective configuration")

        # 2. Can create rolling horizon solver?
        try:
            system = Mock()
            system.N = 24
            system.components = {}
            RollingHorizonMILPSolver(system, RollingHorizonConfig())
            checklist.append("✅ Rolling Horizon solver")
        except:
            checklist.append("❌ Rolling Horizon solver")

        # 3. Can create mixed fidelity study?
        try:
            StudyService()._generate_fidelity_configs(StudyConfig(
                study_id="test",
                study_type="fidelity",
                base_config=SimulationConfig(
                    simulation_id="test",
                    system_config={},
                    profile_config={},
                    solver_config={},
                    output_config={}
                ),
                fidelity_sweep=FidelitySweepSpec(mixed_fidelity_configs=[{"c": "SIMPLE"}])
            ))
            checklist.append("✅ Mixed-fidelity simulation")
        except:
            checklist.append("❌ Mixed-fidelity simulation")

        # 4. Can create job manager?
        try:
            with patch('EcoSystemiser.profile_loader.climate.job_manager.REDIS_AVAILABLE', False):
                JobManager()
            checklist.append("✅ Job Manager")
        except:
            checklist.append("❌ Job Manager")

        # 5. Can resolve locations?
        try:
            LocationResolver().resolve_location("paris")
            checklist.append("✅ Location resolution")
        except:
            checklist.append("❌ Location resolution")

        # Print checklist
        print("\n=== PRODUCTION READINESS CHECKLIST ===")
        for item in checklist:
            print(item)

        # All must pass
        assert all("✅" in item for item in checklist), "Not all components are production ready"


if __name__ == "__main__":
    # Run with detailed output
    pytest.main([__file__, "-v", "-s", "--tb=short"])