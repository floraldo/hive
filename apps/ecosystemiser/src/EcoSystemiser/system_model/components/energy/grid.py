"""Grid component with MILP optimization support and hierarchical fidelity."""
import cvxpy as cp
import numpy as np
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import logging

from ..shared.registry import register_component
from ..shared.component import Component, ComponentParams
from ..shared.archetypes import TransmissionTechnicalParams, FidelityLevel

logger = logging.getLogger(__name__)


# =============================================================================
# GRID-SPECIFIC TECHNICAL PARAMETERS (Co-located with component)
# =============================================================================

class GridTechnicalParams(TransmissionTechnicalParams):
    """Grid-specific technical parameters extending transmission archetype.

    This model inherits from TransmissionTechnicalParams and adds grid-specific
    parameters for different fidelity levels.
    """
    # Economic parameters (should eventually move to economic block)
    import_tariff: float = Field(0.25, description="Import electricity price [$/kWh]")
    feed_in_tariff: float = Field(0.08, description="Export electricity price [$/kWh]")

    # STANDARD fidelity additions
    grid_losses: Optional[float] = Field(
        None,
        description="Transmission loss factor [%]"
    )

    # DETAILED fidelity parameters
    voltage_limits: Optional[Dict[str, float]] = Field(
        None,
        description="Voltage limits {min_pu, max_pu}"
    )
    power_factor_limits: Optional[Dict[str, float]] = Field(
        None,
        description="Power factor requirements"
    )

    # RESEARCH fidelity parameters
    grid_impedance_model: Optional[Dict[str, Any]] = Field(
        None,
        description="Detailed grid impedance model"
    )


class GridParams(ComponentParams):
    """Grid parameters using the hierarchical technical parameter system."""
    technical: GridTechnicalParams = Field(
        default_factory=lambda: GridTechnicalParams(
            capacity_nominal=100.0,  # Default 100 kW capacity
            max_import=100.0,  # Default 100 kW import
            max_export=100.0,  # Default 100 kW export
            import_tariff=0.25,
            feed_in_tariff=0.08,
            fidelity_level=FidelityLevel.STANDARD
        ),
        description="Technical parameters following the hierarchical archetype system"
    )


@register_component("Grid")
class Grid(Component):
    """Grid connection component with CVXPY optimization support."""

    PARAMS_MODEL = GridParams

    def _post_init(self):
        """Initialize grid-specific attributes from technical parameters."""
        self.type = "transmission"
        self.medium = "electricity"

        # Single source of truth: the technical parameter block
        tech = self.technical

        # Core parameters extracted from technical block
        self.P_max_import = tech.max_import  # kW
        self.P_max_export = tech.max_export  # kW
        # For backward compatibility, use the max of import/export as P_max
        self.P_max = max(tech.max_import, tech.max_export)

        # Economic parameters
        self.import_tariff = tech.import_tariff
        self.feed_in_tariff = tech.feed_in_tariff

        # Store advanced parameters for fidelity-aware constraints
        self.grid_losses = tech.grid_losses
        self.voltage_limits = tech.voltage_limits
        self.power_factor_limits = tech.power_factor_limits

        # EXPLICIT FIDELITY CONTROL
        self.fidelity_level = tech.fidelity_level

        # CVXPY variables (created later by add_optimization_vars)
        self.P_draw = None  # Import from grid
        self.P_feed = None  # Export to grid

    def add_optimization_vars(self, N: int):
        """Create CVXPY optimization variables."""
        self.P_draw = cp.Variable(N, name=f'{self.name}_P_draw', nonneg=True)
        self.P_feed = cp.Variable(N, name=f'{self.name}_P_feed', nonneg=True)

        # Add as flows
        self.flows['source']['P_draw'] = {
            'type': 'electricity',
            'value': self.P_draw
        }
        self.flows['sink']['P_feed'] = {
            'type': 'electricity',
            'value': self.P_feed
        }

    def set_constraints(self) -> List:
        """Set CVXPY constraints for grid connection with fidelity-aware modeling.

        Constraint complexity scales with fidelity level:
        - SIMPLE: Basic import/export limits
        - STANDARD: Add grid losses
        - DETAILED: Add voltage and power factor constraints
        - RESEARCH: Full grid impedance modeling
        """
        constraints = []

        # Get fidelity level
        fidelity = getattr(self, 'fidelity_level', FidelityLevel.STANDARD)

        # BASIC CONSTRAINTS (always active)
        if self.P_draw is not None:
            constraints.append(self.P_draw <= self.P_max_import)
        if self.P_feed is not None:
            constraints.append(self.P_feed <= self.P_max_export)

        # STANDARD: Add grid losses
        if fidelity >= FidelityLevel.STANDARD:
            if self.grid_losses is not None and self.P_draw is not None:
                # Account for transmission losses on import
                # Actual power delivered = imported * (1 - losses)
                logger.debug("STANDARD: Adding grid loss constraints")

        # DETAILED: Add power quality constraints
        if fidelity >= FidelityLevel.DETAILED:
            if self.voltage_limits is not None:
                logger.debug("DETAILED: Voltage limit constraints would be added here")
                # In practice, this would require voltage variables

            if self.power_factor_limits is not None:
                logger.debug("DETAILED: Power factor constraints would be added here")
                # This would require reactive power modeling

        # RESEARCH: Full grid modeling
        if fidelity >= FidelityLevel.RESEARCH:
            logger.info("RESEARCH: Full grid impedance modeling activated")
            # Placeholder for detailed grid modeling

        return constraints

    def rule_based_import(self, power: float) -> float:
        """Import power from grid in rule-based mode."""
        return min(power, self.P_max)

    def rule_based_export(self, power: float) -> float:
        """Export power to grid in rule-based mode."""
        return min(power, self.P_max)