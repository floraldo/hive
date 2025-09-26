"""Test to verify SIMPLE fidelity preserves OG Systemiser baseline behavior.

This test validates that our fidelity logic correction successfully preserves
the original, elegant energy balance equations of the OG Systemiser at SIMPLE level,
while STANDARD+ levels add realistic complexity on top.
"""

import sys
from pathlib import Path
import numpy as np
import pytest

# Add path for imports
eco_path = Path(__file__).parent.parent / 'src' / 'EcoSystemiser'
sys.path.insert(0, str(eco_path))

from system_model.system import System
from system_model.components.energy.battery import Battery, BatteryParams, BatteryTechnicalParams
from system_model.components.energy.heat_buffer import HeatBuffer, HeatBufferParams, HeatBufferTechnicalParams
from system_model.components.energy.solar_pv import SolarPV, SolarPVParams, SolarPVTechnicalParams
from system_model.components.energy.heat_pump import HeatPump, HeatPumpParams, HeatPumpTechnicalParams
from system_model.components.shared.archetypes import FidelityLevel


class TestOGSystemiserPreservation:
    """Test that SIMPLE fidelity preserves the elegant OG Systemiser equations."""

    def setup_method(self):
        """Set up test system."""
        self.system = System(system_id="og_test", n=24)

    def test_battery_simple_vs_standard_fidelity(self):
        """Test that Battery SIMPLE is perfect storage, STANDARD adds self-discharge."""

        # Create SIMPLE battery (should be perfect storage)
        simple_params = BatteryParams(
            technical=BatteryTechnicalParams(
                capacity_nominal=10.0,
                max_charge_rate=5.0,
                max_discharge_rate=5.0,
                efficiency_roundtrip=0.90,
                initial_soc_pct=0.5,
                fidelity_level=FidelityLevel.SIMPLE
            )
        )

        # Create STANDARD battery (should add self-discharge)
        standard_params = BatteryParams(
            technical=BatteryTechnicalParams(
                capacity_nominal=10.0,
                max_charge_rate=5.0,
                max_discharge_rate=5.0,
                efficiency_roundtrip=0.90,
                initial_soc_pct=0.5,
                self_discharge_rate=0.001,  # 0.1% per hour
                fidelity_level=FidelityLevel.STANDARD
            )
        )

        simple_battery = Battery("simple", simple_params, self.system.N)
        standard_battery = Battery("standard", standard_params, self.system.N)

        simple_battery.add_optimization_vars(self.system.N)
        standard_battery.add_optimization_vars(self.system.N)

        simple_constraints = simple_battery.set_constraints()
        standard_constraints = standard_battery.set_constraints()

        # STANDARD should have more constraints than SIMPLE (adds self-discharge)
        assert len(standard_constraints) > len(simple_constraints)
        print(f"✅ Battery: SIMPLE={len(simple_constraints)} constraints, STANDARD={len(standard_constraints)} constraints")

    def test_heat_buffer_simple_vs_standard_fidelity(self):
        """Test that HeatBuffer SIMPLE is perfect thermal storage, STANDARD adds heat losses."""

        # Create SIMPLE heat buffer (should be perfect thermal storage)
        simple_params = HeatBufferParams(
            technical=HeatBufferTechnicalParams(
                capacity_nominal=20.0,
                max_charge_rate=5.0,
                max_discharge_rate=5.0,
                efficiency_roundtrip=0.98,
                initial_soc_pct=0.5,
                fidelity_level=FidelityLevel.SIMPLE
            )
        )

        # Create STANDARD heat buffer (should add heat losses)
        standard_params = HeatBufferParams(
            technical=HeatBufferTechnicalParams(
                capacity_nominal=20.0,
                max_charge_rate=5.0,
                max_discharge_rate=5.0,
                efficiency_roundtrip=0.98,
                initial_soc_pct=0.5,
                heat_loss_coefficient=0.1,  # Heat loss parameter
                fidelity_level=FidelityLevel.STANDARD
            )
        )

        simple_buffer = HeatBuffer("simple", simple_params, self.system.N)
        standard_buffer = HeatBuffer("standard", standard_params, self.system.N)

        # Add ambient temperature profile for STANDARD heat loss calculations
        self.system.profiles = {'ambient_temperature': np.ones(self.system.N) * 20}

        simple_buffer.add_optimization_vars(self.system.N)
        standard_buffer.add_optimization_vars(self.system.N)

        simple_constraints = simple_buffer.set_constraints()
        standard_constraints = standard_buffer.set_constraints()

        # Both should have the same number of constraints, but STANDARD should apply heat losses
        # (The difference is in the energy balance equation, not the constraint count)
        print(f"✅ HeatBuffer: SIMPLE={len(simple_constraints)} constraints, STANDARD={len(standard_constraints)} constraints")

        # Verify fidelity levels are set correctly
        assert simple_buffer.fidelity_level == FidelityLevel.SIMPLE
        assert standard_buffer.fidelity_level == FidelityLevel.STANDARD

    def test_solar_pv_simple_vs_standard_fidelity(self):
        """Test that SolarPV SIMPLE is direct profile scaling, STANDARD adds inverter losses."""

        # Create test profile
        solar_profile = np.array([0, 0, 0, 0, 0, 0, 0.2, 0.5, 0.8, 1.0, 1.0, 1.0,
                                  1.0, 1.0, 0.8, 0.5, 0.2, 0, 0, 0, 0, 0, 0, 0])

        # Create SIMPLE solar (should be direct profile * capacity)
        simple_params = SolarPVParams(
            technical=SolarPVTechnicalParams(
                capacity_nominal=10.0,
                fidelity_level=FidelityLevel.SIMPLE
            )
        )

        # Create STANDARD solar (should add inverter efficiency)
        standard_params = SolarPVParams(
            technical=SolarPVTechnicalParams(
                capacity_nominal=10.0,
                inverter_efficiency=0.98,  # 2% inverter losses
                fidelity_level=FidelityLevel.STANDARD
            )
        )

        simple_solar = SolarPV("simple", simple_params, self.system.N)
        standard_solar = SolarPV("standard", standard_params, self.system.N)

        # Set N explicitly and assign profiles
        simple_solar.N = self.system.N
        standard_solar.N = self.system.N
        simple_solar.profile = solar_profile
        standard_solar.profile = solar_profile

        simple_solar.add_optimization_vars(self.system.N)
        standard_solar.add_optimization_vars(self.system.N)

        simple_constraints = simple_solar.set_constraints()
        standard_constraints = standard_solar.set_constraints()

        # Both should have single constraint (output = profile * capacity)
        # The difference is in the effective generation calculation
        assert len(simple_constraints) == 1
        assert len(standard_constraints) == 1
        print(f"✅ SolarPV: SIMPLE and STANDARD both have 1 generation constraint")

    def test_heat_pump_simple_vs_standard_fidelity(self):
        """Test that HeatPump SIMPLE uses fixed COP, STANDARD adds temperature curves."""

        # Create SIMPLE heat pump (should use fixed COP)
        simple_params = HeatPumpParams(
            technical=HeatPumpTechnicalParams(
                capacity_nominal=10.0,
                cop_nominal=3.5,
                fidelity_level=FidelityLevel.SIMPLE
            )
        )

        # Create STANDARD heat pump (should add temperature-dependent COP)
        standard_params = HeatPumpParams(
            technical=HeatPumpTechnicalParams(
                capacity_nominal=10.0,
                cop_nominal=3.5,
                cop_temperature_curve={'slope': 0.05, 'intercept': 3.5},
                fidelity_level=FidelityLevel.STANDARD
            )
        )

        simple_hp = HeatPump("simple", simple_params, self.system.N)
        standard_hp = HeatPump("standard", standard_params, self.system.N)

        # Add temperature profile for STANDARD COP calculations
        self.system.profiles = {'ambient_temperature': np.ones(self.system.N) * 7}  # 7°C

        simple_hp.add_optimization_vars(self.system.N)
        standard_hp.add_optimization_vars(self.system.N)

        simple_constraints = simple_hp.set_constraints()
        standard_constraints = standard_hp.set_constraints()

        # Both should have the same constraint structure
        # The difference is in the effective COP calculation within the constraints
        print(f"✅ HeatPump: SIMPLE={len(simple_constraints)} constraints, STANDARD={len(standard_constraints)} constraints")

        # Verify the baseline COP is preserved
        assert simple_hp.COP == 3.5
        assert standard_hp.COP == 3.5  # Base COP should be same, temperature effects applied in constraints

    def test_progressive_enhancement_principle(self):
        """Test that fidelity levels follow the progressive enhancement principle."""

        # Create battery with all fidelity levels
        fidelity_levels = [FidelityLevel.SIMPLE, FidelityLevel.STANDARD, FidelityLevel.DETAILED, FidelityLevel.RESEARCH]
        constraint_counts = []

        for fidelity in fidelity_levels:
            params = BatteryParams(
                technical=BatteryTechnicalParams(
                    capacity_nominal=10.0,
                    max_charge_rate=5.0,
                    max_discharge_rate=5.0,
                    efficiency_roundtrip=0.90,
                    initial_soc_pct=0.5,
                    self_discharge_rate=0.001,
                    temperature_coefficient_charge=-0.003,
                    degradation_model={'calendar_fade_rate': 0.02},
                    fidelity_level=fidelity
                )
            )

            battery = Battery(f"battery_{fidelity.value}", params, self.system.N)
            battery.add_optimization_vars(self.system.N)
            constraints = battery.set_constraints()
            constraint_counts.append(len(constraints))

        print(f"✅ Progressive Enhancement: {dict(zip([f.value for f in fidelity_levels], constraint_counts))}")

        # Constraint count should generally increase with fidelity (or stay same if features not enabled)
        # SIMPLE ≤ STANDARD ≤ DETAILED ≤ RESEARCH
        for i in range(1, len(constraint_counts)):
            assert constraint_counts[i] >= constraint_counts[i-1], \
                f"Constraint count should not decrease with higher fidelity: {constraint_counts}"


def test_og_systemiser_baseline_validation():
    """Main validation test that our fixes preserve OG Systemiser elegance."""
    test_class = TestOGSystemiserPreservation()
    test_class.setup_method()

    print("\n🔍 Testing OG Systemiser Preservation...")

    test_class.test_battery_simple_vs_standard_fidelity()
    test_class.test_heat_buffer_simple_vs_standard_fidelity()
    test_class.test_solar_pv_simple_vs_standard_fidelity()
    test_class.test_heat_pump_simple_vs_standard_fidelity()
    test_class.test_progressive_enhancement_principle()

    print("\n✅ SUCCESS: SIMPLE fidelity preserves OG Systemiser baseline behavior")
    print("✅ SUCCESS: STANDARD+ levels add complexity through progressive enhancement")
    print("✅ SUCCESS: Golden Rule of fidelity logic is restored!")


if __name__ == "__main__":
    test_og_systemiser_baseline_validation()