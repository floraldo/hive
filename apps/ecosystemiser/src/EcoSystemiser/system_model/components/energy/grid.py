"""Grid component with MILP optimization support and hierarchical fidelity."""

from typing import Any, Dict, List

import cvxpy as cp
import numpy as np
from ecosystemiser.system_model.components.shared.archetypes import (
    FidelityLevel
    TransmissionTechnicalParams
)
from ecosystemiser.system_model.components.shared.component import (
    Component
    ComponentParams
)
from ecosystemiser.system_model.components.shared.registry import register_component
from hive_logging import get_logger
from pydantic import BaseModel, Field

logger = get_logger(__name__)

# =============================================================================
# GRID-SPECIFIC TECHNICAL PARAMETERS (Co-located with component)
# =============================================================================


class GridTechnicalParams(TransmissionTechnicalParams):
    """Grid-specific technical parameters extending transmission archetype.
from __future__ import annotations


    This model inherits from TransmissionTechnicalParams and adds grid-specific
    parameters for different fidelity levels.
    """

    # Economic parameters (should eventually move to economic block)
    import_tariff: float = Field(0.25, description="Import electricity price [$/kWh]")
    feed_in_tariff: float = Field(0.08, description="Export electricity price [$/kWh]")

    # STANDARD fidelity additions
    grid_losses: float | None = Field(None, description="Transmission loss factor [%]")

    # DETAILED fidelity parameters
    voltage_limits: Optional[Dict[str, float]] = Field(None, description="Voltage limits {min_pu, max_pu}")
    power_factor_limits: Optional[Dict[str, float]] = Field(None, description="Power factor requirements")

    # RESEARCH fidelity parameters
    grid_impedance_model: Optional[Dict[str, Any]] = Field(None, description="Detailed grid impedance model")


# =============================================================================
# PHYSICS STRATEGIES (Rule-Based & Fidelity)
# =============================================================================


class GridPhysicsSimple:
    """Implements the SIMPLE rule-based physics for grid transmission.

    This is the baseline fidelity level providing:
    - Basic import/export with power limits
    - No transmission losses
    - Direct power transfer
    """

    def __init__(self, params) -> None:
        """Initialize with component parameters."""
        self.params = params

    def rule_based_import(self, power_requested: float, max_import: float) -> float:
        """
        Calculate actual power import in SIMPLE mode.

        Args:
            power_requested: Power requested from grid [kW]
            max_import: Maximum import capacity [kW]

        Returns:
            Actual power imported [kW]
        """
        # Simple clipping to max import
        return min(power_requested, max_import)

    def rule_based_export(self, power_available: float, max_export: float) -> float:
        """
        Calculate actual power export in SIMPLE mode.

        Args:
            power_available: Power available for export [kW]
            max_export: Maximum export capacity [kW]

        Returns:
            Actual power exported [kW]
        """
        # Simple clipping to max export
        return min(power_available, max_export)


class GridPhysicsStandard(GridPhysicsSimple):
    """Implements the STANDARD rule-based physics for grid transmission.

    Inherits from SIMPLE and adds:
    - Transmission losses on import
    - Grid efficiency modeling
    """

    def rule_based_import(self, power_requested: float, max_import: float) -> float:
        """
        Calculate actual power import with transmission losses.

        First applies SIMPLE physics, then adds STANDARD-specific effects.
        """
        # 1. Get the baseline result from SIMPLE physics
        power_from_grid = super().rule_based_import(power_requested, max_import)

        # 2. Add STANDARD-specific physics: transmission losses
        grid_losses = getattr(self.params.technical, "grid_losses", 0.02)  # 2% default
        if grid_losses and grid_losses > 0:
            # Power delivered = power from grid * (1 - losses)
            power_delivered = power_from_grid * (1 - grid_losses)
            return power_delivered

        return power_from_grid


# =============================================================================
# OPTIMIZATION STRATEGY (MILP)
# =============================================================================


class GridOptimizationSimple:
    """Implements the SIMPLE MILP optimization constraints for grid.

    This is the baseline optimization strategy providing:
    - Basic import/export capacity constraints
    - No grid losses or power quality considerations
    """

    def __init__(self, params, component_instance) -> None:
        """Initialize with both params and component instance for constraint access."""
        self.params = params
        self.component = component_instance

    def set_constraints(self) -> list:
        """
        Create SIMPLE CVXPY constraints for grid optimization.

        Returns constraints for basic grid operation without losses.
        """
        constraints = []
        comp = self.component

        # SIMPLE MODEL: Basic capacity constraints only
        if comp.P_draw is not None:
            constraints.append(comp.P_draw <= comp.P_max_import)
        if comp.P_feed is not None:
            constraints.append(comp.P_feed <= comp.P_max_export)

        return constraints


class GridOptimizationStandard(GridOptimizationSimple):
    """Implements the STANDARD MILP optimization constraints for grid.

    Inherits from SIMPLE and adds:
    - Grid loss acknowledgment (for future system-level implementation)
    - Preparation for power quality constraints
    """

    def set_constraints(self) -> list:
        """
        Create STANDARD CVXPY constraints for grid optimization.

        Adds grid loss awareness to the constraints.
        """
        # Start with SIMPLE constraints
        constraints = super().set_constraints()
        comp = self.component

        # STANDARD: Acknowledge grid losses (actual implementation would be in energy balance)
        grid_losses = getattr(comp.technical, "grid_losses", None)
        if grid_losses and grid_losses > 0 and comp.P_draw is not None:
            logger.debug(f"STANDARD: Grid losses of {grid_losses*100:.1f}% acknowledged")
            # Note: Actual loss implementation would be in system-level energy balance
            # Could add: constraints.append(comp.P_draw_effective == comp.P_draw * (1 - grid_losses))

        return constraints


