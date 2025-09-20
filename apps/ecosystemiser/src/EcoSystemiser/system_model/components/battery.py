"""
Battery component for energy storage.

Handles charge/discharge with efficiency and constraints.
"""
import numpy as np
import cvxpy as cp
from typing import Optional, List
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)


class BatteryTechnicalParams(BaseModel):
    """Technical parameters for battery storage."""
    capacity_kwh: float = Field(10.0, description="Storage capacity [kWh]")
    max_charge_kw: float = Field(5.0, description="Maximum charge power [kW]")
    max_discharge_kw: float = Field(5.0, description="Maximum discharge power [kW]")
    round_trip_efficiency: float = Field(0.92, description="Round-trip efficiency")
    min_soc: float = Field(0.1, description="Minimum state of charge")
    max_soc: float = Field(0.9, description="Maximum state of charge")
    initial_soc: float = Field(0.5, description="Initial state of charge")
    degradation_rate: float = Field(0.02, description="Annual degradation rate")


class BatteryParams(BaseModel):
    """Complete battery parameters."""
    technical: BatteryTechnicalParams = Field(default_factory=BatteryTechnicalParams)

    # Simplified constructor support
    capacity_kwh: Optional[float] = None
    max_charge_kw: Optional[float] = None
    max_discharge_kw: Optional[float] = None
    round_trip_efficiency: Optional[float] = None
    initial_soc: Optional[float] = None

    def __init__(self, **data):
        """Initialize with support for flat parameters."""
        # Handle flat parameters
        tech_params = {}
        for key in ['capacity_kwh', 'max_charge_kw', 'max_discharge_kw',
                   'round_trip_efficiency', 'initial_soc']:
            if key in data and data[key] is not None:
                tech_params[key] = data.pop(key)

        if tech_params:
            if 'technical' not in data:
                data['technical'] = {}
            data['technical'].update(tech_params)

        super().__init__(**data)


