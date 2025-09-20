"""
PowerDemand component for electricity consumption.

Represents electrical load with demand profiles.
"""
import numpy as np
import cvxpy as cp
from typing import Optional, List, Union
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)


class PowerDemandTechnicalParams(BaseModel):
    """Technical parameters for power demand."""
    avg_daily_kwh: float = Field(30.0, description="Average daily consumption [kWh]")
    peak_demand_kw: float = Field(8.0, description="Peak demand [kW]")
    min_demand_kw: float = Field(0.5, description="Minimum demand [kW]")
    power_factor: float = Field(0.95, description="Power factor")


class PowerDemandParams(BaseModel):
    """Complete power demand parameters."""
    technical: PowerDemandTechnicalParams = Field(default_factory=PowerDemandTechnicalParams)

    # Simplified constructor support
    peak_demand_kw: Optional[float] = None
    avg_daily_kwh: Optional[float] = None
    profile_data: Optional[List[float]] = None

    def __init__(self, **data):
        """Initialize with support for flat parameters."""
        # Handle flat parameters
        if 'peak_demand_kw' in data and data['peak_demand_kw'] is not None:
            if 'technical' not in data:
                data['technical'] = {}
            data['technical']['peak_demand_kw'] = data.pop('peak_demand_kw')

        if 'avg_daily_kwh' in data and data['avg_daily_kwh'] is not None:
            if 'technical' not in data:
                data['technical'] = {}
            data['technical']['avg_daily_kwh'] = data.pop('avg_daily_kwh')

        # Profile data is handled separately
        self._profile_data = data.pop('profile_data', None)

        super().__init__(**data)


