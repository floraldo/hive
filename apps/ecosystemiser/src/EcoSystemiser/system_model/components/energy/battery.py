"""Battery storage component with MILP optimization support."""
import cvxpy as cp
import numpy as np
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from hive_logging import get_logger
from ecosystemiser.system_model.components.shared.registry import register_component
from ecosystemiser.system_model.components.shared.component import Component, ComponentParams
from ecosystemiser.system_model.components.shared.archetypes import StorageTechnicalParams, FidelityLevel
from ecosystemiser.system_model.components.shared.base_classes import BaseStoragePhysics, BaseStorageOptimization

logger = get_logger(__name__)

# =============================================================================
# BATTERY-SPECIFIC TECHNICAL PARAMETERS (Co-located with component)
# =============================================================================

class BatteryTechnicalParams(StorageTechnicalParams):
    """Battery-specific technical parameters extending storage archetype."""

    # Core battery power limits (SIMPLE fidelity)
    max_charge_rate: float = Field(..., description="Maximum charging power [kW]")
    max_discharge_rate: float = Field(..., description="Maximum discharge power [kW]")

    # STANDARD fidelity parameters
    self_discharge_rate: float = Field(0.0001, description="Self-discharge rate per timestep [fraction/hour]")

    # Battery-specific additions (DETAILED fidelity)
    temperature_coefficient_capacity: Optional[float] = Field(
        None,
        description="Temperature coefficient for capacity (%/°C)"
    )
    temperature_coefficient_charge: Optional[float] = Field(
        None,
        description="Temperature coefficient for charging (%/°C)"
    )

    # STANDARD fidelity additions
    degradation_model: Optional[Dict[str, float]] = Field(
        None,
        description="Battery degradation model parameters"
    )

    # DETAILED fidelity parameters
    voltage_curve: Optional[Dict[str, Any]] = Field(
        None,
        description="Voltage vs SOC curve for detailed modeling"
    )

    # RESEARCH fidelity parameters
    electrochemical_model: Optional[Dict[str, Any]] = Field(
        None,
        description="Detailed electrochemical model parameters"
    )

class BatteryParams(ComponentParams):
    """Battery parameters using the hierarchical technical parameter system."""
    technical: BatteryTechnicalParams = Field(
        default_factory=lambda: BatteryTechnicalParams(
            capacity_nominal=10.0,  # Default 10 kWh
            max_charge_rate=5.0,    # Default 5 kW charge
            max_discharge_rate=5.0, # Default 5 kW discharge
            efficiency_roundtrip=0.95,
            initial_soc_pct=0.5,
            fidelity_level=FidelityLevel.STANDARD
        ),
        description="Technical parameters following the hierarchical archetype system"
    )

# =============================================================================
# PHYSICS STRATEGIES (Rule-Based & Fidelity)
# =============================================================================

class BatteryPhysicsSimple(BaseStoragePhysics):
    """Implements the SIMPLE rule-based physics for a battery.

    This is the baseline fidelity level providing:
    - Basic charge/discharge with roundtrip efficiency
    - Energy balance: E_new = E_old + charge*eta - discharge/eta
    - Physical bounds enforcement (0 <= E <= E_max)
    """

    def rule_based_update_state(self, t: int, E_old: float, charge_power: float, discharge_power: float) -> float:
        """
        Implement SIMPLE battery physics with roundtrip efficiency.

        This matches the exact logic from BaseStorageComponent for numerical equivalence.
        """
        # Use component's roundtrip efficiency parameter
        eta = self.params.technical.efficiency_roundtrip

        # Calculate energy changes - EXACTLY as original Systemiser
        # Energy gained from charging (power * efficiency)
        energy_gained = charge_power * eta

        # Energy lost from discharging (power / efficiency)
        energy_lost = discharge_power / eta

        # Net energy change
        net_change = energy_gained - energy_lost

        # Update state
        next_state = E_old + net_change

        # Enforce physical bounds
        return self.apply_bounds(next_state)

    def apply_bounds(self, energy_level: float) -> float:
        """
        Apply physical energy bounds (0 <= E <= E_max).

        Args:
            energy_level: Energy level to bound

        Returns:
            float: Bounded energy level
        """
        # Get maximum capacity from params
        E_max = self.params.technical.capacity_nominal

        # Apply bounds
        return max(0.0, min(energy_level, E_max))