class Battery:
    """
    Battery component for energy storage.

    Manages charge/discharge cycles with efficiency losses and SOC constraints.
    """

    def __init__(self, name: str = "battery", params: Optional[BatteryParams] = None, N: int = 24):
        """
        Initialize battery component.

        Args:
            name: Component name
            params: Battery parameters
            N: Number of timesteps
        """
        self.name = name
        self.type = "storage"
        self.medium = "electricity"
        self.N = N

        # Use provided params or defaults
        self.params = params if params else BatteryParams()

        # Extract key parameters
        self.E_max = self.params.technical.capacity_kwh
        self.P_charge_max = self.params.technical.max_charge_kw
        self.P_discharge_max = self.params.technical.max_discharge_kw
        self.eta = np.sqrt(self.params.technical.round_trip_efficiency)  # One-way efficiency
        self.min_soc = self.params.technical.min_soc
        self.max_soc = self.params.technical.max_soc
        self.E_init = self.params.technical.initial_soc * self.E_max

        # Initialize flows
        self.flows = {
            'charge': {},      # Incoming power for charging
            'discharge': {},   # Outgoing power from discharging
            'input': {},       # All inputs
            'output': {}       # All outputs
        }

        # Initialize state arrays (for rule-based solver)
        self.E = np.zeros(N + 1)  # Energy state (includes initial state)
        self.E[0] = self.E_init
        self.P_charge = np.zeros(N)
        self.P_discharge = np.zeros(N)

        # For MILP solver
        self.E_var = None
        self.P_charge_var = None
        self.P_discharge_var = None

        logger.debug(f"Initialized Battery '{name}' with capacity={self.E_max}kWh, "
                    f"initial SOC={self.E_init/self.E_max:.1%}")

    def add_optimization_vars(self):
        """Add optimization variables for MILP solver."""
        self.E_var = cp.Variable(self.N + 1, name=f"{self.name}_energy", nonneg=True)
        self.P_charge_var = cp.Variable(self.N, name=f"{self.name}_charge", nonneg=True)
        self.P_discharge_var = cp.Variable(self.N, name=f"{self.name}_discharge", nonneg=True)

    def set_constraints(self) -> List:
        """
        Set constraints for MILP optimization.

        Returns:
            List of cvxpy constraints
        """
        constraints = []

        if self.E_var is not None:
            # Initial state
            constraints.append(self.E_var[0] == self.E_init)

            # Energy balance for each timestep
            for t in range(self.N):
                # E[t+1] = E[t] + eta*P_charge[t] - P_discharge[t]/eta
                constraints.append(
                    self.E_var[t + 1] == self.E_var[t] +
                    self.eta * self.P_charge_var[t] -
                    self.P_discharge_var[t] / self.eta
                )

            # SOC constraints
            constraints.append(self.E_var >= self.min_soc * self.E_max)
            constraints.append(self.E_var <= self.max_soc * self.E_max)

        if self.P_charge_var is not None:
            # Charge power constraint
            constraints.append(self.P_charge_var <= self.P_charge_max)

        if self.P_discharge_var is not None:
            # Discharge power constraint
            constraints.append(self.P_discharge_var <= self.P_discharge_max)

        # Cannot charge and discharge simultaneously (optional)
        # This would require binary variables for strict enforcement

        # Connect flows to charge/discharge variables
        for flow in self.flows.get('input', {}).values():
            if isinstance(flow['value'], cp.Variable):
                # Input flow contributes to charging
                constraints.append(flow['value'] <= self.P_charge_var)

        for flow in self.flows.get('output', {}).values():
            if isinstance(flow['value'], cp.Variable):
                # Output flow comes from discharging
                constraints.append(flow['value'] <= self.P_discharge_var)

        return constraints

    def charge(self, power: float, timestep: int) -> float:
        """
        Charge battery (for rule-based solver).

        Args:
            power: Charging power [kW]
            timestep: Current timestep

        Returns:
            Actual charging power [kW]
        """
        if timestep >= self.N:
            return 0.0

        # Check available capacity
        available_capacity = self.max_soc * self.E_max - self.E[timestep]
        max_charge_energy = available_capacity

        # Apply power constraint
        max_charge_power = min(self.P_charge_max, max_charge_energy)

        # Actual charge
        actual_charge = min(power, max_charge_power)

        # Update state
        self.P_charge[timestep] = actual_charge
        self.E[timestep + 1] = self.E[timestep] + actual_charge * self.eta

        return actual_charge

    def discharge(self, power: float, timestep: int) -> float:
        """
        Discharge battery (for rule-based solver).

        Args:
            power: Requested discharge power [kW]
            timestep: Current timestep

        Returns:
            Actual discharge power [kW]
        """
        if timestep >= self.N:
            return 0.0

        # Check available energy
        available_energy = self.E[timestep] - self.min_soc * self.E_max

        # Apply power constraint
        max_discharge_power = min(self.P_discharge_max, available_energy * self.eta)

        # Actual discharge
        actual_discharge = min(power, max_discharge_power)

        # Update state
        self.P_discharge[timestep] = actual_discharge
        self.E[timestep + 1] = self.E[timestep] - actual_discharge / self.eta

        return actual_discharge

    def get_soc(self, timestep: int) -> float:
        """
        Get state of charge at given timestep.

        Args:
            timestep: Timestep index

        Returns:
            SOC (0-1)
        """
        if 0 <= timestep <= self.N:
            return self.E[timestep] / self.E_max
        return 0.0

    def get_available_charge_power(self, timestep: int) -> float:
        """
        Get available charging power at given timestep.

        Args:
            timestep: Timestep index

        Returns:
            Available charge power [kW]
        """
        if timestep >= self.N:
            return 0.0

        available_capacity = self.max_soc * self.E_max - self.E[timestep]
        return min(self.P_charge_max, available_capacity)

    def get_available_discharge_power(self, timestep: int) -> float:
        """
        Get available discharge power at given timestep.

        Args:
            timestep: Timestep index

        Returns:
            Available discharge power [kW]
        """
        if timestep >= self.N:
            return 0.0

        available_energy = self.E[timestep] - self.min_soc * self.E_max
        return min(self.P_discharge_max, available_energy * self.eta)

    def calculate_cycles(self) -> float:
        """
        Calculate equivalent full cycles.

        Returns:
            Number of full charge/discharge cycles
        """
        total_discharge = np.sum(self.P_discharge)
        return total_discharge / self.E_max if self.E_max > 0 else 0

    def reset(self):
        """Reset component state."""
        self.E[:] = 0
        self.E[0] = self.E_init
        self.P_charge[:] = 0
        self.P_discharge[:] = 0

    def __repr__(self):
        """String representation."""
        return (f"Battery(name='{self.name}', "
                f"capacity={self.E_max}kWh, "
                f"initial_soc={self.E_init/self.E_max:.1%})")