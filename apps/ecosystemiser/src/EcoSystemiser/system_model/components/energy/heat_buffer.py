"""Heat buffer (thermal storage) component with MILP optimization support and hierarchical fidelity."""
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
# HEAT BUFFER-SPECIFIC TECHNICAL PARAMETERS (Co-located with component)
# =============================================================================

class HeatBufferTechnicalParams(StorageTechnicalParams):
    """Heat buffer-specific technical parameters extending storage archetype.

    This model inherits from StorageTechnicalParams and adds thermal storage-specific
    parameters for different fidelity levels.
    """
    # Heat-specific parameters
    thermal_medium: str = Field("water", description="Thermal storage medium")
    temperature_range: Optional[Dict[str, float]] = Field(
        None,
        description="Operating temperature range {min_temp, max_temp} [°C]"
    )

    # STANDARD fidelity additions
    heat_loss_coefficient: Optional[float] = Field(
        None,
        description="Heat loss coefficient [kW/°C]"
    )

    # DETAILED fidelity parameters
    stratification_model: Optional[Dict[str, Any]] = Field(
        None,
        description="Thermal stratification model parameters"
    )
    ambient_coupling: Optional[Dict[str, float]] = Field(
        None,
        description="Coupling to ambient temperature"
    )

    # RESEARCH fidelity parameters
    thermal_dynamics_model: Optional[Dict[str, Any]] = Field(
        None,
        description="Detailed thermal dynamics model"
    )


class HeatBufferParams(ComponentParams):
    """Heat buffer parameters using the hierarchical technical parameter system.

    Thermal capacity is now specified through the technical parameter block,
    not as flat parameters.
    """
    technical: HeatBufferTechnicalParams = Field(
        default_factory=lambda: HeatBufferTechnicalParams(
            capacity_nominal=20.0,  # Default 20 kWh thermal storage
            max_charge_rate=5.0,    # Default 5 kW charge rate
            max_discharge_rate=5.0, # Default 5 kW discharge rate
            efficiency_roundtrip=0.90,
            fidelity_level=FidelityLevel.STANDARD
        ),
        description="Technical parameters following the hierarchical archetype system"
    )


