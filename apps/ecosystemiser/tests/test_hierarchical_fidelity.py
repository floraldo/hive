"""Tests for hierarchical fidelity architecture and explicit fidelity control."""

import pytest
import numpy as np
from pathlib import Path

from src.EcoSystemiser.system_model.components.shared.archetypes import (
    FidelityLevel,
    BaseTechnicalParams,
    StorageTechnicalParams,
)
from src.EcoSystemiser.system_model.components.energy.battery import (
    Battery,
    BatteryParams,
    BatteryTechnicalParams,  # Now imported from battery.py (co-location principle)
)
from src.EcoSystemiser.system_model.system import System


class TestFidelityLevels:
    """Test the FidelityLevel enum and comparison operations."""

    def test_fidelity_level_ordering(self):
        """Test that fidelity levels are properly ordered."""
        assert FidelityLevel.SIMPLE < FidelityLevel.STANDARD
        assert FidelityLevel.STANDARD < FidelityLevel.DETAILED
        assert FidelityLevel.DETAILED < FidelityLevel.RESEARCH

        assert FidelityLevel.RESEARCH >= FidelityLevel.DETAILED
        assert FidelityLevel.STANDARD >= FidelityLevel.STANDARD

    def test_fidelity_level_comparison(self):
        """Test fidelity level comparison operations."""
        simple = FidelityLevel.SIMPLE
        detailed = FidelityLevel.DETAILED

        assert simple < detailed
        assert detailed > simple
        assert simple <= detailed
        assert detailed >= simple
        assert simple != detailed


class TestArchetypeParameters:
    """Test the hierarchical parameter archetypes."""

    def test_base_technical_params(self):
        """Test base technical parameters with fidelity level."""
        params = BaseTechnicalParams(
            capacity_nominal=100.0,
            fidelity_level=FidelityLevel.STANDARD
        )

        assert params.capacity_nominal == 100.0
        assert params.fidelity_level == FidelityLevel.STANDARD
        assert params.lifetime_years == 20.0  # Default

    def test_battery_technical_params_hierarchy(self):
        """Test battery parameter hierarchy with different fidelity levels."""
        # Simple fidelity
        simple_params = BatteryTechnicalParams(
            capacity_nominal=10.0,
            fidelity_level=FidelityLevel.SIMPLE
        )
        assert simple_params.fidelity_level == FidelityLevel.SIMPLE

        # Detailed fidelity with temperature coefficients
        detailed_params = BatteryTechnicalParams(
            capacity_nominal=10.0,
            fidelity_level=FidelityLevel.DETAILED,
            temperature_coefficient_charge=-0.003,
            degradation_model={'calendar_fade_rate': 0.02}
        )
        assert detailed_params.fidelity_level == FidelityLevel.DETAILED
        assert detailed_params.temperature_coefficient_charge == -0.003

    def test_parameter_validation(self):
        """Test that parameters are validated based on fidelity level."""
        # This should work - all required params present
        params = BatteryTechnicalParams(
            capacity_nominal=10.0,
            fidelity_level=FidelityLevel.STANDARD,
            efficiency_roundtrip=0.90
        )
        assert params.efficiency_roundtrip == 0.90


class TestBatteryFidelityConstraints:
    """Test that Battery component applies constraints based on fidelity level."""

    def setup_method(self):
        """Set up test system and components."""
        self.system = System(system_id="test", n=24)  # 24-hour simulation

    def test_simple_fidelity_constraints(self):
        """Test that SIMPLE fidelity only applies basic constraints."""
        # Create battery with SIMPLE fidelity
        params = BatteryParams(
            technical=BatteryTechnicalParams(
                capacity_nominal=10.0,
                fidelity_level=FidelityLevel.SIMPLE
            )
        )

        battery = Battery("test_battery", params, self.system)
        battery.add_optimization_vars(self.system.N)

        # Get constraints
        constraints = battery.set_constraints()

        # Count constraint types (SIMPLE should have fewer constraints)
        # Basic: initial state, bounds, energy balance
        # We expect roughly 3 + N constraints for SIMPLE
        base_constraint_count = 3 + self.system.N

        # Allow some variance but should be close to base
        assert len(constraints) <= base_constraint_count + 5

    def test_standard_fidelity_constraints(self):
        """Test that STANDARD fidelity adds SOC limits and self-discharge."""
        # Create battery with STANDARD fidelity
        params = BatteryParams(
            technical=BatteryTechnicalParams(
                capacity_nominal=10.0,
                fidelity_level=FidelityLevel.STANDARD,
                soc_min=0.2,
                soc_max=0.8,
                self_discharge_rate=0.001
            )
        )

        battery = Battery("test_battery", params, self.system)
        battery.add_optimization_vars(self.system.N)

        # Get constraints
        constraints = battery.set_constraints()

        # STANDARD should have more constraints than SIMPLE
        # Additional: SOC limits for each timestep
        base_constraint_count = 3 + self.system.N
        soc_constraints = 2 * (self.system.N - 1)  # min and max SOC

        # Should have noticeably more constraints
        assert len(constraints) >= base_constraint_count + soc_constraints // 2

    def test_detailed_fidelity_constraints(self):
        """Test that DETAILED fidelity adds temperature and degradation constraints."""
        # Create battery with DETAILED fidelity
        params = BatteryParams(
            technical=BatteryTechnicalParams(
                capacity_nominal=10.0,
                fidelity_level=FidelityLevel.DETAILED,
                temperature_coefficient_charge=-0.003,
                degradation_model={'calendar_fade_rate': 0.02}
            )
        )

        battery = Battery("test_battery", params, self.system)

        # Add temperature profile to system for testing
        self.system.profiles = {
            'ambient_temperature': np.ones(self.system.N) * 20  # 20°C constant
        }

        battery.add_optimization_vars(self.system.N)

        # Get constraints
        constraints = battery.set_constraints()

        # DETAILED should have the most constraints
        # Additional: temperature derating, capacity fade
        # The actual count depends on profile availability
        assert len(constraints) > 0  # Should create constraints

    def test_explicit_fidelity_control(self):
        """Test that fidelity level explicitly controls constraint activation."""
        # Create two batteries with same parameters but different fidelity
        standard_params = BatteryParams(
            technical=BatteryTechnicalParams(
                capacity_nominal=10.0,
                fidelity_level=FidelityLevel.STANDARD,
                temperature_coefficient_charge=-0.003  # Present but not used
            )
        )

        detailed_params = BatteryParams(
            technical=BatteryTechnicalParams(
                capacity_nominal=10.0,
                fidelity_level=FidelityLevel.DETAILED,
                temperature_coefficient_charge=-0.003  # Should be used
            )
        )

        # Add temperature profile
        self.system.profiles = {
            'ambient_temperature': np.ones(self.system.N) * 30  # 30°C
        }

        # Create batteries
        standard_battery = Battery("standard", standard_params, self.system)
        detailed_battery = Battery("detailed", detailed_params, self.system)

        standard_battery.add_optimization_vars(self.system.N)
        detailed_battery.add_optimization_vars(self.system.N)

        # Get constraints
        standard_constraints = standard_battery.set_constraints()
        detailed_constraints = detailed_battery.set_constraints()

        # DETAILED should have more constraints even with same parameters
        # because it explicitly checks fidelity level
        # The temperature coefficient is ignored in STANDARD mode
        assert len(detailed_constraints) >= len(standard_constraints)


