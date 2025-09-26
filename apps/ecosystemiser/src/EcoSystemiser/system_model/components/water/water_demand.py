"""Water demand component with MILP optimization support."""
import cvxpy as cp
import numpy as np
from pydantic import BaseModel, Field
from typing import Optional, List, Union
import logging

from ..shared.registry import register_component
from ..shared.component import Component

logger = logging.getLogger(__name__)


class WaterDemandParams(BaseModel):
    """Water demand parameters for consumption modeling."""
    base_demand_m3h: float = Field(0.5, description="Base water demand [m³/h]")
    peak_factor: float = Field(2.0, description="Peak demand multiplier")
    seasonal_variation: float = Field(0.2, description="Seasonal variation factor (0-1)")
    daily_pattern: Optional[List[float]] = Field(None, description="24-hour demand pattern")
    min_pressure_bar: float = Field(1.0, description="Minimum required water pressure [bar]")
    priority_level: int = Field(1, description="Priority level for demand fulfillment (1=highest)")


@register_component("WaterDemand")
class WaterDemand(Component):
    """Water demand component representing consumption patterns."""

    PARAMS_MODEL = WaterDemandParams

    def _post_init(self):
        """Initialize water demand-specific attributes after DRY parameter unpacking."""
        self.type = "consumption"
        self.medium = "water"

        # Create default daily pattern if not provided
        if not hasattr(self, 'daily_pattern') or self.daily_pattern is None:
            # Default residential pattern: peaks at 7-9am and 6-9pm
            self.daily_pattern = [
                0.5, 0.4, 0.3, 0.3, 0.4, 0.6, 0.9, 1.2, 1.0, 0.8,
                0.7, 0.6, 0.6, 0.7, 0.8, 0.9, 1.1, 1.3, 1.2, 1.0,
                0.8, 0.7, 0.6, 0.5
            ]

        # Normalize daily pattern
        pattern_mean = np.mean(self.daily_pattern)
        self.daily_pattern = [p / pattern_mean for p in self.daily_pattern]

        # CVXPY variables (created later by add_optimization_vars)
        self.Q_demand = None    # Water demand at each timestep
        self.Q_supplied = None  # Actual water supplied
        self.Q_shortfall = None # Unmet demand

        # For rule-based operation
        self.demand_profile = None
        self.actual_consumption = np.zeros(self.N)
        self.unmet_demand = np.zeros(self.N)

    def add_optimization_vars(self):
        """Create CVXPY optimization variables."""
        self.Q_demand = cp.Variable(self.N, name=f'{self.name}_demand', nonneg=True)
        self.Q_supplied = cp.Variable(self.N, name=f'{self.name}_supplied', nonneg=True)
        self.Q_shortfall = cp.Variable(self.N, name=f'{self.name}_shortfall', nonneg=True)

        # Add flows
        self.flows['input']['Q_supplied'] = {
            'type': 'water',
            'value': self.Q_supplied
        }
        self.flows['output']['Q_demand'] = {
            'type': 'water',
            'value': self.Q_demand
        }

    def set_constraints(self) -> List:
        """Set CVXPY constraints for water demand."""
        constraints = []

        if self.Q_demand is not None and self.demand_profile is not None:
            # Set demand based on profile
            for t in range(self.N):
                constraints.append(
                    self.Q_demand[t] == self.demand_profile[t]
                )

        if self.Q_supplied is not None and self.Q_demand is not None:
            # Water balance: supplied + shortfall = demand
            for t in range(self.N):
                constraints.append(
                    self.Q_supplied[t] + self.Q_shortfall[t] == self.Q_demand[t]
                )

            # Cannot supply more than demanded
            constraints.append(self.Q_supplied <= self.Q_demand)

        return constraints

    def set_demand_profile(self, profile: Optional[Union[np.ndarray, List[float]]] = None):
        """Set or generate the water demand profile.

        Args:
            profile: Optional custom demand profile. If None, generates from parameters.
        """
        if profile is not None:
            self.demand_profile = np.array(profile[:self.N])
        else:
            # Generate profile from daily pattern
            self.demand_profile = np.zeros(self.N)
            for t in range(self.N):
                hour_of_day = t % 24
                pattern_factor = self.daily_pattern[hour_of_day]

                # Apply seasonal variation (simple sinusoidal)
                day_of_year = (t // 24) % 365
                seasonal_factor = 1 + self.seasonal_variation * np.sin(2 * np.pi * day_of_year / 365)

                # Calculate demand
                self.demand_profile[t] = (self.base_demand_m3h *
                                         pattern_factor *
                                         seasonal_factor)

    def rule_based_operation(self, available_water: float, t: int) -> tuple:
        """Rule-based water demand fulfillment.

        Args:
            available_water: Available water supply at timestep t [m³/h]
            t: Current timestep

        Returns:
            Tuple of (actual_consumption, unmet_demand) [m³/h]
        """
        if t >= self.N or self.demand_profile is None:
            return 0.0, 0.0

        # Current demand
        demand = self.demand_profile[t]

        # Fulfill as much demand as possible
        actual_consumption = min(demand, available_water)
        unmet_demand = demand - actual_consumption

        # Store results
        self.actual_consumption[t] = actual_consumption
        self.unmet_demand[t] = unmet_demand

        return actual_consumption, unmet_demand

    def get_demand_at_timestep(self, t: int) -> float:
        """Get water demand at specific timestep.

        Args:
            t: Timestep index

        Returns:
            Water demand [m³/h]
        """
        if self.demand_profile is not None and 0 <= t < self.N:
            return float(self.demand_profile[t])
        return 0.0

    def get_fulfillment_rate(self) -> float:
        """Calculate overall demand fulfillment rate.

        Returns:
            Fulfillment rate (0-1)
        """
        if self.demand_profile is None:
            return 0.0

        total_demand = np.sum(self.demand_profile[:self.N])
        total_supplied = np.sum(self.actual_consumption)

        if total_demand > 0:
            return total_supplied / total_demand
        return 1.0

    def get_peak_demand(self) -> float:
        """Get peak demand value.

        Returns:
            Peak demand [m³/h]
        """
        if self.demand_profile is not None:
            return float(np.max(self.demand_profile))
        return self.base_demand_m3h * self.peak_factor

    def reset(self):
        """Reset component state."""
        self.actual_consumption[:] = 0
        self.unmet_demand[:] = 0
        if self.demand_profile is None:
            self.set_demand_profile()

    def __repr__(self):
        """String representation."""
        return (f"WaterDemand(name='{self.name}', "
                f"base_demand={self.base_demand_m3h}m³/h, "
                f"priority={self.priority_level})")