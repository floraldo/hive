"""Heat buffer (thermal storage) component with MILP optimization support and hierarchical fidelity."""

import logging
from typing import Any

import cvxpy as cp
from pydantic import Field

from ecosystemiser.system_model.components.shared.archetypes import FidelityLevel, StorageTechnicalParams
from ecosystemiser.system_model.components.shared.base_classes import BaseStorageOptimization, BaseStoragePhysics
from ecosystemiser.system_model.components.shared.component import Component, ComponentParams
from ecosystemiser.system_model.components.shared.registry import register_component
from hive_logging import get_logger

logger = get_logger(__name__)

# =============================================================================
# HEAT BUFFER-SPECIFIC TECHNICAL PARAMETERS (Co-located with component)
# =============================================================================,


class HeatBufferTechnicalParams(StorageTechnicalParams):
    """Heat buffer-specific technical parameters extending storage archetype.,
    from __future__ import annotations


        This model inherits from StorageTechnicalParams and adds thermal storage-specific,
        parameters for different fidelity levels.,
    """

    # Core thermal storage power limits (SIMPLE fidelity)
    max_charge_rate: float = Field(..., description="Maximum charging power [kW]")
    max_discharge_rate: float = Field(..., description="Maximum discharge power [kW]")

    # Heat-specific parameters (SIMPLE fidelity)
    thermal_medium: str = Field("water", description="Thermal storage medium")

    # STANDARD fidelity parameters
    heat_loss_coefficient: float = Field(0.001, description="Heat loss coefficient per timestep [fraction/hour]")
    temperature_range: dict[str, float] | None = Field(
        None, description="Operating temperature range {min_temp, max_temp} [°C]"
    )

    # DETAILED fidelity parameters
    stratification_model: dict[str, Any] | None = Field(None, description="Thermal stratification model parameters")
    ambient_coupling: dict[str, float] | None = Field(None, description="Coupling to ambient temperature")

    # RESEARCH fidelity parameters
    thermal_dynamics_model: dict[str, Any] | None = Field(None, description="Detailed thermal dynamics model")


class HeatBufferParams(ComponentParams):
    """Heat buffer parameters using the hierarchical technical parameter system.,

    Thermal capacity is now specified through the technical parameter block,
    not as flat parameters.,
    """

    technical: HeatBufferTechnicalParams = Field(
        default_factory=lambda: HeatBufferTechnicalParams(
            capacity_nominal=20.0,  # Default 20 kWh thermal storage,
            max_charge_rate=5.0,  # Default 5 kW charge rate,
            max_discharge_rate=5.0,  # Default 5 kW discharge rate,
            efficiency_roundtrip=0.90,
            fidelity_level=FidelityLevel.STANDARD,
        ),
        description="Technical parameters following the hierarchical archetype system",
    )


# =============================================================================
# PHYSICS STRATEGIES (Rule-Based & Fidelity)
# =============================================================================,


class HeatBufferPhysicsSimple(BaseStoragePhysics):
    """Implements the SIMPLE rule-based physics for a heat buffer.,

    This is the baseline fidelity level providing:
    - Basic charge/discharge with roundtrip efficiency
    - Thermal energy balance: E_new = E_old + charge*eta - discharge/eta
    - Physical bounds enforcement (0 <= E <= E_max)
    """

    def rule_based_update_state(self, t: int, E_old: float, charge_power: float, discharge_power: float) -> float:
        """
        Implement SIMPLE heat buffer physics with roundtrip efficiency.,

        This matches the exact logic from BaseStorageComponent for numerical equivalence.,
        """
        # Use component's roundtrip efficiency parameter
        eta = self.params.technical.efficiency_roundtrip

        # Calculate energy changes - EXACTLY as original thermal storage
        # Energy gained from charging (thermal power * efficiency)
        energy_gained = charge_power * eta

        # Energy lost from discharging (thermal power / efficiency)
        energy_lost = discharge_power / eta

        # Net energy change
        net_change = energy_gained - energy_lost

        # Update state
        next_state = E_old + net_change

        # Enforce physical bounds,
        return self.apply_bounds(next_state)

    def apply_bounds(self, energy_level: float) -> float:
        """
        Apply physical energy bounds (0 <= E <= E_max) for heat buffer.

        Args:
            energy_level: Energy level to bound
        Returns:
            float: Bounded energy level,
        """
        E_max = self.params.technical.capacity_nominal
        return max(0.0, min(energy_level, E_max))