class PowerDemand:
    """
    Power demand component for electricity consumption.

    Represents electrical loads with time-varying demand profiles.
    """

    def __init__(self, name: str = "power_demand", params: Optional[PowerDemandParams] = None,
                 N: int = 24, profile_data: Optional[Union[List, np.ndarray]] = None):
        """
        Initialize power demand component.

        Args:
            name: Component name
            params: Power demand parameters
            N: Number of timesteps
            profile_data: Demand profile data (kW per timestep)
        """
        self.name = name
        self.type = "consumption"
        self.medium = "electricity"
        self.N = N

        # Use provided params or defaults
        self.params = params if params else PowerDemandParams()

        # Extract key parameters
        self.peak_demand = self.params.technical.peak_demand_kw
        self.avg_daily_kwh = self.params.technical.avg_daily_kwh
        self.min_demand = self.params.technical.min_demand_kw

        # Initialize flows
        self.flows = {
            'sink': {},    # Demand as sink for electricity
            'input': {}    # Input flows
        }

        # Set demand profile
        if profile_data is not None:
            if isinstance(profile_data, list):
                profile_data = np.array(profile_data)
            if len(profile_data) != N:
                # Resize profile to match timesteps
                profile_data = np.resize(profile_data, N)
            self.demand_profile = profile_data
        elif hasattr(self.params, '_profile_data') and self.params._profile_data:
            # Use profile from params
            self.demand_profile = np.array(self.params._profile_data)
            if len(self.demand_profile) != N:
                self.demand_profile = np.resize(self.demand_profile, N)
        else:
            # Create default profile
            self.demand_profile = self._create_default_profile(N)

        # Initialize demand array (for rule-based solver)
        self.P_demand = self.demand_profile.copy()

        # For MILP solver
        self.P_demand_var = None

        # Track unmet demand
        self.unmet_demand = np.zeros(N)

        logger.debug(f"Initialized PowerDemand '{name}' with peak={self.peak_demand}kW, "
                    f"total daily={np.sum(self.demand_profile):.1f}kWh")

    def _create_default_profile(self, N: int) -> np.ndarray:
        """
        Create default demand profile (residential pattern).

        Args:
            N: Number of timesteps

        Returns:
            Demand profile array
        """
        profile = np.ones(N) * self.min_demand

        # Morning peak (6-9 AM)
        for hour in range(6, 9):
            if hour < N:
                profile[hour] = self.min_demand + (self.peak_demand - self.min_demand) * 0.7

        # Evening peak (17-22 PM)
        for hour in range(17, 22):
            if hour < N:
                profile[hour] = self.min_demand + (self.peak_demand - self.min_demand) * 0.9

        # Midday moderate (9-17)
        for hour in range(9, 17):
            if hour < N:
                profile[hour] = self.min_demand + (self.peak_demand - self.min_demand) * 0.4

        # Night low (22-6)
        for hour in range(22, 24):
            if hour < N:
                profile[hour] = self.min_demand + (self.peak_demand - self.min_demand) * 0.2
        for hour in range(0, 6):
            if hour < N:
                profile[hour] = self.min_demand + (self.peak_demand - self.min_demand) * 0.2

        # Scale to match daily consumption if specified
        if self.avg_daily_kwh > 0:
            current_total = np.sum(profile)
            if current_total > 0:
                scale_factor = self.avg_daily_kwh / current_total
                profile *= scale_factor

        return profile

    def add_optimization_vars(self):
        """Add optimization variables for MILP solver."""
        # For demand, the requirement is fixed by the profile
        # We may have a variable for unmet demand in advanced models
        self.P_demand_var = self.demand_profile
        self.unmet_demand_var = cp.Variable(self.N, name=f"{self.name}_unmet", nonneg=True)

    def set_constraints(self) -> List:
        """
        Set constraints for MILP optimization.

        Returns:
            List of cvxpy constraints
        """
        constraints = []

        # Demand must be met (or recorded as unmet)
        total_supply = 0

        for flow in self.flows.get('input', {}).values():
            if isinstance(flow['value'], cp.Variable):
                total_supply += flow['value']

        if isinstance(total_supply, cp.Expression):
            # Supply + unmet demand = required demand
            if self.unmet_demand_var is not None:
                constraints.append(
                    total_supply + self.unmet_demand_var == self.demand_profile
                )
            else:
                # Strict requirement: supply must meet demand
                constraints.append(total_supply == self.demand_profile)

        return constraints

    def get_demand(self, timestep: int) -> float:
        """
        Get demand at given timestep.

        Args:
            timestep: Timestep index

        Returns:
            Demand in kW
        """
        if 0 <= timestep < self.N:
            return self.demand_profile[timestep]
        return 0.0

    def get_total_demand(self) -> float:
        """
        Get total demand over all timesteps.

        Returns:
            Total demand in kWh
        """
        return np.sum(self.demand_profile)

    def get_peak_demand(self) -> float:
        """
        Get peak demand.

        Returns:
            Peak demand in kW
        """
        return np.max(self.demand_profile)

    def get_load_factor(self) -> float:
        """
        Calculate load factor.

        Returns:
            Load factor (average/peak ratio)
        """
        avg_demand = np.mean(self.demand_profile)
        peak = self.get_peak_demand()
        return avg_demand / peak if peak > 0 else 0

    def update_profile(self, new_profile: Union[List, np.ndarray]):
        """
        Update demand profile.

        Args:
            new_profile: New demand profile
        """
        if isinstance(new_profile, list):
            new_profile = np.array(new_profile)

        if len(new_profile) != self.N:
            new_profile = np.resize(new_profile, self.N)

        self.demand_profile = new_profile
        self.P_demand = new_profile.copy()

    def calculate_unmet_demand(self) -> float:
        """
        Calculate total unmet demand.

        Returns:
            Total unmet demand in kWh
        """
        return np.sum(self.unmet_demand)

    def reset(self):
        """Reset component state."""
        self.P_demand = self.demand_profile.copy()
        self.unmet_demand[:] = 0

    def __repr__(self):
        """String representation."""
        return (f"PowerDemand(name='{self.name}', "
                f"peak={self.get_peak_demand():.1f}kW, "
                f"total={self.get_total_demand():.1f}kWh)")