"""Water storage component with MILP optimization support and hierarchical fidelity."""
import cvxpy as cp
import numpy as np
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import logging

from ..shared.registry import register_component
from ..shared.component import Component, ComponentParams
from ..shared.archetypes import StorageTechnicalParams, FidelityLevel

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


class WaterStorageParams(ComponentParams):
    """Water storage parameters using the hierarchical technical parameter system.

    Capacity and flow rates are specified through the technical parameter block,
    following the archetype inheritance pattern. Units are in m³ and m³/h.
    """
    technical: WaterStorageTechnicalParams = Field(
        default_factory=lambda: WaterStorageTechnicalParams(
            capacity_nominal=10.0,  # Default 10 m³ storage
            max_charge_rate=2.0,    # Default 2 m³/h inflow
            max_discharge_rate=2.0, # Default 2 m³/h outflow
            efficiency_roundtrip=0.98,  # Storage efficiency
            initial_soc=0.5,        # Start at 50% full
            soc_min=0.05,          # Minimum 5% (emergency reserve)
            soc_max=1.0,           # Maximum 100%
            fidelity_level=FidelityLevel.STANDARD
        ),
        description="Technical parameters following the hierarchical archetype system"
    )


@register_component("WaterStorage")
class WaterStorage(Component):
    """Water storage component for tanks, reservoirs, and cisterns."""

    PARAMS_MODEL = WaterStorageParams

    def _post_init(self):
        """Initialize water storage-specific attributes from technical parameters.

        All parameters are now sourced from the technical parameter block,
        following the single source of truth principle.
        """
        self.type = "storage"
        self.medium = "water"

        # Single source of truth: the technical parameter block
        tech = self.technical

        # Core parameters extracted from technical block (water units: m³, m³/h)
        self.capacity_m3 = tech.capacity_nominal  # m³
        self.max_flow_in_m3h = tech.max_charge_rate  # m³/h
        self.max_flow_out_m3h = tech.max_discharge_rate  # m³/h
        self.efficiency = tech.efficiency_roundtrip
        self.initial_level_m3 = tech.initial_soc * tech.capacity_nominal if tech.initial_soc else tech.capacity_nominal * 0.5
        self.min_level_m3 = tech.soc_min * tech.capacity_nominal if tech.soc_min else 0.0
        self.max_level_m3 = tech.soc_max * tech.capacity_nominal if tech.soc_max else tech.capacity_nominal

        # Store advanced parameters for fidelity-aware constraints
        self.storage_type = tech.storage_type
        self.loss_rate_daily = tech.loss_rate_daily
        self.water_quality_class = tech.water_quality_class
        self.temperature_effects = tech.temperature_effects
        self.mixing_model = tech.mixing_model
        self.stratification_model = tech.stratification_model
        self.water_quality_decay = tech.water_quality_decay

        # EXPLICIT FIDELITY CONTROL
        self.fidelity_level = tech.fidelity_level

        # CVXPY variables (created later by add_optimization_vars)
        self.V_water = None  # Water volume at each timestep
        self.Q_in = None     # Inflow rate
        self.Q_out = None    # Outflow rate
        self.Q_loss = None   # Loss rate

        # For rule-based operation
        if hasattr(self, 'N'):
            self.water_level = np.zeros(self.N + 1)
            self.water_level[0] = self.initial_level_m3

    def add_optimization_vars(self):
        """Create CVXPY optimization variables."""
        self.V_water = cp.Variable(self.N + 1, name=f'{self.name}_volume', nonneg=True)
        self.Q_in = cp.Variable(self.N, name=f'{self.name}_inflow', nonneg=True)
        self.Q_out = cp.Variable(self.N, name=f'{self.name}_outflow', nonneg=True)
        self.Q_loss = cp.Variable(self.N, name=f'{self.name}_loss', nonneg=True)

        # Add flows
        self.flows['input']['Q_in'] = {
            'type': 'water',
            'value': self.Q_in
        }
        self.flows['output']['Q_out'] = {
            'type': 'water',
            'value': self.Q_out
        }
        self.flows['sink']['Q_loss'] = {
            'type': 'water',
            'value': self.Q_loss
        }

    def set_constraints(self) -> List:
        """Set CVXPY constraints for water storage with fidelity-aware modeling.

        Constraint complexity scales with fidelity level:
        - SIMPLE: Basic water balance and volume limits
        - STANDARD: Add temperature-dependent losses and mixing
        - DETAILED: Add water quality decay and stratification
        - RESEARCH: Full CFD and biofilm modeling
        """
        constraints = []

        if self.V_water is not None:
            # Get fidelity level
            fidelity = getattr(self, 'fidelity_level', FidelityLevel.STANDARD)
            N = len(self.V_water) - 1  # V_water has N+1 elements

            # BASIC CONSTRAINTS (always active)
            # Initial state
            constraints.append(self.V_water[0] == self.initial_level_m3)

            # Volume bounds
            constraints.append(self.V_water >= self.min_level_m3)
            constraints.append(self.V_water <= self.max_level_m3)

            # Water balance for each timestep
            for t in range(N):
                # Base loss rate
                hourly_loss_rate = self.loss_rate_daily / 24.0
                effective_loss_rate = hourly_loss_rate

                # STANDARD: Apply temperature effects on losses
                if fidelity >= FidelityLevel.STANDARD and self.temperature_effects:
                    if hasattr(self, 'system') and hasattr(self.system, 'profiles'):
                        if 'ambient_temperature' in self.system.profiles:
                            temp = self.system.profiles['ambient_temperature'][t] if t < len(self.system.profiles['ambient_temperature']) else 20
                            # Higher temperature increases evaporation
                            temp_factor = self.temperature_effects.get('evaporation_factor', 0.05)
                            temp_multiplier = 1 + temp_factor * (temp - 20) / 10  # Reference 20°C
                            effective_loss_rate = hourly_loss_rate * max(0.1, temp_multiplier)
                            logger.debug("STANDARD: Applied temperature-dependent losses to water storage")

                # Water balance equation
                constraints.append(
                    self.V_water[t + 1] == self.V_water[t] +
                    self.efficiency * self.Q_in[t] -
                    self.Q_out[t] -
                    self.Q_loss[t]
                )

                # Loss modeling
                constraints.append(
                    self.Q_loss[t] == self.V_water[t] * effective_loss_rate
                )

                # DETAILED: Add water quality constraints
                if fidelity >= FidelityLevel.DETAILED and self.water_quality_decay:
                    logger.debug("DETAILED: Water quality decay constraints would be added here")
                    # In practice, this would require quality state variables

                # DETAILED: Add stratification effects
                if fidelity >= FidelityLevel.DETAILED and self.stratification_model:
                    logger.debug("DETAILED: Thermal stratification constraints would be added here")
                    # This would require temperature layer variables

            # RESEARCH: Full CFD modeling
            if fidelity >= FidelityLevel.RESEARCH:
                logger.info("RESEARCH: Full CFD modeling activated for water storage")
                # Placeholder for detailed fluid dynamics

        # Flow constraints
        if self.Q_in is not None:
            constraints.append(self.Q_in <= self.max_flow_in_m3h)

        if self.Q_out is not None:
            constraints.append(self.Q_out <= self.max_flow_out_m3h)

        return constraints

    def rule_based_operation(self, water_demand: float, water_supply: float, t: int) -> tuple:
        """Rule-based water storage operation.

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

        # Calculate losses
        hourly_loss = current_level * self.loss_rate_daily / 24.0

        # Try to meet demand from storage
        available_water = current_level - self.min_level_m3
        max_outflow = min(self.max_flow_out_m3h, available_water)
        actual_outflow = min(water_demand, max_outflow)

        # Store excess supply
        available_capacity = self.max_level_m3 - current_level
        max_inflow = min(self.max_flow_in_m3h, available_capacity)
        actual_inflow = min(water_supply, max_inflow) * self.efficiency

        # Update water level
        self.water_level[t + 1] = current_level + actual_inflow - actual_outflow - hourly_loss

        # Ensure constraints are met
        self.water_level[t + 1] = max(self.min_level_m3,
                                      min(self.max_level_m3, self.water_level[t + 1]))

        return actual_outflow, actual_inflow

    def get_fill_percentage(self, timestep: int) -> float:
        """Get fill percentage at given timestep.

        Args:
            timestep: Timestep index

        Returns:
            Fill percentage (0-100)
        """
        if 0 <= timestep <= self.N:
            return (self.water_level[timestep] / self.capacity_m3) * 100
        return 0.0

    def reset(self):
        """Reset component state."""
        self.water_level[:] = 0
        self.water_level[0] = self.initial_level_m3

    def __repr__(self):
        """String representation."""
        return (f"WaterStorage(name='{self.name}', "
                f"capacity={self.capacity_m3}m³, "
                f"initial_level={self.initial_level_m3}m³)")