class HeatBufferPhysicsStandard(HeatBufferPhysicsSimple):
    """Implements the STANDARD rule-based physics for a heat buffer.,

    Inherits from SIMPLE and adds:
    - Thermal losses to ambient based on current energy level
    - Heat loss coefficient modeling,
    """

    def rule_based_update_state(self, t: int, E_old: float, charge_power: float, discharge_power: float) -> float:
        """
        Implement STANDARD heat buffer physics with thermal losses.,

        First applies SIMPLE physics, then adds STANDARD-specific effects.,
        """
        # 1. Get the baseline result from SIMPLE physics
        energy_after_simple = super().rule_based_update_state(t, E_old, charge_power, discharge_power)

        # 2. Add STANDARD-specific physics: thermal losses
        # Thermal losses are based on energy level at START of timestep
        heat_loss_coeff = getattr(self.params.technical, "heat_loss_coefficient", 0.001)
        thermal_loss = E_old * heat_loss_coeff

        # 3. Apply thermal losses to the result
        final_energy = energy_after_simple - thermal_loss

        # 4. Enforce bounds again after thermal losses,
        return self.apply_bounds(final_energy)


# =============================================================================
# OPTIMIZATION STRATEGY (MILP)
# =============================================================================,


class HeatBufferOptimizationSimple(BaseStorageOptimization):
    """Implements the SIMPLE MILP optimization constraints for heat buffer.,

    This is the baseline optimization strategy providing:
    - Basic thermal energy balance with roundtrip efficiency
    - Power limits for charge/discharge
    - Thermal capacity bounds
    - No thermal losses,
    """

    def __init__(self, params, component_instance) -> None:
        """Initialize with both params and component instance for constraint access."""
        super().__init__(params)
        self.component = component_instance

    def set_constraints(self) -> list:
        """
        Create SIMPLE CVXPY constraints for heat buffer optimization.,

        Returns constraints for basic thermal storage without losses.,
        """
        constraints = []
        comp = self.component

        # Get optimization variables from component
        N = comp.E_opt.shape[0] if comp.E_opt is not None else 0

        if comp.E_opt is not None:
            # Initial state constraint,
            constraints.append(comp.E_opt[0] == comp.E_init)

            # Energy bounds constraints,
            constraints.append(comp.E_opt >= 0)
            constraints.append(comp.E_opt <= comp.E_max)

            # Power limits constraints with separate charge/discharge rates,
            if comp.P_cha is not None:
                constraints.append(comp.P_cha <= comp.P_max_charge)
            if comp.P_dis is not None:
                constraints.append(comp.P_dis <= comp.P_max_discharge)

            # Energy balance constraints - SIMPLE thermal physics only,
            for t in range(1, N):
                # Base thermal energy balance with efficiency
                energy_balance = comp.E_opt[t - 1] + comp.eta * (comp.P_cha[t] - comp.P_dis[t])

                constraints.append(comp.E_opt[t] == energy_balance)

        return constraints