@register_component("HeatBuffer")
class HeatBuffer(Component):
    """Heat buffer (thermal storage) component with CVXPY optimization support."""

    PARAMS_MODEL = HeatBufferParams

    def _post_init(self):
        """Initialize heat buffer-specific attributes from technical parameters.

        All parameters are now sourced from the technical parameter block,
        following the single source of truth principle.
        """
        self.type = "storage"
        self.medium = "heat"

        # Single source of truth: the technical parameter block
        tech = self.technical

        # Core parameters extracted from technical block
        self.E_max = tech.capacity_nominal  # kWh
        self.P_max = max(tech.max_charge_rate, tech.max_discharge_rate)  # kW
        self.P_max_charge = tech.max_charge_rate
        self.P_max_discharge = tech.max_discharge_rate
        self.eta = tech.efficiency_roundtrip
        self.E_init = tech.initial_soc_pct * tech.capacity_nominal if tech.initial_soc_pct else tech.capacity_nominal * 0.5

        # Store advanced parameters for fidelity-aware constraints
        self.thermal_medium = tech.thermal_medium
        self.temperature_range = tech.temperature_range
        self.heat_loss_coefficient = tech.heat_loss_coefficient
        self.stratification_model = tech.stratification_model
        self.ambient_coupling = tech.ambient_coupling

        # EXPLICIT FIDELITY CONTROL
        self.fidelity_level = tech.fidelity_level

        # Set capacity alias for compatibility
        self.capacity = self.E_max

        # Storage array for rule-based solver
        self.E = None  # Will be initialized by solver

        # CVXPY variables (created later by add_optimization_vars)
        self.E_opt = None
        self.P_cha = None
        self.P_dis = None

    def add_optimization_vars(self, N: Optional[int] = None):
        """Create CVXPY optimization variables."""
        if N is None:
            N = self.N

        self.E_opt = cp.Variable(N, name=f'{self.name}_E')
        self.P_cha = cp.Variable(N, name=f'{self.name}_P_cha', nonneg=True)
        self.P_dis = cp.Variable(N, name=f'{self.name}_P_dis', nonneg=True)

        # Store as E for compatibility
        self.E = self.E_opt

        # Add charge/discharge as flows
        self.flows['sink']['P_cha'] = {
            'type': 'heat',
            'value': self.P_cha
        }
        self.flows['source']['P_dis'] = {
            'type': 'heat',
            'value': self.P_dis
        }

    def set_constraints(self) -> List:
        """Set CVXPY constraints for heat buffer with fidelity-aware modeling.

        Constraint complexity scales with fidelity level:
        - SIMPLE: Basic energy balance and bounds
        - STANDARD: Add heat losses to ambient
        - DETAILED: Add thermal stratification and temperature effects
        - RESEARCH: Full thermal dynamics modeling
        """
        constraints = []
        N = self.E_opt.shape[0] if self.E_opt is not None else 0

        if self.E_opt is not None:
            # Get fidelity level
            fidelity = getattr(self, 'fidelity_level', FidelityLevel.STANDARD)

            # BASIC CONSTRAINTS (always active)
            # Initial state
            constraints.append(self.E_opt[0] == self.E_init)

            # Energy bounds
            constraints.append(self.E_opt >= 0)
            constraints.append(self.E_opt <= self.E_max)

            # Power limits with separate charge/discharge rates
            if self.P_cha is not None:
                constraints.append(self.P_cha <= self.P_max_charge)
            if self.P_dis is not None:
                constraints.append(self.P_dis <= self.P_max_discharge)

            # Energy balance dynamics - Progressive Enhancement Pattern
            for t in range(1, N):
                # --- SIMPLE MODEL (OG Systemiser baseline) ---
                # Perfect thermal storage with efficiency: E[t] = E[t-1] + eta * (P_in - P_out)
                energy_balance = self.E_opt[t-1] + self.eta * (self.P_cha[t] - self.P_dis[t])

                # --- STANDARD ENHANCEMENTS (additive on top of SIMPLE) ---
                if fidelity >= FidelityLevel.STANDARD and self.heat_loss_coefficient:
                    # Add ambient heat losses to the perfect storage model
                    if hasattr(self, 'system') and hasattr(self.system, 'profiles'):
                        if 'ambient_temperature' in self.system.profiles:
                            # Simplified heat loss model: Loss proportional to stored energy
                            heat_loss = self.heat_loss_coefficient * 0.1  # Simplified constant loss
                            energy_balance = energy_balance - heat_loss
                            logger.debug("STANDARD: Applied heat loss to thermal storage")

                # --- DETAILED ENHANCEMENTS (additive on top of STANDARD) ---
                if fidelity >= FidelityLevel.DETAILED and self.stratification_model:
                    # Thermal stratification would modify the energy balance here
                    logger.debug("DETAILED: Thermal stratification would modify energy balance")
                    # In practice: energy_balance = apply_stratification_effects(energy_balance)

                if fidelity >= FidelityLevel.DETAILED and self.ambient_coupling:
                    # Enhanced ambient coupling would further modify the balance
                    logger.debug("DETAILED: Enhanced ambient coupling would modify energy balance")
                    # In practice: energy_balance = apply_ambient_coupling(energy_balance)

                # --- RESEARCH ENHANCEMENTS (additive on top of DETAILED) ---
                if fidelity >= FidelityLevel.RESEARCH:
                    logger.debug("RESEARCH: Full thermal dynamics would modify energy balance")
                    # In practice: energy_balance = apply_cfd_thermal_dynamics(energy_balance)

                # Apply the final energy balance constraint with all fidelity enhancements
                constraints.append(self.E_opt[t] == energy_balance)


        return constraints

    def rule_based_charge(self, power: float, t: int) -> float:
        """Charge heat buffer in rule-based mode."""
        if self.E is None:
            return 0.0

        # Available capacity
        available_capacity = self.E_max - self.E[t]

        # Maximum charge power considering efficiency
        max_charge = min(power, self.P_max, available_capacity / self.eta)

        # Update state
        actual_energy = max_charge * self.eta
        self.E[t+1] = self.E[t] + actual_energy if t < len(self.E)-1 else self.E[t]

        return max_charge

    def rule_based_discharge(self, power: float, t: int) -> float:
        """Discharge heat buffer in rule-based mode."""
        if self.E is None:
            return 0.0

        # Available energy
        available_energy = self.E[t]

        # Maximum discharge power considering efficiency
        max_discharge = min(power, self.P_max, available_energy * self.eta)

        # Update state
        actual_energy = max_discharge / self.eta
        self.E[t+1] = self.E[t] - actual_energy if t < len(self.E)-1 else self.E[t]

        return max_discharge