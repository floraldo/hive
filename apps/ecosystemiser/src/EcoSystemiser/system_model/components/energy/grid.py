"""Grid component for electricity transmission."""
import cvxpy as cp
import numpy as np
from pydantic import BaseModel, Field
from typing import Optional
from ..shared.component import Component, ComponentParams

class GridTechnicalParams(BaseModel):
    """Technical parameters for grid connection."""
    P_max: float = Field(..., description="Maximum grid connection capacity (kW)")
    feed_in_tariff: float = Field(0.08, description="Feed-in tariff (€/kWh)")
    import_tariff: float = Field(0.25, description="Import tariff (€/kWh)")

class GridParams(ComponentParams):
    """Complete parameter set for Grid component."""
    technical: GridTechnicalParams

class Grid(Component):
    """Grid connection component for electricity import/export."""

    def __init__(self, name: str, params: GridParams, n: int = 24):
        super().__init__(name, params, n)
        self.type = "transmission"
        self.medium = "electricity"

        # Extract technical parameters
        tech = params.technical
        self.P_max = tech.P_max
        self.feed_in_tariff = tech.feed_in_tariff
        self.import_tariff = tech.import_tariff

        # Initialize flow variables for grid
        # These will be set by system.connect()
        self.flows['source']['P_draw'] = {'value': np.zeros(n)}  # Draw from grid
        self.flows['sink']['P_feed'] = {'value': np.zeros(n)}    # Feed to grid

    def set_constraints(self):
        """Define grid operational constraints."""
        constraints = []

        # Grid draw constraint (import limit)
        if 'P_draw' in self.flows['source'] and isinstance(self.flows['source']['P_draw']['value'], cp.Variable):
            constraints.append(self.flows['source']['P_draw']['value'] <= self.P_max)

        # Grid feed constraint (export limit)
        if 'P_feed' in self.flows['sink'] and isinstance(self.flows['sink']['P_feed']['value'], cp.Variable):
            constraints.append(self.flows['sink']['P_feed']['value'] <= self.P_max)

        return constraints