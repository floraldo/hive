"""Water storage component with MILP optimization support and hierarchical fidelity."""
import cvxpy as cp
import numpy as np
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import logging

from ..shared.registry import register_component
from ..shared.component import Component, ComponentParams
from ..shared.archetypes import StorageTechnicalParams, FidelityLevel
from ..shared.base_classes import BaseStoragePhysics, BaseStorageOptimization

logger = logging.getLogger(__name__)


# =============================================================================
# WATER STORAGE-SPECIFIC TECHNICAL PARAMETERS (Co-located with component)
# =============================================================================

class WaterStorageTechnicalParams(StorageTechnicalParams):
    """Water storage-specific technical parameters extending storage archetype.

    This model inherits from StorageTechnicalParams and adds water storage-specific
    parameters for different fidelity levels.
    """
    # Water-specific parameters (in cubic meters and m³/h)
    storage_type: str = Field("tank", description="Type of water storage (tank, reservoir, cistern)")
    loss_rate_daily: float = Field(0.01, description="Daily loss rate (evaporation, leakage) [%]")
    water_quality_class: Optional[str] = Field(
        None,
        description="Water quality classification (potable, greywater, blackwater)"
    )

    # STANDARD fidelity additions
    temperature_effects: Optional[Dict[str, float]] = Field(
        None,
        description="Temperature-dependent loss rates"
    )
    mixing_model: Optional[str] = Field(
        None,
        description="Water mixing model (FIFO, LIFO, perfect_mix)"
    )

    # DETAILED fidelity parameters
    stratification_model: Optional[Dict[str, Any]] = Field(
        None,
        description="Thermal stratification in water storage"
    )
    water_quality_decay: Optional[Dict[str, float]] = Field(
        None,
        description="Water quality degradation parameters"
    )
    membrane_fouling: Optional[Dict[str, Any]] = Field(
        None,
        description="Membrane fouling model for advanced storage"
    )

    # RESEARCH fidelity parameters
    cfd_model: Optional[Dict[str, Any]] = Field(
        None,
        description="Computational fluid dynamics model parameters"
    )
    biofilm_model: Optional[Dict[str, Any]] = Field(
        None,
        description="Biofilm growth and water quality modeling"
    )


# =============================================================================
# PHYSICS STRATEGIES (Rule-Based & Fidelity)
# =============================================================================

class WaterStoragePhysicsSimple(BaseStoragePhysics):
    """Implements the SIMPLE rule-based physics for water storage.

    This is the baseline fidelity level providing:
    - Basic water balance: V_new = V_old + inflow*efficiency - outflow - losses
    - Simple daily loss rate for evaporation and leakage
    - Physical bounds enforcement (0 <= V <= V_max)
    """

    def rule_based_update_state(self, t: int, V_old: float, inflow: float, outflow: float) -> float:
        """
        Implement SIMPLE water storage physics with daily loss rate.

        Args:
            t: Current timestep
            V_old: Water volume at start of timestep (m³)
            inflow: Water inflow rate (m³/h)
            outflow: Water outflow rate (m³/h)

        Returns:
            float: New water volume after physics update (m³)
        """
        # Use component's efficiency parameter
        efficiency = self.params.technical.efficiency_roundtrip

        # Basic loss rate (convert daily to hourly)
        hourly_loss_rate = self.params.technical.loss_rate_daily / 24.0

        # Calculate volume changes
        volume_gained = inflow * efficiency
        volume_lost = outflow + (V_old * hourly_loss_rate)  # Outflow + evaporation/leakage

        # Net volume change
        net_change = volume_gained - volume_lost

        # Update state
        new_volume = V_old + net_change

        return self.apply_bounds(new_volume)