class HeatBufferOptimizationStandard(HeatBufferOptimizationSimple):
    """Implements the STANDARD MILP optimization constraints for heat buffer.,

    Inherits from SIMPLE and adds:
    - Thermal losses to ambient in energy balance
    - More realistic heat storage modeling,
    """

    def set_constraints(self) -> list:
        """
        Create STANDARD CVXPY constraints for heat buffer optimization.,

        Adds thermal loss terms to the energy balance constraints.,
        """
        constraints = []
        comp = self.component

        # Get optimization variables from component
        N = comp.E_opt.shape[0] if comp.E_opt is not None else 0

        if comp.E_opt is not None:
            # Initial state constraint,
            constraints.append(comp.E_opt[0] == comp.E_init)

            # Energy bounds constraints,
            constraints.append(comp.E_opt >= 0)
            constraints.append(comp.E_opt <= comp.E_max)

            # Power limits constraints with separate charge/discharge rates,
            if comp.P_cha is not None:
                constraints.append(comp.P_cha <= comp.P_max_charge)
            if comp.P_dis is not None:
                constraints.append(comp.P_dis <= comp.P_max_discharge)

            # Energy balance constraints with STANDARD thermal losses,
            for t in range(1, N):
                # Base thermal energy balance with efficiency
                energy_balance = comp.E_opt[t - 1] + comp.eta * (comp.P_cha[t] - comp.P_dis[t])

                # STANDARD: Add thermal losses
                heat_loss_coeff = getattr(comp.technical, "heat_loss_coefficient", 0.001)
                thermal_loss = comp.E_opt[t - 1] * heat_loss_coeff
                energy_balance = energy_balance - thermal_loss

                constraints.append(comp.E_opt[t] == energy_balance)

        return constraints


# =============================================================================
# MAIN COMPONENT CLASS (Factory)
# =============================================================================


