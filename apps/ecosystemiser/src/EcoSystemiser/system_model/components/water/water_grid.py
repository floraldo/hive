"""Water grid component with MILP optimization support and hierarchical fidelity."""
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
# WATER GRID-SPECIFIC TECHNICAL PARAMETERS (Co-located with component)
# =============================================================================

class WaterGridTechnicalParams(TransmissionTechnicalParams):
    """Water grid-specific technical parameters extending transmission archetype.

    This model inherits from TransmissionTechnicalParams and adds water grid-specific
    parameters for different fidelity levels.
    """
    # Water grid economic parameters (should eventually move to economic block)
    water_tariff: float = Field(1.5, description="Water import price [$/m³]")
    wastewater_tariff: float = Field(2.0, description="Wastewater discharge price [$/m³]")

    # Water-specific parameters
    supply_pressure_bar: float = Field(3.0, description="Supply water pressure [bar]")
    min_pressure_bar: float = Field(1.0, description="Minimum acceptable pressure [bar]")
    supply_reliability: float = Field(0.99, description="Grid supply reliability factor (0-1)")

    # STANDARD fidelity additions
    pressure_losses: Optional[Dict[str, float]] = Field(
        None,
        description="Pressure loss factors in distribution"
    )
    water_quality_degradation: Optional[float] = Field(
        None,
        description="Water quality degradation factor"
    )

    # DETAILED fidelity parameters
    network_topology: Optional[Dict[str, Any]] = Field(
        None,
        description="Detailed network topology model"
    )
    peak_demand_surcharge: Optional[Dict[str, float]] = Field(
        None,
        description="Peak demand pricing structure"
    )

    # RESEARCH fidelity parameters
    hydraulic_model: Optional[Dict[str, Any]] = Field(
        None,
        description="Detailed hydraulic network model"
    )
    contamination_tracking: Optional[Dict[str, Any]] = Field(
        None,
        description="Water contamination tracking model"
    )


class WaterGridParams(ComponentParams):
    """Water grid parameters using the hierarchical technical parameter system."""
    technical: WaterGridTechnicalParams = Field(
        default_factory=lambda: WaterGridTechnicalParams(
            capacity_nominal=10.0,    # Default 10 m³/h capacity
            max_import=10.0,          # Default 10 m³/h import
            max_export=5.0,           # Default 5 m³/h discharge
            water_tariff=1.5,
            wastewater_tariff=2.0,
            fidelity_level=FidelityLevel.STANDARD
        ),
        description="Technical parameters following the hierarchical archetype system"
    )


