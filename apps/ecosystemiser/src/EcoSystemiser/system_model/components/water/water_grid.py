"""Water grid component with MILP optimization support and hierarchical fidelity."""

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
# WATER GRID-SPECIFIC TECHNICAL PARAMETERS (Co-located with component)
# =============================================================================


class WaterGridTechnicalParams(TransmissionTechnicalParams):
    """Water grid-specific technical parameters extending transmission archetype.
from __future__ import annotations


    This model inherits from TransmissionTechnicalParams and adds water grid-specific
    parameters for different fidelity levels.
    """

    # Water grid economic parameters (should eventually move to economic block)
    water_tariff: float = Field(1.5, description="Water import price [$/m³]")
    wastewater_tariff: float = Field(2.0, description="Wastewater discharge price [$/m³]")

    # Water-specific parameters
    supply_pressure_bar: float = Field(3.0, description="Supply water pressure [bar]")
    min_pressure_bar: float = Field(1.0, description="Minimum acceptable pressure [bar]")
    supply_reliability: float = Field(0.99, description="Grid supply reliability factor (0-1)")

    # STANDARD fidelity additions
    pressure_losses: Optional[Dict[str, float]] = Field(None, description="Pressure loss factors in distribution")
    water_quality_degradation: float | None = Field(None, description="Water quality degradation factor")

    # DETAILED fidelity parameters
    network_topology: Optional[Dict[str, Any]] = Field(None, description="Detailed network topology model")
    peak_demand_surcharge: Optional[Dict[str, float]] = Field(None, description="Peak demand pricing structure")

    # RESEARCH fidelity parameters
    hydraulic_model: Optional[Dict[str, Any]] = Field(None, description="Detailed hydraulic network model")
    contamination_tracking: Optional[Dict[str, Any]] = Field(None, description="Water contamination tracking model")


# =============================================================================
# PHYSICS STRATEGIES (Rule-Based & Fidelity)
# =============================================================================


class WaterGridPhysicsSimple:
    """Implements the SIMPLE rule-based physics for water grid transmission.

    This is the baseline fidelity level providing:
    - Basic import/export with flow limits
    - No pressure losses or reliability issues
    - Direct water transfer
    """

    def __init__(self, params) -> None:
        """Initialize with component parameters."""
        self.params = params

    def rule_based_import(self, water_demand: float, max_supply: float) -> float:
        """
        Calculate actual water import in SIMPLE mode.

        Args:
            water_demand: Water requested from grid [m³/h]
            max_supply: Maximum supply capacity [m³/h]

        Returns:
            Actual water imported [m³/h]
        """
        # Simple clipping to max supply
        return min(water_demand, max_supply)

    def rule_based_export(self, wastewater: float, max_discharge: float) -> float:
        """
        Calculate actual wastewater export in SIMPLE mode.

        Args:
            wastewater: Wastewater available for export [m³/h]
            max_discharge: Maximum discharge capacity [m³/h]

        Returns:
            Actual wastewater exported [m³/h]
        """
        # Simple clipping to max discharge
        return min(wastewater, max_discharge)


class WaterGridPhysicsStandard(WaterGridPhysicsSimple):
    """Implements the STANDARD rule-based physics for water grid transmission.

    Inherits from SIMPLE and adds:
    - Supply reliability constraints
    - Pressure loss considerations
    """

    def rule_based_import(self, water_demand: float, max_supply: float) -> float:
        """
        Calculate actual water import with reliability and pressure losses.

        First applies SIMPLE physics, then adds STANDARD-specific effects.
        """
        # 1. Get the baseline result from SIMPLE physics
        water_from_grid = super().rule_based_import(water_demand, max_supply)

        # 2. Add STANDARD-specific physics: reliability factor
        supply_reliability = getattr(self.params.technical, "supply_reliability", 0.99)
        if supply_reliability < 1.0:
            # Reduce effective capacity by reliability factor
            effective_supply = water_from_grid * supply_reliability
            return effective_supply

        return water_from_grid


# =============================================================================
# OPTIMIZATION STRATEGY (MILP)
# =============================================================================


