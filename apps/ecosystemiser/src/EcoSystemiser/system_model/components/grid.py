"""
Grid component for electrical grid connection.

Handles import/export with tariffs and capacity limits.
"""
import numpy as np
import cvxpy as cp
from typing import Optional, List
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)


class GridTechnicalParams(BaseModel):
    """Technical parameters for grid connection."""
    max_import_kw: float = Field(1000.0, description="Maximum import power [kW]")
    max_export_kw: float = Field(1000.0, description="Maximum export power [kW]")
    voltage_level: float = Field(400, description="Voltage level [V]")
    phases: int = Field(3, description="Number of phases")
    frequency: float = Field(50, description="Grid frequency [Hz]")


class GridTariffParams(BaseModel):
    """Tariff parameters for grid electricity."""
    import_price_per_kwh: float = Field(0.30, description="Import price [€/kWh]")
    export_price_per_kwh: float = Field(0.12, description="Export price [€/kWh]")
    demand_charge_per_kw: float = Field(0.0, description="Demand charge [€/kW]")
    connection_charge_monthly: float = Field(50.0, description="Monthly connection charge [€]")


class GridParams(BaseModel):
    """Complete grid parameters."""
    technical: GridTechnicalParams = Field(default_factory=GridTechnicalParams)
    tariff: GridTariffParams = Field(default_factory=GridTariffParams)

    # Simplified constructor support
    max_import_kw: Optional[float] = None
    max_export_kw: Optional[float] = None
    import_price: Optional[float] = None
    export_price: Optional[float] = None

    def __init__(self, **data):
        """Initialize with support for flat parameters."""
        # Handle flat parameters
        if 'max_import_kw' in data and data['max_import_kw'] is not None:
            if 'technical' not in data:
                data['technical'] = {}
            data['technical']['max_import_kw'] = data.pop('max_import_kw')

        if 'max_export_kw' in data and data['max_export_kw'] is not None:
            if 'technical' not in data:
                data['technical'] = {}
            data['technical']['max_export_kw'] = data.pop('max_export_kw')

        if 'import_price' in data and data['import_price'] is not None:
            if 'tariff' not in data:
                data['tariff'] = {}
            data['tariff']['import_price_per_kwh'] = data.pop('import_price')

        if 'export_price' in data and data['export_price'] is not None:
            if 'tariff' not in data:
                data['tariff'] = {}
            data['tariff']['export_price_per_kwh'] = data.pop('export_price')

        super().__init__(**data)


class Grid:
    """
    Grid component for electrical grid connection.

    Handles bidirectional power flow with the electrical grid,
    including import/export limits and tariffs.
    """

    def __init__(self, name: str = "grid", params: Optional[GridParams] = None, N: int = 24):
        """
        Initialize grid component.

        Args:
            name: Component name
            params: Grid parameters
            N: Number of timesteps
        """
        self.name = name
        self.type = "transmission"
        self.medium = "electricity"
        self.N = N

        # Use provided params or defaults
        self.params = params if params else GridParams()

        # Extract key parameters
        self.P_import_max = self.params.technical.max_import_kw
        self.P_export_max = self.params.technical.max_export_kw
        self.import_price = self.params.tariff.import_price_per_kwh
        self.export_price = self.params.tariff.export_price_per_kwh

        # Initialize flows
        self.flows = {
            'import': {},  # Grid imports (we export to grid)
            'export': {},  # Grid exports (we import from grid)
            'source': {},  # Grid as source
            'sink': {}     # Grid as sink
        }

        # Initialize power arrays (for rule-based solver)
        self.P_import = np.zeros(N)
        self.P_export = np.zeros(N)

        # For MILP solver
        self.P_import_var = None
        self.P_export_var = None

        logger.debug(f"Initialized Grid '{name}' with max import={self.P_import_max}kW, "
                    f"max export={self.P_export_max}kW")

    def add_optimization_vars(self):
        """Add optimization variables for MILP solver."""
        self.P_import_var = cp.Variable(self.N, name=f"{self.name}_import", nonneg=True)
        self.P_export_var = cp.Variable(self.N, name=f"{self.name}_export", nonneg=True)

    def set_constraints(self) -> List:
        """
        Set constraints for MILP optimization.

        Returns:
            List of cvxpy constraints
        """
        constraints = []

        if self.P_import_var is not None:
            # Import capacity constraint
            constraints.append(self.P_import_var <= self.P_import_max)

        if self.P_export_var is not None:
            # Export capacity constraint
            constraints.append(self.P_export_var <= self.P_export_max)

        # Energy balance constraint
        # Sum of all flows in and out should balance
        total_in = 0
        total_out = 0

        for flow in self.flows.get('source', {}).values():
            if isinstance(flow['value'], cp.Variable):
                total_out += flow['value']

        for flow in self.flows.get('sink', {}).values():
            if isinstance(flow['value'], cp.Variable):
                total_in += flow['value']

        # Grid can both import and export
        if self.P_import_var is not None and self.P_export_var is not None:
            if isinstance(total_in, cp.Expression) or isinstance(total_out, cp.Expression):
                # Balance: what we export to grid + what others consume =
                #          what we import from grid + what others generate
                constraints.append(total_in + self.P_import_var == total_out + self.P_export_var)

        return constraints

    def calculate_cost(self, timestep: Optional[int] = None) -> float:
        """
        Calculate grid cost for given timestep or total.

        Args:
            timestep: Specific timestep (None for total)

        Returns:
            Cost in currency units
        """
        if timestep is not None:
            import_cost = self.P_import[timestep] * self.import_price
            export_revenue = self.P_export[timestep] * self.export_price
            return import_cost - export_revenue
        else:
            import_cost = np.sum(self.P_import) * self.import_price
            export_revenue = np.sum(self.P_export) * self.export_price
            return import_cost - export_revenue

    def get_carbon_emissions(self, timestep: Optional[int] = None) -> float:
        """
        Calculate carbon emissions from grid electricity.

        Args:
            timestep: Specific timestep (None for total)

        Returns:
            CO2 emissions in kg
        """
        # Assume 0.45 kg CO2/kWh for grid electricity (EU average)
        co2_factor = 0.45

        if timestep is not None:
            return self.P_import[timestep] * co2_factor
        else:
            return np.sum(self.P_import) * co2_factor

    def reset(self):
        """Reset component state."""
        self.P_import[:] = 0
        self.P_export[:] = 0

    def __repr__(self):
        """String representation."""
        return (f"Grid(name='{self.name}', "
                f"max_import={self.P_import_max}kW, "
                f"max_export={self.P_export_max}kW)")