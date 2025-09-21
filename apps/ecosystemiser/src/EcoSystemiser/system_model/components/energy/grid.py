"""Grid component with MILP optimization support."""
import cvxpy as cp
import numpy as np
from pydantic import BaseModel, Field
from typing import Optional, List
import logging

from ..shared.registry import register_component
from ..shared.component import Component

logger = logging.getLogger(__name__)


class GridParams(BaseModel):
    """Grid parameters matching original Systemiser."""
    P_max: float = Field(100.0, description="Max import/export power [kW]")
    import_tariff: float = Field(0.25, description="Import electricity price [$/kWh]")
    feed_in_tariff: float = Field(0.08, description="Export electricity price [$/kWh]")


@register_component("Grid")
class Grid(Component):
    """Grid connection component with CVXPY optimization support."""

    PARAMS_MODEL = GridParams

    def _post_init(self):
        """Initialize grid-specific attributes after DRY parameter unpacking."""
        self.type = "transmission"
        self.medium = "electricity"

        # DRY pattern eliminates these lines (auto-unpacked):
        # self.P_max = params.P_max
        # self.import_tariff = params.import_tariff
        # self.feed_in_tariff = params.feed_in_tariff

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
        """Set CVXPY constraints for grid connection."""
        constraints = []

        # Power limits
        if self.P_draw is not None:
            constraints.append(self.P_draw <= self.P_max)
        if self.P_feed is not None:
            constraints.append(self.P_feed <= self.P_max)

        return constraints

    def rule_based_import(self, power: float) -> float:
        """Import power from grid in rule-based mode."""
        return min(power, self.P_max)

    def rule_based_export(self, power: float) -> float:
        """Export power to grid in rule-based mode."""
        return min(power, self.P_max)