class WaterGridOptimizationSimple:
    """Implements the SIMPLE MILP optimization constraints for water grid.

    This is the baseline optimization strategy providing:
    - Basic import/export capacity constraints
    - No reliability or pressure loss considerations
    """

    def __init__(self, params, component_instance) -> None:
        """Initialize with both params and component instance for constraint access."""
        self.params = params
        self.component = component_instance

    def set_constraints(self) -> list:
        """
        Create SIMPLE CVXPY constraints for water grid optimization.

        Returns constraints for basic water transmission without losses.
        """
        constraints = []
        comp = self.component

        # SIMPLE MODEL: Basic capacity constraints only
        if comp.Q_import is not None:
            # Import capacity constraints
            constraints.append(comp.Q_import <= comp.max_supply_m3h)

        if comp.Q_export is not None:
            # Export capacity constraints
            constraints.append(comp.Q_export <= comp.max_discharge_m3h)

        return constraints


class WaterGridOptimizationStandard(WaterGridOptimizationSimple):
    """Implements the STANDARD MILP optimization constraints for water grid.

    Inherits from SIMPLE and adds:
    - Supply reliability constraints
    - Preparation for pressure loss modeling
    """

    def set_constraints(self) -> list:
        """
        Create STANDARD CVXPY constraints for water grid optimization.

        Adds supply reliability to the constraints.
        """
        # Start with SIMPLE constraints
        constraints = super().set_constraints()
        comp = self.component

        # STANDARD: Add reliability constraints
        if comp.Q_import is not None and comp.supply_reliability < 1.0:
            # Reduce effective capacity by reliability factor
            effective_supply = comp.max_supply_m3h * comp.supply_reliability
            constraints.append(comp.Q_import <= effective_supply)

        return constraints


class WaterGridParams(ComponentParams):
    """Water grid parameters using the hierarchical technical parameter system."""

    technical: WaterGridTechnicalParams = Field(
        default_factory=lambda: WaterGridTechnicalParams(
            capacity_nominal=10.0,  # Default 10 m³/h capacity
            max_import=10.0,  # Default 10 m³/h import
            max_export=5.0,  # Default 5 m³/h discharge
            water_tariff=1.5
            wastewater_tariff=2.0
            fidelity_level=FidelityLevel.STANDARD
        )
        description="Technical parameters following the hierarchical archetype system"
    )


# =============================================================================
# MAIN COMPONENT CLASS (Factory)
# =============================================================================