class WaterStoragePhysicsStandard(WaterStoragePhysicsSimple):
    """Implements the STANDARD rule-based physics for water storage.

    Inherits from SIMPLE and adds:
    - Temperature-dependent evaporation rates
    - Mixing model effects on loss rates
    """

    def rule_based_update_state(self, t: int, V_old: float, inflow: float, outflow: float) -> float:
        """
        Implement STANDARD water storage physics with temperature effects.

        First applies SIMPLE physics, then adds STANDARD-specific effects.
        """
        # 1. Get the baseline result from SIMPLE physics
        volume_after_simple = super().rule_based_update_state(t, V_old, inflow, outflow)

        # 2. Add STANDARD-specific physics: temperature-dependent losses
        temperature_effects = getattr(self.params.technical, 'temperature_effects', None)
        if temperature_effects:
            # Simplified temperature adjustment
            # In real implementation, would use actual ambient temperature
            temp_factor = temperature_effects.get('evaporation_factor', 0.05)
            # Assume some temperature deviation for demonstration
            temp_deviation = 5  # Assume 5°C above reference
            additional_loss_multiplier = 1 + temp_factor * temp_deviation / 10

            # Apply additional temperature-dependent loss
            additional_loss = V_old * (self.params.technical.loss_rate_daily / 24.0) * (additional_loss_multiplier - 1)
            volume_after_standard = volume_after_simple - additional_loss

            return self.apply_bounds(volume_after_standard)

        return volume_after_simple


# =============================================================================
# OPTIMIZATION STRATEGY (MILP)
# =============================================================================

class WaterStorageOptimizationSimple(BaseStorageOptimization):
    """Implements the SIMPLE MILP optimization constraints for water storage.

    This is the baseline optimization strategy providing:
    - Basic water balance with fixed loss rate
    - Volume bounds and flow constraints
    - No temperature-dependent effects
    """

    def __init__(self, params, component_instance):
        """Initialize with both params and component instance for constraint access."""
        super().__init__(params)
        self.component = component_instance

    def set_constraints(self) -> list:
        """
        Create SIMPLE CVXPY constraints for water storage optimization.

        Returns constraints for basic water storage without enhanced losses.
        """
        constraints = []
        comp = self.component

        if comp.V_water is not None:
            # Core water storage constraints
            N = comp.N

            # Initial state
            constraints.append(comp.V_water[0] == comp.initial_level_m3)

            # Volume bounds
            constraints.append(comp.V_water >= comp.min_level_m3)
            constraints.append(comp.V_water <= comp.max_level_m3)

            # SIMPLE MODEL: Basic loss rate
            hourly_loss_rate = comp.technical.loss_rate_daily / 24.0

            # Water balance for each timestep
            for t in range(N):
                # Water balance equation
                constraints.append(
                    comp.V_water[t + 1] == comp.V_water[t] +
                    comp.technical.efficiency_roundtrip * comp.Q_in[t] -
                    comp.Q_out[t] -
                    comp.V_water[t] * hourly_loss_rate
                )

            # Flow constraints
            constraints.append(comp.Q_in <= comp.technical.max_charge_rate)
            constraints.append(comp.Q_out <= comp.technical.max_discharge_rate)

        return constraints


class WaterStorageOptimizationStandard(WaterStorageOptimizationSimple):
    """Implements the STANDARD MILP optimization constraints for water storage.

    Inherits from SIMPLE and adds:
    - Temperature-dependent evaporation losses
    - More realistic water storage modeling
    """

    def set_constraints(self) -> list:
        """
        Create STANDARD CVXPY constraints for water storage optimization.

        Adds temperature-dependent losses to the constraints.
        """
        constraints = []
        comp = self.component

        if comp.V_water is not None:
            # Core water storage constraints
            N = comp.N

            # Initial state
            constraints.append(comp.V_water[0] == comp.initial_level_m3)

            # Volume bounds
            constraints.append(comp.V_water >= comp.min_level_m3)
            constraints.append(comp.V_water <= comp.max_level_m3)

            # STANDARD: Enhanced loss rate with temperature effects
            hourly_loss_rate = comp.technical.loss_rate_daily / 24.0

            # Temperature-dependent losses
            temperature_effects = getattr(comp.technical, 'temperature_effects', None)
            if temperature_effects:
                # Apply temperature enhancement to evaporation
                evap_factor = temperature_effects.get('evaporation_factor', 0.05)
                # Simplified: assume 5°C above reference for demo
                temp_deviation = 5
                additional_loss_multiplier = 1 + evap_factor * temp_deviation / 10
                hourly_loss_rate = hourly_loss_rate * additional_loss_multiplier

            # Water balance for each timestep with enhanced losses
            for t in range(N):
                # Water balance equation
                constraints.append(
                    comp.V_water[t + 1] == comp.V_water[t] +
                    comp.technical.efficiency_roundtrip * comp.Q_in[t] -
                    comp.Q_out[t] -
                    comp.V_water[t] * hourly_loss_rate
                )

            # Flow constraints
            constraints.append(comp.Q_in <= comp.technical.max_charge_rate)
            constraints.append(comp.Q_out <= comp.technical.max_discharge_rate)

        return constraints