@register_component("WaterGrid")
class WaterGrid(Component):
    """Water grid component for municipal water supply and wastewater discharge.

    This component follows the same pattern as the electrical Grid component
    but handles water flows instead of electrical power flows.
    """

    PARAMS_MODEL = WaterGridParams

    def _post_init(self):
        """Initialize water grid-specific attributes from technical parameters."""
        self.type = "transmission"
        self.medium = "water"

        # Single source of truth: the technical parameter block
        tech = self.technical

        # Core parameters extracted from technical block (m³/h)
        self.max_supply_m3h = tech.max_import     # Maximum supply rate
        self.max_discharge_m3h = tech.max_export  # Maximum discharge rate
        self.water_price_per_m3 = tech.water_tariff
        self.wastewater_price_per_m3 = tech.wastewater_tariff

        # Store water grid-specific parameters
        self.supply_pressure_bar = tech.supply_pressure_bar
        self.min_pressure_bar = tech.min_pressure_bar
        self.supply_reliability = tech.supply_reliability
        self.pressure_losses = tech.pressure_losses
        self.water_quality_degradation = tech.water_quality_degradation

        # CVXPY variables (for MILP solver)
        self.Q_import = None    # Water imported from grid
        self.Q_export = None    # Water exported to grid (wastewater)

    def add_optimization_vars(self, N: Optional[int] = None):
        """Create CVXPY optimization variables."""
        if N is None:
            N = self.N

        self.Q_import = cp.Variable(N, name=f'{self.name}_import', nonneg=True)
        self.Q_export = cp.Variable(N, name=f'{self.name}_export', nonneg=True)

        # Add flows
        self.flows['source']['Q_import'] = {
            'type': 'water',
            'value': self.Q_import
        }
        self.flows['sink']['Q_export'] = {
            'type': 'water',
            'value': self.Q_export
        }

    def set_constraints(self) -> List:
        """Set CVXPY constraints for water grid with fidelity-aware modeling."""
        constraints = []

        # Get fidelity level
        fidelity = self.technical.fidelity_level

        # Basic constraints (all fidelity levels)
        if self.Q_import is not None:
            # Import capacity constraints
            constraints.append(self.Q_import <= self.max_supply_m3h)

        if self.Q_export is not None:
            # Export capacity constraints
            constraints.append(self.Q_export <= self.max_discharge_m3h)

        # STANDARD: Add reliability constraints
        if fidelity >= FidelityLevel.STANDARD:
            if self.Q_import is not None and self.supply_reliability < 1.0:
                # Reduce effective capacity by reliability factor
                effective_supply = self.max_supply_m3h * self.supply_reliability
                constraints.append(self.Q_import <= effective_supply)

        # DETAILED: Add pressure-dependent constraints
        if fidelity >= FidelityLevel.DETAILED:
            if self.pressure_losses:
                # Pressure losses reduce effective capacity
                pressure_factor = self.pressure_losses.get('distribution_factor', 0.95)
                if self.Q_import is not None:
                    effective_supply = self.max_supply_m3h * pressure_factor
                    constraints.append(self.Q_import <= effective_supply)

        return constraints

    def get_operating_cost(self, timestep: int) -> float:
        """Calculate operating cost for water grid at given timestep.

        Args:
            timestep: Time index

        Returns:
            Operating cost [$]
        """
        if not hasattr(self, 'Q_import') or self.Q_import is None:
            return 0.0

        # Water import cost
        import_cost = 0.0
        export_cost = 0.0

        if hasattr(self.Q_import, 'value') and self.Q_import.value is not None:
            import_cost = self.Q_import.value[timestep] * self.water_price_per_m3

        if hasattr(self.Q_export, 'value') and self.Q_export.value is not None:
            export_cost = self.Q_export.value[timestep] * self.wastewater_price_per_m3

        return import_cost + export_cost

    def get_total_cost(self) -> float:
        """Calculate total operating cost over all timesteps."""
        if not hasattr(self, 'Q_import') or self.Q_import is None:
            return 0.0

        total_cost = 0.0

        if hasattr(self.Q_import, 'value') and self.Q_import.value is not None:
            total_import_cost = np.sum(self.Q_import.value) * self.water_price_per_m3
            total_cost += total_import_cost

        if hasattr(self.Q_export, 'value') and self.Q_export.value is not None:
            total_export_cost = np.sum(self.Q_export.value) * self.wastewater_price_per_m3
            total_cost += total_export_cost

        return total_cost

    def rule_based_operation(self, water_demand: float, wastewater_production: float, t: int) -> tuple:
        """Rule-based water grid operation with fidelity-aware performance.

        Args:
            water_demand: Required water import [m³/h]
            wastewater_production: Wastewater for export [m³/h]
            t: Current timestep

        Returns:
            Tuple of (actual_import, actual_export) [m³/h]
        """
        # Apply reliability factor for STANDARD+ fidelity
        effective_supply_capacity = self.max_supply_m3h
        if self.technical.fidelity_level >= FidelityLevel.STANDARD:
            effective_supply_capacity *= self.supply_reliability

        # Apply pressure losses for DETAILED+ fidelity
        if self.technical.fidelity_level >= FidelityLevel.DETAILED and self.pressure_losses:
            pressure_factor = self.pressure_losses.get('distribution_factor', 0.95)
            effective_supply_capacity *= pressure_factor

        # Meet water demand up to capacity
        actual_import = min(water_demand, effective_supply_capacity)

        # Handle wastewater export up to capacity
        actual_export = min(wastewater_production, self.max_discharge_m3h)

        return actual_import, actual_export

    def __repr__(self):
        """String representation."""
        return (f"WaterGrid(name='{self.name}', "
                f"max_supply={self.max_supply_m3h}m³/h, "
                f"max_discharge={self.max_discharge_m3h}m³/h, "
                f"fidelity={self.technical.fidelity_level.value})")