class BatteryPhysicsStandard(BatteryPhysicsSimple):
    """Implements the STANDARD rule-based physics for a battery.

    Inherits from SIMPLE and adds:
    - Self-discharge losses based on current energy level
    - Temperature-independent degradation modeling (future)
    """

    def rule_based_update_state(self, t: int, E_old: float, charge_power: float, discharge_power: float) -> float:
        """
        Implement STANDARD battery physics with self-discharge.

        First applies SIMPLE physics, then adds STANDARD-specific effects.
        """
        # 1. Get the baseline result from SIMPLE physics
        energy_after_simple = super().rule_based_update_state(t, E_old, charge_power, discharge_power)

        # 2. Add STANDARD-specific physics: self-discharge
        # Self-discharge is based on energy level at START of timestep
        self_discharge_rate = getattr(self.params.technical, 'self_discharge_rate', 0.0001)
        self_discharge_loss = E_old * self_discharge_rate

        # 3. Apply self-discharge to the result
        final_energy = energy_after_simple - self_discharge_loss

        # 4. Enforce bounds again after self-discharge
        return self.apply_bounds(final_energy)

# =============================================================================
# OPTIMIZATION STRATEGY (MILP)
# =============================================================================

class BatteryOptimizationSimple(BaseStorageOptimization):
    """Implements the SIMPLE MILP optimization constraints for battery.

    This is the baseline optimization strategy providing:
    - Basic energy balance with roundtrip efficiency
    - Power limits for charge/discharge
    - Energy capacity bounds
    - No losses or degradation
    """

    def __init__(self, params, component_instance):
        """Initialize with both params and component instance for constraint access."""
        super().__init__(params)
        self.component = component_instance

    def set_constraints(self) -> list:
        """
        Create SIMPLE CVXPY constraints for battery optimization.

        Returns constraints for basic battery operation without losses.
        """
        constraints = []
        comp = self.component

        # Get optimization variables from component
        N = comp.E_opt.shape[0] - 1 if comp.E_opt is not None else 0

        if comp.E_opt is not None:
            # Initial state constraint
            constraints.append(comp.E_opt[0] == comp.E_init)

            # Energy bounds constraints
            constraints.append(comp.E_opt >= 0)
            constraints.append(comp.E_opt <= comp.E_max)

            # Power limits constraints
            if comp.P_cha is not None:
                constraints.append(comp.P_cha <= comp.P_max)
            if comp.P_dis is not None:
                constraints.append(comp.P_dis <= comp.P_max)

            # Energy balance constraints - SIMPLE physics only
            for t in range(N):
                # Basic charge/discharge with efficiency
                energy_change = comp.eta * comp.P_cha[t] - comp.P_dis[t] / comp.eta

                constraints.append(
                    comp.E_opt[t + 1] == comp.E_opt[t] + energy_change
                )

        return constraints

class BatteryOptimizationStandard(BatteryOptimizationSimple):
    """Implements the STANDARD MILP optimization constraints for battery.

    Inherits from SIMPLE and adds:
    - Self-discharge losses in energy balance
    - More realistic battery modeling
    """

    def set_constraints(self) -> list:
        """
        Create STANDARD CVXPY constraints for battery optimization.

        First gets SIMPLE constraints, then modifies energy balance
        to include self-discharge losses.
        """
        constraints = []
        comp = self.component

        # Get optimization variables from component
        N = comp.E_opt.shape[0] - 1 if comp.E_opt is not None else 0

        if comp.E_opt is not None:
            # Initial state constraint
            constraints.append(comp.E_opt[0] == comp.E_init)

            # Energy bounds constraints
            constraints.append(comp.E_opt >= 0)
            constraints.append(comp.E_opt <= comp.E_max)

            # Power limits constraints
            if comp.P_cha is not None:
                constraints.append(comp.P_cha <= comp.P_max)
            if comp.P_dis is not None:
                constraints.append(comp.P_dis <= comp.P_max)

            # Energy balance constraints with STANDARD enhancements
            for t in range(N):
                # Basic charge/discharge with efficiency
                energy_change = comp.eta * comp.P_cha[t] - comp.P_dis[t] / comp.eta

                # STANDARD enhancement: add self-discharge
                self_discharge_rate = getattr(comp.technical, 'self_discharge_rate', 0.0001)
                # Self-discharge based on energy at start of timestep
                energy_change -= comp.E_opt[t] * self_discharge_rate

                constraints.append(
                    comp.E_opt[t + 1] == comp.E_opt[t] + energy_change
                )

        return constraints

# =============================================================================
# MAIN COMPONENT CLASS (Factory)
# =============================================================================