# =============================================================================
# MAIN COMPONENT CLASS (Factory)
# =============================================================================

class WaterStorageParams(ComponentParams):
    """Water storage parameters using the hierarchical technical parameter system.

    Capacity and flow rates are specified through the technical parameter block,
    following the archetype inheritance pattern. Units are in m³ and m³/h.
    """
    technical: WaterStorageTechnicalParams = Field(
        default_factory=lambda: WaterStorageTechnicalParams(
            capacity_nominal=10.0,        # Default 10 m³ storage
            max_charge_rate=2.0,          # Default 2 m³/h inflow
            max_discharge_rate=2.0,       # Default 2 m³/h outflow
            efficiency_roundtrip=0.98,    # Storage efficiency
            initial_soc_pct=0.5,          # Start at 50% full
            soc_min_pct=0.05,             # Minimum 5% (emergency reserve)
            soc_max_pct=1.0,              # Maximum 100%
            fidelity_level=FidelityLevel.STANDARD
        ),
        description="Technical parameters following the hierarchical archetype system"
    )


@register_component("WaterStorage")
class WaterStorage(Component):
    """Water storage component with Strategy Pattern architecture.

    This class acts as a factory and container for water storage strategies:
    - Physics strategies: Handle fidelity-specific rule-based storage calculations
    - Optimization strategies: Handle MILP constraint generation
    - Clean separation: Data contract + strategy selection only

    The component delegates physics and optimization to strategy objects
    based on the configured fidelity level.
    """

    PARAMS_MODEL = WaterStorageParams

    def _post_init(self):
        """Initialize water storage attributes and strategy objects."""
        self.type = "storage"
        self.medium = "water"

        # Extract parameters from technical block
        tech = self.technical

        # Core parameters - EXACTLY as water storage expects (m³, m³/h)
        self.capacity_m3 = tech.capacity_nominal
        self.V_max = tech.capacity_nominal  # Alias for compatibility
        self.max_flow_in_m3h = tech.max_charge_rate
        self.max_flow_out_m3h = tech.max_discharge_rate
        self.efficiency = tech.efficiency_roundtrip
        self.initial_level_m3 = tech.initial_soc_pct * tech.capacity_nominal
        self.min_level_m3 = tech.soc_min_pct * tech.capacity_nominal
        self.max_level_m3 = tech.soc_max_pct * tech.capacity_nominal

        # Store water storage-specific parameters
        self.storage_type = tech.storage_type
        self.loss_rate_daily = tech.loss_rate_daily
        self.water_quality_class = tech.water_quality_class
        self.temperature_effects = tech.temperature_effects
        self.mixing_model = tech.mixing_model
        self.stratification_model = tech.stratification_model
        self.water_quality_decay = tech.water_quality_decay

        # CVXPY variables (for MILP solver)
        self.V_water = None  # Water volume at each timestep
        self.Q_in = None     # Inflow rate
        self.Q_out = None    # Outflow rate

        # For rule-based operation
        if hasattr(self, 'N'):
            self.water_level = np.zeros(self.N + 1)
            self.water_level[0] = self.initial_level_m3

        # STRATEGY PATTERN: Instantiate the correct strategies
        self.physics = self._get_physics_strategy()
        self.optimization = self._get_optimization_strategy()

    def _get_physics_strategy(self):
        """Factory method: Select physics strategy based on fidelity level."""
        fidelity = self.technical.fidelity_level

        if fidelity == FidelityLevel.SIMPLE:
            return WaterStoragePhysicsSimple(self.params)
        elif fidelity == FidelityLevel.STANDARD:
            return WaterStoragePhysicsStandard(self.params)
        elif fidelity == FidelityLevel.DETAILED:
            # For now, DETAILED uses STANDARD physics (can be extended later)
            return WaterStoragePhysicsStandard(self.params)
        elif fidelity == FidelityLevel.RESEARCH:
            # For now, RESEARCH uses STANDARD physics (can be extended later)
            return WaterStoragePhysicsStandard(self.params)
        else:
            raise ValueError(f"Unknown fidelity level for WaterStorage: {fidelity}")

    def _get_optimization_strategy(self):
        """Factory method: Select optimization strategy based on fidelity level."""
        fidelity = self.technical.fidelity_level

        if fidelity == FidelityLevel.SIMPLE:
            return WaterStorageOptimizationSimple(self.params, self)
        elif fidelity == FidelityLevel.STANDARD:
            return WaterStorageOptimizationStandard(self.params, self)
        elif fidelity == FidelityLevel.DETAILED:
            # For now, DETAILED uses STANDARD optimization (can be extended later)
            return WaterStorageOptimizationStandard(self.params, self)
        elif fidelity == FidelityLevel.RESEARCH:
            # For now, RESEARCH uses STANDARD optimization (can be extended later)
            return WaterStorageOptimizationStandard(self.params, self)
        else:
            raise ValueError(f"Unknown fidelity level for WaterStorage optimization: {fidelity}")

    def rule_based_update_state(self, t: int, inflow: float, outflow: float):
        """
        Delegate to physics strategy for state update calculation.

        This maintains the same interface as BaseStorageComponent but
        delegates the actual physics calculation to the strategy object.
        """
        # Check bounds
        if t >= self.N:
            return

        # Get current water level
        current_level = self.water_level[t]

        # Delegate to physics strategy
        new_level = self.physics.rule_based_update_state(t, current_level, inflow, outflow)

        # Update state
        self.water_level[t + 1] = new_level

        # Log for debugging if needed
        if t == 0 and logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"{self.name} at t={t}: inflow={inflow:.3f}m³/h, "
                f"outflow={outflow:.3f}m³/h, level={new_level:.3f}m³"
            )

    def add_optimization_vars(self, N: Optional[int] = None):
        """Create CVXPY optimization variables."""
        if N is None:
            N = self.N

        self.V_water = cp.Variable(N + 1, name=f'{self.name}_volume', nonneg=True)
        self.Q_in = cp.Variable(N, name=f'{self.name}_inflow', nonneg=True)
        self.Q_out = cp.Variable(N, name=f'{self.name}_outflow', nonneg=True)

        # Add flows
        self.flows['sink']['Q_in'] = {
            'type': 'water',
            'value': self.Q_in
        }
        self.flows['source']['Q_out'] = {
            'type': 'water',
            'value': self.Q_out
        }

    def set_constraints(self) -> List:
        """Delegate constraint creation to optimization strategy."""
        return self.optimization.set_constraints()

    def rule_based_operation(self, water_demand: float, water_supply: float, t: int) -> tuple:
        """Rule-based water storage operation with fidelity-aware performance.

        Args:
            water_demand: Water demand at timestep t [m³/h]
            water_supply: Available water supply at timestep t [m³/h]
            t: Current timestep

        Returns:
            Tuple of (actual_outflow, actual_inflow) [m³/h]
        """
        if t >= self.N:
            return 0.0, 0.0

        # Current water level
        current_level = self.water_level[t]

        # Try to meet demand from storage
        available_water = current_level - self.min_level_m3
        max_outflow = min(self.max_flow_out_m3h, available_water)
        actual_outflow = min(water_demand, max_outflow)

        # Store excess supply
        available_capacity = self.max_level_m3 - current_level
        max_inflow = min(self.max_flow_in_m3h, available_capacity)
        actual_inflow = min(water_supply, max_inflow)

        # Use physics strategy to update state
        self.rule_based_update_state(t, actual_inflow, actual_outflow)

        return actual_outflow, actual_inflow

    def get_fill_percentage(self, timestep: int) -> float:
        """Get fill percentage at given timestep."""
        if 0 <= timestep <= self.N:
            return (self.water_level[timestep] / self.capacity_m3) * 100
        return 0.0

    def reset(self):
        """Reset component state."""
        if hasattr(self, 'water_level'):
            self.water_level[:] = 0
            self.water_level[0] = self.initial_level_m3

    def __repr__(self):
        """String representation."""
        return (f"WaterStorage(name='{self.name}', "
                f"capacity={self.capacity_m3}m³, "
                f"fidelity={self.technical.fidelity_level.value})")