class GridParams(ComponentParams):
    """Grid parameters using the hierarchical technical parameter system."""

    technical: GridTechnicalParams = Field(
        default_factory=lambda: GridTechnicalParams(
            capacity_nominal=100.0,  # Default 100 kW capacity
            max_import=100.0,  # Default 100 kW import
            max_export=100.0,  # Default 100 kW export
            import_tariff=0.25
            feed_in_tariff=0.08
            fidelity_level=FidelityLevel.STANDARD
        )
        description="Technical parameters following the hierarchical archetype system"
    )


# =============================================================================
# MAIN COMPONENT CLASS (Factory)
# =============================================================================


@register_component("Grid")
class Grid(Component):
    """Grid connection component with Strategy Pattern architecture.

    This class acts as a factory and container for grid strategies:
    - Physics strategies: Handle fidelity-specific transmission calculations
    - Optimization strategies: Handle MILP constraint generation
    - Clean separation: Data contract + strategy selection only

    The component delegates physics and optimization to strategy objects
    based on the configured fidelity level.
    """

    PARAMS_MODEL = GridParams

    def _post_init(self) -> None:
        """Initialize grid attributes and strategy objects."""
        self.type = "transmission"
        self.medium = "electricity"

        # Extract parameters from technical block
        tech = self.technical

        # Core parameters - EXACTLY as original Grid expects
        self.P_max_import = tech.max_import  # kW
        self.P_max_export = tech.max_export  # kW
        # For backward compatibility, use the max of import/export as P_max
        self.P_max = max(tech.max_import, tech.max_export)

        # Economic parameters
        self.import_tariff = tech.import_tariff
        self.feed_in_tariff = tech.feed_in_tariff

        # Store advanced parameters for strategy access
        self.grid_losses = tech.grid_losses
        self.voltage_limits = tech.voltage_limits
        self.power_factor_limits = tech.power_factor_limits

        # CVXPY variables (created later by add_optimization_vars)
        self.P_draw = None  # Import from grid
        self.P_feed = None  # Export to grid

        # STRATEGY PATTERN: Instantiate the correct strategies
        self.physics = self._get_physics_strategy()
        self.optimization = self._get_optimization_strategy()

    def _get_physics_strategy(self):
        """Factory method: Select physics strategy based on fidelity level."""
        fidelity = self.technical.fidelity_level

        if fidelity == FidelityLevel.SIMPLE:
            return GridPhysicsSimple(self.params)
        elif fidelity == FidelityLevel.STANDARD:
            return GridPhysicsStandard(self.params)
        elif fidelity == FidelityLevel.DETAILED:
            # For now, DETAILED uses STANDARD physics (can be extended later)
            return GridPhysicsStandard(self.params)
        elif fidelity == FidelityLevel.RESEARCH:
            # For now, RESEARCH uses STANDARD physics (can be extended later)
            return GridPhysicsStandard(self.params)
        else:
            raise ValueError(f"Unknown fidelity level for Grid: {fidelity}")

    def _get_optimization_strategy(self):
        """Factory method: Select optimization strategy based on fidelity level."""
        fidelity = self.technical.fidelity_level

        if fidelity == FidelityLevel.SIMPLE:
            return GridOptimizationSimple(self.params, self)
        elif fidelity == FidelityLevel.STANDARD:
            return GridOptimizationStandard(self.params, self)
        elif fidelity == FidelityLevel.DETAILED:
            # For now, DETAILED uses STANDARD optimization (can be extended later)
            return GridOptimizationStandard(self.params, self)
        elif fidelity == FidelityLevel.RESEARCH:
            # For now, RESEARCH uses STANDARD optimization (can be extended later)
            return GridOptimizationStandard(self.params, self)
        else:
            raise ValueError(f"Unknown fidelity level for Grid optimization: {fidelity}")

    def add_optimization_vars(self, N: int) -> None:
        """Create CVXPY optimization variables."""
        self.P_draw = cp.Variable(N, name=f"{self.name}_P_draw", nonneg=True)
        self.P_feed = cp.Variable(N, name=f"{self.name}_P_feed", nonneg=True)

        # Add as flows
        self.flows["source"]["P_draw"] = {"type": "electricity", "value": self.P_draw}
        self.flows["sink"]["P_feed"] = {"type": "electricity", "value": self.P_feed}

    def set_constraints(self) -> List:
        """Delegate constraint creation to optimization strategy."""
        return self.optimization.set_constraints()

    def rule_based_import(self, power: float) -> float:
        """
        Delegate to physics strategy for import calculation.

        This maintains the same interface but delegates the actual
        physics calculation to the strategy object.
        """
        return self.physics.rule_based_import(power, self.P_max_import)

    def rule_based_export(self, power: float) -> float:
        """
        Delegate to physics strategy for export calculation.

        This maintains the same interface but delegates the actual
        physics calculation to the strategy object.
        """
        return self.physics.rule_based_export(power, self.P_max_export)