@register_component("Battery")
class Battery(Component):
    """Battery storage component with Strategy Pattern architecture.

    This class acts as a factory and container for battery strategies:
    - Physics strategies: Handle fidelity-specific rule-based calculations
    - Optimization strategies: Handle MILP constraint generation
    - Clean separation: Data contract + strategy selection only

    The component delegates physics and optimization to strategy objects
    based on the configured fidelity level.
    """

    PARAMS_MODEL = BatteryParams

    def _post_init(self):
        """Initialize battery attributes and strategy objects."""
        self.type = "storage"
        self.medium = "electricity"

        # Extract parameters from technical block
        tech = self.technical

        # Core parameters - EXACTLY as original Systemiser expects
        self.E_max = tech.capacity_nominal  # kWh
        self.P_max = max(tech.max_charge_rate, tech.max_discharge_rate)  # kW
        self.eta = tech.efficiency_roundtrip  # Single efficiency value
        self.E_init = tech.capacity_nominal * tech.initial_soc_pct

        # Storage array for rule-based solver
        self.E = None  # Will be initialized by solver

        # CVXPY variables (for MILP solver)
        self.E_opt = None
        self.P_cha = None
        self.P_dis = None

        # STRATEGY PATTERN: Instantiate the correct strategies
        self.physics = self._get_physics_strategy()
        self.optimization = self._get_optimization_strategy()

    def _get_physics_strategy(self):
        """Factory method: Select physics strategy based on fidelity level."""
        fidelity = self.technical.fidelity_level

        if fidelity == FidelityLevel.SIMPLE:
            return BatteryPhysicsSimple(self.params)
        elif fidelity == FidelityLevel.STANDARD:
            return BatteryPhysicsStandard(self.params)
        elif fidelity == FidelityLevel.DETAILED:
            # For now, DETAILED uses STANDARD physics (can be extended later)
            return BatteryPhysicsStandard(self.params)
        elif fidelity == FidelityLevel.RESEARCH:
            # For now, RESEARCH uses STANDARD physics (can be extended later)
            return BatteryPhysicsStandard(self.params)
        else:
            raise ValueError(f"Unknown fidelity level for Battery: {fidelity}")

    def _get_optimization_strategy(self):
        """Factory method: Select optimization strategy based on fidelity level."""
        fidelity = self.technical.fidelity_level

        if fidelity == FidelityLevel.SIMPLE:
            return BatteryOptimizationSimple(self.params, self)
        elif fidelity == FidelityLevel.STANDARD:
            return BatteryOptimizationStandard(self.params, self)
        elif fidelity == FidelityLevel.DETAILED:
            # For now, DETAILED uses STANDARD optimization (can be extended later)
            return BatteryOptimizationStandard(self.params, self)
        elif fidelity == FidelityLevel.RESEARCH:
            # For now, RESEARCH uses STANDARD optimization (can be extended later)
            return BatteryOptimizationStandard(self.params, self)
        else:
            raise ValueError(f"Unknown fidelity level for Battery optimization: {fidelity}")

    def rule_based_update_state(self, t: int, charge_power: float, discharge_power: float):
        """
        Delegate to physics strategy for state update.

        This maintains the same interface as BaseStorageComponent but
        delegates the actual physics calculation to the strategy object.
        """
        if self.E is None or t >= len(self.E):
            return

        # Determine the energy level at the START of the current timestep
        if t == 0:
            initial_level = self.E_init
        else:
            initial_level = self.E[t-1]

        # Delegate to physics strategy
        new_energy = self.physics.rule_based_update_state(t, initial_level, charge_power, discharge_power)

        # Update the storage array
        self.E[t] = new_energy

        # Log for debugging if needed
        if t == 0 and logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"{self.name} at t={t}: charge={charge_power:.3f}kW, "
                f"discharge={discharge_power:.3f}kW, initial={initial_level:.3f}kWh, "
                f"E[{t}]={self.E[t]:.3f}kWh"
            )

    def add_optimization_vars(self, N: int):
        """Create CVXPY optimization variables for MILP solver."""
        self.E_opt = cp.Variable(N + 1, name=f'{self.name}_energy', nonneg=True)
        self.P_cha = cp.Variable(N, name=f'{self.name}_charge', nonneg=True)
        self.P_dis = cp.Variable(N, name=f'{self.name}_discharge', nonneg=True)

        # Add flows
        self.flows['sink']['P_cha'] = {
            'type': 'electricity',
            'value': self.P_cha
        }
        self.flows['source']['P_dis'] = {
            'type': 'electricity',
            'value': self.P_dis
        }

    def set_constraints(self) -> List:
        """Delegate constraint creation to optimization strategy."""
        return self.optimization.set_constraints()

    # Provide storage capability methods for compatibility
    def get_available_discharge(self, t: int) -> float:
        """Calculate available discharge power considering state and efficiency."""
        # Get state at START of timestep
        if t == 0:
            current_level = self.E_init
        else:
            current_level = self.E[t-1] if hasattr(self, 'E') and t > 0 else 0.0

        # Available power is limited by both P_max and current energy level
        return min(self.P_max, current_level)

    def get_available_charge(self, t: int) -> float:
        """Calculate available charge power considering state and capacity."""
        # Get state at START of timestep
        if t == 0:
            current_level = self.E_init
        else:
            current_level = self.E[t-1] if hasattr(self, 'E') and t > 0 else 0.0

        # Available charge power is limited by remaining capacity and power limit
        remaining_capacity = self.E_max - current_level
        return min(self.P_max, remaining_capacity)