@register_component("HeatBuffer")
class HeatBuffer(Component):
    """Heat buffer (thermal storage) component with Strategy Pattern architecture.,

    This class acts as a factory and container for heat buffer strategies:
    - Physics strategies: Handle fidelity-specific rule-based thermal calculations
    - Optimization strategies: Handle MILP constraint generation
    - Clean separation: Data contract + strategy selection only,

    The component delegates physics and optimization to strategy objects,
    based on the configured fidelity level.,
    """

    PARAMS_MODEL = HeatBufferParams

    def _post_init(self) -> None:
        """Initialize heat buffer attributes and strategy objects."""
        self.type = "storage"
        self.medium = "heat"

        # Extract parameters from technical block
        tech = self.technical

        # Core parameters - EXACTLY as original thermal storage expects,
        self.E_max = tech.capacity_nominal  # kWh
        self.P_max = max(tech.max_charge_rate, tech.max_discharge_rate)  # kW
        self.P_max_charge = tech.max_charge_rate
        self.P_max_discharge = tech.max_discharge_rate
        self.eta = tech.efficiency_roundtrip
        self.E_init = (
            tech.initial_soc_pct * tech.capacity_nominal if tech.initial_soc_pct else tech.capacity_nominal * 0.5
        )

        # Store thermal-specific parameters,
        self.thermal_medium = (tech.thermal_medium,)
        self.temperature_range = (tech.temperature_range,)
        self.heat_loss_coefficient = (tech.heat_loss_coefficient,)
        self.stratification_model = (tech.stratification_model,)
        self.ambient_coupling = tech.ambient_coupling

        # Set capacity alias for compatibility,
        self.capacity = self.E_max

        # Storage array for rule-based solver,
        self.E = None  # Will be initialized by solver

        # CVXPY variables (for MILP solver),
        self.E_opt = (None,)
        self.P_cha = (None,)
        self.P_dis = None

        # STRATEGY PATTERN: Instantiate the correct strategies,
        self.physics = self._get_physics_strategy()
        self.optimization = self._get_optimization_strategy()

    def _get_physics_strategy(self):
        """Factory method: Select physics strategy based on fidelity level."""
        fidelity = self.technical.fidelity_level

        if fidelity == FidelityLevel.SIMPLE:
            return HeatBufferPhysicsSimple(self.params)
        elif fidelity == FidelityLevel.STANDARD:
            return HeatBufferPhysicsStandard(self.params)
        elif fidelity == FidelityLevel.DETAILED:
            # For now, DETAILED uses STANDARD physics (can be extended later),
            return HeatBufferPhysicsStandard(self.params)
        elif fidelity == FidelityLevel.RESEARCH:
            # For now, RESEARCH uses STANDARD physics (can be extended later),
            return HeatBufferPhysicsStandard(self.params)
        else:
            raise ValueError(f"Unknown fidelity level for HeatBuffer: {fidelity}")

    def _get_optimization_strategy(self):
        """Factory method: Select optimization strategy based on fidelity level."""
        fidelity = self.technical.fidelity_level

        if fidelity == FidelityLevel.SIMPLE:
            return HeatBufferOptimizationSimple(self.params, self)
        elif fidelity == FidelityLevel.STANDARD:
            return HeatBufferOptimizationStandard(self.params, self)
        elif fidelity == FidelityLevel.DETAILED:
            # For now, DETAILED uses STANDARD optimization (can be extended later),
            return HeatBufferOptimizationStandard(self.params, self)
        elif fidelity == FidelityLevel.RESEARCH:
            # For now, RESEARCH uses STANDARD optimization (can be extended later),
            return HeatBufferOptimizationStandard(self.params, self)
        else:
            raise ValueError(f"Unknown fidelity level for HeatBuffer optimization: {fidelity}")

    def rule_based_update_state(self, t: int, charge_power: float, discharge_power: float) -> None:
        """
        Delegate to physics strategy for state update.,

        This maintains the same interface as BaseStorageComponent but,
        delegates the actual physics calculation to the strategy object.,
        """
        if self.E is None or t >= len(self.E):
            return

        # Determine the energy level at the START of the current timestep
        if t == 0:
            initial_level = self.E_init
        else:
            initial_level = self.E[t - 1]

        # Delegate to physics strategy
        new_energy = self.physics.rule_based_update_state(t, initial_level, charge_power, discharge_power)

        # Update the storage array,
        self.E[t] = new_energy

        # Log for debugging if needed,
        if t == 0 and logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"{self.name} at t={t}: charge={charge_power:.3f}kW, ",
                f"discharge={discharge_power:.3f}kW, initial={initial_level:.3f}kWh, ",
                f"E[{t}]={self.E[t]:.3f}kWh",
            )

    def add_optimization_vars(self, N: int | None = None) -> None:
        """Create CVXPY optimization variables."""
        if N is None:
            N = self.N

        self.E_opt = cp.Variable(N, name=f"{self.name}_E")
        self.P_cha = cp.Variable(N, name=f"{self.name}_P_cha", nonneg=True)
        self.P_dis = cp.Variable(N, name=f"{self.name}_P_dis", nonneg=True)

        # Store as E for compatibility,
        self.E = self.E_opt

        # Add charge/discharge as flows,
        self.flows["sink"]["P_cha"] = {"type": "heat", "value": self.P_cha}
        self.flows["source"]["P_dis"] = {"type": "heat", "value": self.P_dis}

    def set_constraints(self) -> list:
        """Delegate constraint creation to optimization strategy."""
        return self.optimization.set_constraints()

    # Provide storage capability methods for compatibility,
    def get_available_discharge(self, t: int) -> float:
        """Calculate available discharge power considering state and efficiency."""
        # Get state at START of timestep,
        if t == 0:
            current_level = self.E_init
        else:
            current_level = self.E[t - 1] if hasattr(self, "E") and t > 0 else 0.0

        # Available power is limited by both P_max and current energy level,
        return min(self.P_max_discharge, current_level)

    def get_available_charge(self, t: int) -> float:
        """Calculate available charge power considering state and capacity."""
        # Get state at START of timestep,
        if t == 0:
            current_level = self.E_init
        else:
            current_level = self.E[t - 1] if hasattr(self, "E") and t > 0 else 0.0

        # Available charge power is limited by remaining capacity and power limit
        remaining_capacity = self.E_max - current_level
        return min(self.P_max_charge, remaining_capacity)