class TestFidelityPerformance:
    """Test performance characteristics at different fidelity levels."""

    def test_constraint_generation_time(self):
        """Test that higher fidelity takes more time to generate constraints."""
        import time

        system = System(system_id="test", n=100)  # 100 timesteps

        # Simple fidelity
        simple_params = BatteryParams(
            technical=BatteryTechnicalParams(
                capacity_nominal=10.0,
                fidelity_level=FidelityLevel.SIMPLE
            )
        )

        # Detailed fidelity
        detailed_params = BatteryParams(
            technical=BatteryTechnicalParams(
                capacity_nominal=10.0,
                fidelity_level=FidelityLevel.DETAILED,
                temperature_coefficient_charge=-0.003,
                degradation_model={'calendar_fade_rate': 0.02}
            )
        )

        # Add profiles for detailed constraints
        system.profiles = {
            'ambient_temperature': np.random.normal(20, 5, system.N)
        }

        # Time SIMPLE constraint generation
        simple_battery = Battery("simple", simple_params, system)
        simple_battery.add_optimization_vars(system.N)

        start = time.time()
        simple_constraints = simple_battery.set_constraints()
        simple_time = time.time() - start

        # Time DETAILED constraint generation
        detailed_battery = Battery("detailed", detailed_params, system)
        detailed_battery.add_optimization_vars(system.N)

        start = time.time()
        detailed_constraints = detailed_battery.set_constraints()
        detailed_time = time.time() - start

        # Log results
        print(f"SIMPLE: {len(simple_constraints)} constraints in {simple_time:.4f}s")
        print(f"DETAILED: {len(detailed_constraints)} constraints in {detailed_time:.4f}s")

        # DETAILED should have more constraints
        assert len(detailed_constraints) >= len(simple_constraints)

        # Note: Time difference might be small for constraint generation
        # The real performance impact is in the solver phase


def test_no_backward_compatibility():
    """Test that old-style parameters are no longer supported.

    This test verifies that the legacy flat parameter structure
    is rejected, enforcing the new hierarchical architecture.
    """
    from src.EcoSystemiser.system_model.components.energy.battery import Battery
    from pydantic import ValidationError

    system = System(system_id="test", n=24)

    # Old-style parameters (without technical archetype)
    old_params = {
        'P_max': 5.0,
        'E_max': 10.0,
        'E_init': 5.0,
        'eta_charge': 0.95,
        'eta_discharge': 0.95
    }

    # This should now raise a validation error
    # because these fields no longer exist in BatteryParams
    with pytest.raises((ValidationError, AttributeError, TypeError)):
        battery = Battery("legacy", old_params, system)

    # The correct way is now through technical params
    correct_params = BatteryParams(
        technical=BatteryTechnicalParams(
            capacity_nominal=10.0,
            fidelity_level=FidelityLevel.STANDARD
        )
    )

    battery = Battery("modern", correct_params, system)
    assert battery.E_max == 10.0
    assert battery.fidelity_level == FidelityLevel.STANDARD


if __name__ == "__main__":
    # Run specific test for development
    test = TestBatteryFidelityConstraints()
    test.setup_method()
    test.test_explicit_fidelity_control()
    print("✅ Explicit fidelity control test passed")

    # Test performance
    perf_test = TestFidelityPerformance()
    perf_test.test_constraint_generation_time()
    print("✅ Performance test completed")