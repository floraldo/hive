"""
SolarPV component for photovoltaic generation.

Generates electricity from solar irradiation profiles.
"""
import numpy as np
import cvxpy as cp
from typing import Optional, List, Union
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)


class SolarPVTechnicalParams(BaseModel):
    """Technical parameters for solar PV system."""
    capacity_kw: float = Field(5.0, description="Installed capacity [kW]")
    panel_efficiency: float = Field(0.20, description="Panel efficiency")
    degradation_rate: float = Field(0.005, description="Annual degradation rate")
    temperature_coefficient: float = Field(-0.004, description="Temperature coefficient [1/°C]")
    nominal_operating_temp: float = Field(45, description="NOCT [°C]")


class SolarPVParams(BaseModel):
    """Complete solar PV parameters."""
    technical: SolarPVTechnicalParams = Field(default_factory=SolarPVTechnicalParams)

    # Simplified constructor support
    capacity_kw: Optional[float] = None
    efficiency: Optional[float] = None

    def __init__(self, **data):
        """Initialize with support for flat parameters."""
        # Handle flat parameters
        if 'capacity_kw' in data and data['capacity_kw'] is not None:
            if 'technical' not in data:
                data['technical'] = {}
            data['technical']['capacity_kw'] = data.pop('capacity_kw')

        if 'efficiency' in data and data['efficiency'] is not None:
            if 'technical' not in data:
                data['technical'] = {}
            data['technical']['panel_efficiency'] = data.pop('efficiency')

        super().__init__(**data)


class SolarPV:
    """
    Solar PV component for electricity generation.

    Generates electricity based on solar irradiation and temperature profiles.
    """

    def __init__(self, name: str = "solar_pv", params: Optional[SolarPVParams] = None,
                 N: int = 24, profile_data: Optional[Union[List, np.ndarray]] = None):
        """
        Initialize solar PV component.

        Args:
            name: Component name
            params: Solar PV parameters
            N: Number of timesteps
            profile_data: Generation profile data (normalized 0-1 or actual kW)
        """
        self.name = name
        self.type = "generation"
        self.medium = "electricity"
        self.N = N

        # Use provided params or defaults
        self.params = params if params else SolarPVParams()

        # Extract key parameters
        self.capacity = self.params.technical.capacity_kw
        self.efficiency = self.params.technical.panel_efficiency

        # Initialize flows
        self.flows = {
            'source': {},  # PV as source of electricity
            'output': {}   # Output flows
        }

        # Set generation profile
        if profile_data is not None:
            if isinstance(profile_data, list):
                profile_data = np.array(profile_data)
            if len(profile_data) != N:
                # Resize profile to match timesteps
                profile_data = np.resize(profile_data, N)
            self.generation_profile = profile_data
        else:
            # Default profile: simple sinusoidal for daylight hours
            self.generation_profile = self._create_default_profile(N)

        # Normalize if needed (if max > capacity, assume it's already in kW)
        if np.max(self.generation_profile) <= 1.0:
            # Profile is normalized, scale by capacity
            self.generation_profile *= self.capacity

        # Initialize generation array (for rule-based solver)
        self.P_gen = self.generation_profile.copy()

        # For MILP solver
        self.P_gen_var = None

        logger.debug(f"Initialized SolarPV '{name}' with capacity={self.capacity}kW, "
                    f"max generation={np.max(self.generation_profile):.2f}kW")

    def _create_default_profile(self, N: int) -> np.ndarray:
        """
        Create default generation profile.

        Args:
            N: Number of timesteps

        Returns:
            Generation profile array
        """
        profile = np.zeros(N)
        daylight_hours = range(6, 18)  # 6 AM to 6 PM

        for hour in daylight_hours:
            if hour < N:
                # Simple sinusoidal profile peaking at noon
                angle = (hour - 6) * np.pi / 12
                profile[hour] = np.sin(angle)

        return profile

    def add_optimization_vars(self):
        """Add optimization variables for MILP solver."""
        # For solar PV, generation is fixed by the profile
        # So we don't create a variable, just use the profile directly
        self.P_gen_var = self.generation_profile

    def set_constraints(self) -> List:
        """
        Set constraints for MILP optimization.

        Returns:
            List of cvxpy constraints
        """
        constraints = []

        # Solar generation is deterministic based on profile
        # The only constraint is that actual output <= available generation
        for flow in self.flows.get('output', {}).values():
            if isinstance(flow['value'], cp.Variable):
                # Output cannot exceed available generation
                constraints.append(flow['value'] <= self.generation_profile)

        return constraints

    def get_available_power(self, timestep: int) -> float:
        """
        Get available power at given timestep.

        Args:
            timestep: Timestep index

        Returns:
            Available power in kW
        """
        if 0 <= timestep < self.N:
            return self.generation_profile[timestep]
        return 0.0

    def get_total_generation(self) -> float:
        """
        Get total generation over all timesteps.

        Returns:
            Total generation in kWh
        """
        return np.sum(self.generation_profile)

    def get_capacity_factor(self) -> float:
        """
        Calculate capacity factor.

        Returns:
            Capacity factor (0-1)
        """
        total_generation = self.get_total_generation()
        max_possible = self.capacity * self.N
        return total_generation / max_possible if max_possible > 0 else 0

    def update_profile(self, new_profile: Union[List, np.ndarray]):
        """
        Update generation profile.

        Args:
            new_profile: New generation profile
        """
        if isinstance(new_profile, list):
            new_profile = np.array(new_profile)

        if len(new_profile) != self.N:
            new_profile = np.resize(new_profile, self.N)

        # Normalize if needed
        if np.max(new_profile) <= 1.0:
            new_profile *= self.capacity

        self.generation_profile = new_profile
        self.P_gen = new_profile.copy()

    def reset(self):
        """Reset component state."""
        self.P_gen = self.generation_profile.copy()

    def __repr__(self):
        """String representation."""
        return (f"SolarPV(name='{self.name}', "
                f"capacity={self.capacity}kW, "
                f"total_generation={self.get_total_generation():.1f}kWh)")