@register_component("WaterGrid")
class WaterGrid(Component):
    """Water grid component with Strategy Pattern architecture.

    This class acts as a factory and container for water grid strategies:
    - Physics strategies: Handle fidelity-specific water transmission calculations
    - Optimization strategies: Handle MILP constraint generation
    - Clean separation: Data contract + strategy selection only

    The component delegates physics and optimization to strategy objects
    based on the configured fidelity level.
    """

    PARAMS_MODEL = WaterGridParams

    def _post_init(self) -> None:
        """Initialize water grid attributes and strategy objects."""
        self.type = "transmission"
        self.medium = "water"

        # Extract parameters from technical block
        tech = self.technical

        # Core parameters - EXACTLY as original WaterGrid expects (m³/h)
        self.max_supply_m3h = tech.max_import  # Maximum supply rate
        self.max_discharge_m3h = tech.max_export  # Maximum discharge rate
        self.water_price_per_m3 = tech.water_tariff
        self.wastewater_price_per_m3 = tech.wastewater_tariff

        # Store water grid-specific parameters
        self.supply_pressure_bar = tech.supply_pressure_bar
        self.min_pressure_bar = tech.min_pressure_bar
        self.supply_reliability = tech.supply_reliability
        self.pressure_losses = tech.pressure_losses
        self.water_quality_degradation = tech.water_quality_degradation

        # CVXPY variables (for MILP solver)
        self.Q_import = None  # Water imported from grid
        self.Q_export = None  # Water exported to grid (wastewater)

        # STRATEGY PATTERN: Instantiate the correct strategies
        self.physics = self._get_physics_strategy()
        self.optimization = self._get_optimization_strategy()

    def _get_physics_strategy(self):
        """Factory method: Select physics strategy based on fidelity level."""
        fidelity = self.technical.fidelity_level

        if fidelity == FidelityLevel.SIMPLE:
            return WaterGridPhysicsSimple(self.params)
        elif fidelity == FidelityLevel.STANDARD:
            return WaterGridPhysicsStandard(self.params)
        elif fidelity == FidelityLevel.DETAILED:
            # For now, DETAILED uses STANDARD physics (can be extended later)
            return WaterGridPhysicsStandard(self.params)
        elif fidelity == FidelityLevel.RESEARCH:
            # For now, RESEARCH uses STANDARD physics (can be extended later)
            return WaterGridPhysicsStandard(self.params)
        else:
            raise ValueError(f"Unknown fidelity level for WaterGrid: {fidelity}")

    def _get_optimization_strategy(self):
        """Factory method: Select optimization strategy based on fidelity level."""
        fidelity = self.technical.fidelity_level

        if fidelity == FidelityLevel.SIMPLE:
            return WaterGridOptimizationSimple(self.params, self)
        elif fidelity == FidelityLevel.STANDARD:
            return WaterGridOptimizationStandard(self.params, self)
        elif fidelity == FidelityLevel.DETAILED:
            # For now, DETAILED uses STANDARD optimization (can be extended later)
            return WaterGridOptimizationStandard(self.params, self)
        elif fidelity == FidelityLevel.RESEARCH:
            # For now, RESEARCH uses STANDARD optimization (can be extended later)
            return WaterGridOptimizationStandard(self.params, self)
        else:
            raise ValueError(f"Unknown fidelity level for WaterGrid optimization: {fidelity}")

    def add_optimization_vars(self, N: int | None = None) -> None:
        """Create CVXPY optimization variables."""
        if N is None:
            N = self.N

        self.Q_import = cp.Variable(N, name=f"{self.name}_import", nonneg=True)
        self.Q_export = cp.Variable(N, name=f"{self.name}_export", nonneg=True)

        # Add flows
        self.flows["source"]["Q_import"] = {"type": "water", "value": self.Q_import}
        self.flows["sink"]["Q_export"] = {"type": "water", "value": self.Q_export}

    def set_constraints(self) -> List:
        """Delegate constraint creation to optimization strategy."""
        return self.optimization.set_constraints()

    def get_operating_cost(self, timestep: int) -> float:
        """Calculate operating cost for water grid at given timestep.

        Args:
            timestep: Time index

        Returns:
            Operating cost [$]
        """
        if not hasattr(self, "Q_import") or self.Q_import is None:
            return 0.0

        # Water import cost
        import_cost = 0.0
        export_cost = 0.0

        if hasattr(self.Q_import, "value") and self.Q_import.value is not None:
            import_cost = self.Q_import.value[timestep] * self.water_price_per_m3

        if hasattr(self.Q_export, "value") and self.Q_export.value is not None:
            export_cost = self.Q_export.value[timestep] * self.wastewater_price_per_m3

        return import_cost + export_cost

    def get_total_cost(self) -> float:
        """Calculate total operating cost over all timesteps."""
        if not hasattr(self, "Q_import") or self.Q_import is None:
            return 0.0

        total_cost = 0.0

        if hasattr(self.Q_import, "value") and self.Q_import.value is not None:
            total_import_cost = np.sum(self.Q_import.value) * self.water_price_per_m3
            total_cost += total_import_cost

        if hasattr(self.Q_export, "value") and self.Q_export.value is not None:
            total_export_cost = np.sum(self.Q_export.value) * self.wastewater_price_per_m3
            total_cost += total_export_cost

        return total_cost

    def rule_based_operation(self, water_demand: float, wastewater_production: float, t: int) -> tuple:
        """
        Delegate to physics strategy for water grid operation.

        This maintains the same interface but delegates the actual
        physics calculation to the strategy object.
        """
        # Delegate import calculation to physics strategy
        actual_import = self.physics.rule_based_import(water_demand, self.max_supply_m3h)

        # Delegate export calculation to physics strategy
        actual_export = self.physics.rule_based_export(wastewater_production, self.max_discharge_m3h)

        return actual_import, actual_export

    def __repr__(self) -> None:
        """String representation."""
        return (
            f"WaterGrid(name='{self.name}', "
            f"max_supply={self.max_supply_m3h}m³/h, "
            f"max_discharge={self.max_discharge_m3h}m³/h, "
            f"fidelity={self.technical.fidelity_level.value})"
        )
