"""Grid component with MILP optimization support and hierarchical fidelity."""
import cvxpy as cp
import numpy as np
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import logging

from ..shared.registry import register_component
from ..shared.component import Component, ComponentParams
from ..shared.archetypes import TransmissionTechnicalParams, FidelityLevel
from ..shared.base_classes import BaseOptimization

logger = logging.getLogger(__name__)


# =============================================================================
# GRID-SPECIFIC TECHNICAL PARAMETERS (Co-located with component)
# =============================================================================

class GridTechnicalParams(TransmissionTechnicalParams):
    """Grid-specific technical parameters extending transmission archetype.

    This model inherits from TransmissionTechnicalParams and adds grid-specific
    parameters for different fidelity levels.
    """
    # Economic parameters (should eventually move to economic block)
    import_tariff: float = Field(0.25, description="Import electricity price [$/kWh]")
    feed_in_tariff: float = Field(0.08, description="Export electricity price [$/kWh]")

    # STANDARD fidelity additions
    grid_losses: Optional[float] = Field(
        None,
        description="Transmission loss factor [%]"
    )

    # DETAILED fidelity parameters
    voltage_limits: Optional[Dict[str, float]] = Field(
        None,
        description="Voltage limits {min_pu, max_pu}"
    )
    power_factor_limits: Optional[Dict[str, float]] = Field(
        None,
        description="Power factor requirements"
    )

    # RESEARCH fidelity parameters
    grid_impedance_model: Optional[Dict[str, Any]] = Field(
        None,
        description="Detailed grid impedance model"
    )


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

    def __init__(self, params):
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
        grid_losses = getattr(self.params.technical, 'grid_losses', 0.02)  # 2% default
        if grid_losses and grid_losses > 0:
            # Power delivered = power from grid * (1 - losses)
            power_delivered = power_from_grid * (1 - grid_losses)
            return power_delivered

        return power_from_grid


# =============================================================================
# OPTIMIZATION STRATEGY (MILP)
# =============================================================================

class GridOptimization(BaseOptimization):
    """Handles the MILP (CVXPY) constraints for the grid.

    Encapsulates all optimization logic separately from physics and data.
    This enables clean separation and easy testing of optimization constraints.
    """

    def __init__(self, params, component_instance):
        """Initialize with both params and component instance for constraint access."""
        super().__init__(params)
        self.component = component_instance

    def set_constraints(self) -> list:
        """
        Create CVXPY constraints for grid optimization.

        This method encapsulates all the MILP constraint logic for grid transmission.
        """
        constraints = []
        comp = self.component

        # Get fidelity level
        fidelity = comp.technical.fidelity_level

        # BASIC CONSTRAINTS (always active)
        if comp.P_draw is not None:
            constraints.append(comp.P_draw <= comp.P_max_import)
        if comp.P_feed is not None:
            constraints.append(comp.P_feed <= comp.P_max_export)

        # STANDARD: Add grid losses
        if fidelity >= FidelityLevel.STANDARD:
            grid_losses = getattr(comp.technical, 'grid_losses', None)
            if grid_losses and grid_losses > 0 and comp.P_draw is not None:
                # Account for transmission losses on import
                # This could be modeled as an efficiency factor in the energy balance
                logger.debug(f"STANDARD: Grid losses of {grid_losses*100:.1f}% acknowledged")
                # Note: Actual loss implementation would be in system-level energy balance

        # DETAILED: Add power quality constraints
        if fidelity >= FidelityLevel.DETAILED:
            if comp.voltage_limits is not None:
                logger.debug("DETAILED: Voltage limit constraints would be added here")
                # In practice, this would require voltage variables

            if comp.power_factor_limits is not None:
                logger.debug("DETAILED: Power factor constraints would be added here")
                # This would require reactive power modeling

        # RESEARCH: Full grid modeling
        if fidelity >= FidelityLevel.RESEARCH:
            logger.debug("RESEARCH: Full grid impedance modeling would be added here")
            # Placeholder for detailed grid modeling

        return constraints


class GridParams(ComponentParams):
    """Grid parameters using the hierarchical technical parameter system."""
    technical: GridTechnicalParams = Field(
        default_factory=lambda: GridTechnicalParams(
            capacity_nominal=100.0,  # Default 100 kW capacity
            max_import=100.0,  # Default 100 kW import
            max_export=100.0,  # Default 100 kW export
            import_tariff=0.25,
            feed_in_tariff=0.08,
            fidelity_level=FidelityLevel.STANDARD
        ),
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

    def _post_init(self):
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
        """Factory method: Select optimization strategy."""
        # For now, all fidelity levels use the same optimization strategy
        # Future: Could have different optimization strategies per fidelity
        return GridOptimization(self.params, self)

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