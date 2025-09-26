"""Water grid component for municipal water supply with MILP optimization support."""
import cvxpy as cp
import numpy as np
from pydantic import BaseModel, Field
from typing import Optional, List
import logging

from ..shared.registry import register_component
from ..shared.component import Component

logger = logging.getLogger(__name__)


class WaterGridParams(BaseModel):
    """Water grid parameters for municipal water connection."""
    max_supply_m3h: float = Field(10.0, description="Maximum water supply rate [m³/h]")
    max_discharge_m3h: float = Field(5.0, description="Maximum wastewater discharge rate [m³/h]")
    supply_pressure_bar: float = Field(3.0, description="Supply water pressure [bar]")
    min_pressure_bar: float = Field(1.0, description="Minimum acceptable pressure [bar]")
    water_price_per_m3: float = Field(1.5, description="Water price [$/m³]")
    wastewater_price_per_m3: float = Field(2.0, description="Wastewater treatment price [$/m³]")
    connection_fee_monthly: float = Field(20.0, description="Monthly connection fee [$]")
    supply_reliability: float = Field(0.99, description="Grid supply reliability factor (0-1)")
    water_quality_index: float = Field(0.95, description="Water quality index (0-1)")


@register_component("WaterGrid")
class WaterGrid(Component):
    """Water grid component for municipal water supply and wastewater discharge."""

    PARAMS_MODEL = WaterGridParams

    def _post_init(self):
        """Initialize water grid-specific attributes after DRY parameter unpacking."""
        self.type = "transmission"
        self.medium = "water"

        # CVXPY variables (created later by add_optimization_vars)
        self.Q_supply = None      # Water supplied from grid
        self.Q_discharge = None   # Wastewater discharged to grid
        self.Q_available = None   # Available water considering reliability

        # For rule-based operation
        self.water_imported = np.zeros(self.N)
        self.water_exported = np.zeros(self.N)
        self.total_cost = 0.0

    def add_optimization_vars(self):
        """Create CVXPY optimization variables."""
        self.Q_supply = cp.Variable(self.N, name=f'{self.name}_supply', nonneg=True)
        self.Q_discharge = cp.Variable(self.N, name=f'{self.name}_discharge', nonneg=True)
        self.Q_available = cp.Variable(self.N, name=f'{self.name}_available', nonneg=True)

        # Add flows
        self.flows['output']['Q_supply'] = {
            'type': 'water',
            'value': self.Q_supply,
            'quality': self.water_quality_index
        }
        self.flows['input']['Q_discharge'] = {
            'type': 'water',
            'value': self.Q_discharge,
            'is_wastewater': True
        }

    def set_constraints(self) -> List:
        """Set CVXPY constraints for water grid operation."""
        constraints = []

        if self.Q_supply is not None:
            # Supply constraints
            for t in range(self.N):
                # Available water based on reliability
                constraints.append(
                    self.Q_available[t] == self.max_supply_m3h * self.supply_reliability
                )

                # Cannot supply more than available
                constraints.append(
                    self.Q_supply[t] <= self.Q_available[t]
                )

        if self.Q_discharge is not None:
            # Discharge constraints
            constraints.append(self.Q_discharge <= self.max_discharge_m3h)

        # Physical constraint: cannot simultaneously import and export
        # (would require binary variables for strict enforcement)
        # For continuous relaxation, we rely on economic incentives

        return constraints

    def get_supply_cost(self, timestep: Optional[int] = None) -> float:
        """Calculate water supply cost.

        Args:
            timestep: Optional specific timestep. If None, calculates total.

        Returns:
            Water supply cost [$]
        """
        if timestep is not None:
            if 0 <= timestep < self.N:
                return self.water_imported[timestep] * self.water_price_per_m3
            return 0.0
        else:
            # Total cost over all timesteps
            total_water_cost = np.sum(self.water_imported) * self.water_price_per_m3
            total_wastewater_cost = np.sum(self.water_exported) * self.wastewater_price_per_m3
            connection_cost = self.connection_fee_monthly * (self.N / (24 * 30))  # Pro-rated
            return total_water_cost + total_wastewater_cost + connection_cost

    def rule_based_operation(self, water_balance: float, t: int) -> tuple:
        """Rule-based water grid operation.

        Args:
            water_balance: Net water balance at timestep t [m³/h]
                          (positive = deficit, negative = surplus)
            t: Current timestep

        Returns:
            Tuple of (water_imported, water_exported) [m³/h]
        """
        if t >= self.N:
            return 0.0, 0.0

        water_imported = 0.0
        water_exported = 0.0

        if water_balance > 0:
            # Deficit - import from grid
            available_supply = self.max_supply_m3h * self.supply_reliability
            water_imported = min(water_balance, available_supply)
            self.water_imported[t] = water_imported

        elif water_balance < 0:
            # Surplus - export to grid (as wastewater)
            water_exported = min(-water_balance, self.max_discharge_m3h)
            self.water_exported[t] = water_exported

        # Update cost tracking
        self.total_cost += (water_imported * self.water_price_per_m3 +
                           water_exported * self.wastewater_price_per_m3)

        return water_imported, water_exported

    def check_pressure_requirements(self, required_pressure: float) -> bool:
        """Check if grid can meet pressure requirements.

        Args:
            required_pressure: Required pressure [bar]

        Returns:
            True if pressure requirements are met
        """
        return self.supply_pressure_bar >= required_pressure

    def get_reliability_factor(self) -> float:
        """Get current grid reliability factor.

        Returns:
            Reliability factor (0-1)
        """
        return self.supply_reliability

    def get_water_quality(self) -> float:
        """Get water quality index.

        Returns:
            Water quality index (0-1)
        """
        return self.water_quality_index

    def get_total_water_imported(self) -> float:
        """Get total water imported from grid.

        Returns:
            Total water imported [m³]
        """
        return float(np.sum(self.water_imported))

    def get_total_water_exported(self) -> float:
        """Get total water exported to grid.

        Returns:
            Total water exported [m³]
        """
        return float(np.sum(self.water_exported))

    def reset(self):
        """Reset component state."""
        self.water_imported[:] = 0
        self.water_exported[:] = 0
        self.total_cost = 0.0

    def __repr__(self):
        """String representation."""
        return (f"WaterGrid(name='{self.name}', "
                f"max_supply={self.max_supply_m3h}m³/h, "
                f"price={self.water_price_per_m3}$/m³)")