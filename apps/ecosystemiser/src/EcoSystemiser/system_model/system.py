"""System class - container for components and flows."""

from typing import Any, Dict, List

import cvxpy as cp
import numpy as np
from hive_logging import get_logger

logger = get_logger(__name__)


class System:
    """Container class for system components and their connections."""
from __future__ import annotations


    def __init__(self, system_id: str, n: int = 24) -> None:
        """Initialize system.

        Args:
            system_id: Unique identifier for this system
            n: Number of timesteps
        """
        self.system_id = system_id
        self.N = n

        # Component and flow dictionaries
        self.components = {}
        self.flows = {}

        # Constraints for optimization
        self.constraints = []
        self.system_constraints = []  # System-level constraints

        # Optimization problem (for MILP solver)
        self.objective = None
        self.problem = None

        # Flow type definitions
        self.flow_types = {
            "electricity": {"unit": "kWh", "color": "#FFA500"},  # Orange
            "heat": {"unit": "kWh", "color": "#FF0000"},  # Red
            "water": {"unit": "m³", "color": "#0000FF"},  # Blue
        }

        # Tracking totals (for objective functions)
        self.total_energy = 0
        self.total_co2 = 0
        self.total_cost = 0

    def add_component(self, component) -> None:
        """Add a component to the system.

        Args:
            component: Component instance to add
        """
        self.components[component.name] = component
        logger.debug(f"Added component: {component.name} ({component.type})")

    def remove_component(self, component_name: str) -> None:
        """Remove a component from the system.

        Args:
            component_name: Name of component to remove
        """
        if component_name in self.components:
            self.components.pop(component_name)
            # Also remove associated flows
            flows_to_remove = [
                k for k, v in self.flows.items() if v["source"] == component_name or v["target"] == component_name
            ]
            for flow_key in flows_to_remove:
                del self.flows[flow_key]

            logger.debug(f"Removed component: {component_name}")

    def connect(
        self
        component1_name: str
        component2_name: str
        flow_type: str
        bidirectional: bool = False
    ):
        """Create a connection between two components.

        Args:
            component1_name: Source component name
            component2_name: Target component name
            flow_type: Type of flow ('electricity', 'heat', 'water')
            bidirectional: If True, create flow in both directions
        """
        if flow_type not in self.flow_types:
            raise ValueError(f"Invalid flow type: {flow_type}. Must be one of: {list(self.flow_types.keys())}")

        if component1_name not in self.components:
            raise ValueError(f"Component not found: {component1_name}")
        if component2_name not in self.components:
            raise ValueError(f"Component not found: {component2_name}")

        component1 = self.components[component1_name]
        component2 = self.components[component2_name]

        # Determine flow variable name based on medium
        var_prefix = "W" if flow_type == "water" else "P"

        # Create flow dictionary entry
        flow_key = f"{component1_name}_{var_prefix}_{component2_name}"
        flow = {
            "source": component1_name
            "target": component2_name
            "type": flow_type
            "unit": self.flow_types[flow_type]["unit"]
            "color": self.flow_types[flow_type]["color"]
            "value": np.zeros(self.N),  # Initialize as numpy array
        }

        # Add to system flows
        self.flows[flow_key] = flow

        # Add references to component flow dictionaries
        # Source component outputs to target
        if "output" not in component1.flows:
            component1.flows["output"] = {}
        component1.flows["output"][f"{var_prefix}_{component2_name}"] = flow

        # Target component receives input from source
        if "input" not in component2.flows:
            component2.flows["input"] = {}
        component2.flows["input"][f"{var_prefix}_{component1_name}"] = flow

        # Handle special component types
        if component1.type == "transmission":
            if "source" not in component1.flows:
                component1.flows["source"] = {}
            component1.flows["source"][f"{var_prefix}_draw"] = flow

        if component2.type == "transmission":
            if "sink" not in component2.flows:
                component2.flows["sink"] = {}
            component2.flows["sink"][f"{var_prefix}_feed"] = flow

        logger.debug(f"Connected {component1_name} -> {component2_name} ({flow_type})")

        # Handle bidirectional connection
        if bidirectional:
            self.connect(component2_name, component1_name, flow_type, bidirectional=False)

    def get_flows_by_type(self, flow_type: str) -> Dict[str, Any]:
        """Get all flows of a specific type.

        Args:
            flow_type: Type of flow to filter

        Returns:
            Dictionary of flows of the specified type
        """
        return {k: v for k, v in self.flows.items() if v["type"] == flow_type}

    def get_component_by_type(self, component_type: str) -> List:
        """Get all components of a specific type.

        Args:
            component_type: Type of component to filter

        Returns:
            List of components of the specified type
        """
        return [comp for comp in self.components.values() if comp.type == component_type]

    def validate_connections(self) -> List[str]:
        """Validate that all components have appropriate connections.

        Returns:
            List of validation issues (empty if valid)
        """
        issues = []

        for comp_name, component in self.components.items():
            # Check that generation components have outputs
            if component.type == "generation":
                has_output = any(f["source"] == comp_name for f in self.flows.values())
                if not has_output:
                    issues.append(f"Generation component {comp_name} has no output connections")

            # Check that consumption components have inputs
            elif component.type == "consumption":
                has_input = any(f["target"] == comp_name for f in self.flows.values())
                if not has_input:
                    issues.append(f"Consumption component {comp_name} has no input connections")

        return issues

    def get_system_info(self) -> Dict[str, Any]:
        """Get summary information about the system.

        Returns:
            Dictionary with system information
        """
        info = {
            "system_id": self.system_id
            "timesteps": self.N
            "num_components": len(self.components)
            "num_flows": len(self.flows)
            "component_types": {}
            "flow_types": {}
        }

        # Count components by type
        for component in self.components.values():
            comp_type = component.type
            info["component_types"][comp_type] = info["component_types"].get(comp_type, 0) + 1

        # Count flows by type
        for flow in self.flows.values():
            flow_type = flow["type"]
            info["flow_types"][flow_type] = info["flow_types"].get(flow_type, 0) + 1

        return info

    def prepare_for_optimization(self) -> None:
        """Prepare system for optimization solving.

        This method initializes CVXPY variables for flows and calls
        add_optimization_vars on all components.
        """
        # Convert flow values to CVXPY variables
        for flow_key, flow_data in self.flows.items():
            if not isinstance(flow_data["value"], cp.Variable):
                flow_data["value"] = cp.Variable(self.N, nonneg=True, name=flow_key)

        # Initialize component optimization variables
        for component in self.components.values():
            component.add_optimization_vars()

        logger.debug("System prepared for optimization")

    def create_balance_constraints(self) -> List:
        """Create energy/material balance constraints.

        Returns:
            List of constraints
        """
        constraints = []

        # Get constraints from all components
        for component in self.components.values():
            comp_constraints = component.set_constraints()
            constraints.extend(comp_constraints)

        # Add system-level constraints
        constraints.extend(self.system_constraints)

        self.constraints = constraints
        return constraints

    def get_objective_contributions(self, objective_type: str) -> Dict[str, Any]:
        """Get objective function contributions based on objective type.

        This is the main interface for solvers to get component contributions
        for aggregation into the overall objective function. This maintains
        clear separation: System knows component costs, Solver aggregates them.

        Args:
            objective_type: Type of objective ('min_cost', 'min_co2', 'min_grid')

        Returns:
            Dictionary of component contributions to the objective
        """
        if objective_type == "min_cost":
            return self.get_component_cost_contributions()
        elif objective_type == "min_co2":
            return self.get_component_emission_contributions()
        elif objective_type == "min_grid":
            return self.get_component_grid_usage()
        else:
            raise ValueError(f"Unknown objective type: {objective_type}")

    def get_component_cost_contributions(self, timestep: int | None = None) -> Dict[str, Any]:
        """Get cost contributions from all components.

        The System exposes component cost contributions for the solver to aggregate.
        This maintains clear separation: System knows component costs, Solver aggregates them.

        Args:
            timestep: Specific timestep to get costs for, None for all timesteps

        Returns:
            Dictionary of component cost contributions
        """
        cost_contributions = {}

        for comp_name, component in self.components.items():
            comp_costs = {}

            # Transmission costs (Grid) - always included
            if component.type == "transmission":
                if hasattr(component, "import_tariff"):
                    comp_costs["import_cost"] = {
                        "rate": component.import_tariff
                        "variable": getattr(component, "P_draw", None),  # Grid import variable
                    }
                if hasattr(component, "feed_in_tariff"):
                    comp_costs["export_revenue"] = {
                        "rate": -component.feed_in_tariff,  # Negative cost (revenue)
                        "variable": getattr(component, "P_feed", None),  # Grid export variable
                    }

            # Other operational costs (for components with economic params)
            elif hasattr(component, "economic") and component.economic:
                # Generation costs
                if component.type == "generation" and hasattr(component, "operating_cost"):
                    comp_costs["generation_cost"] = {
                        "rate": component.operating_cost
                        "variable": getattr(component, "P_gen", None)
                    }

                # Storage degradation costs
                if component.type == "storage" and hasattr(component, "degradation_cost"):
                    comp_costs["degradation_cost"] = {
                        "rate": component.degradation_cost
                        "variable": getattr(component, "P_cha", None),  # Cost per charge cycle
                    }

                # Variable operational costs for all flows
                if hasattr(component.economic, "opex_var") and component.economic.opex_var > 0:
                    for flow_dict in component.flows.values():
                        for flow_name, flow in flow_dict.items():
                            if "value" in flow and flow["value"] is not None:
                                comp_costs[f"{flow_name}_variable"] = {
                                    "rate": component.economic.opex_var
                                    "variable": flow["value"]
                                }

            if comp_costs:
                cost_contributions[comp_name] = comp_costs

        return cost_contributions

    def get_component_emission_contributions(self, timestep: int | None = None) -> Dict[str, Any]:
        """Get emission contributions from all components.

        Args:
            timestep: Specific timestep to get emissions for, None for all timesteps

        Returns:
            Dictionary of component emission contributions
        """
        emission_contributions = {}

        for comp_name, component in self.components.items():
            comp_emissions = {}

            if hasattr(component, "environmental") and component.environmental:
                # Grid import emissions
                if component.type == "transmission" and hasattr(component, "grid_emission_factor"):
                    comp_emissions["grid_emissions"] = {
                        "factor": component.grid_emission_factor,  # kg CO2/kWh
                        "variable": getattr(component, "P_import", None)
                    }

                # Generation emissions
                if component.type == "generation" and hasattr(component, "emission_factor"):
                    comp_emissions["generation_emissions"] = {
                        "factor": component.emission_factor
                        "variable": getattr(component, "P_gen", None)
                    }

                # Operational emissions for all flows
                if hasattr(component.environmental, "co2_operational") and component.environmental.co2_operational > 0:
                    for flow_dict in component.flows.values():
                        for flow_name, flow in flow_dict.items():
                            if "value" in flow and flow["value"] is not None:
                                comp_emissions[f"{flow_name}_operational"] = {
                                    "factor": component.environmental.co2_operational
                                    "variable": flow["value"]
                                }

            if comp_emissions:
                emission_contributions[comp_name] = comp_emissions

        return emission_contributions

    def get_component_grid_usage(self) -> Dict[str, Any]:
        """Get grid usage from transmission components.

        Returns:
            Dictionary of grid usage variables for minimization
        """
        grid_usage = {}

        for comp_name, component in self.components.items():
            if component.type == "transmission" and component.medium == "electricity":
                comp_usage = {}

                if hasattr(component, "P_import"):
                    comp_usage["import"] = getattr(component, "P_import", None)
                if hasattr(component, "P_export"):
                    comp_usage["export"] = getattr(component, "P_export", None)

                # Include all electricity flows for grid components
                for flow_dict in component.flows.values():
                    for flow_name, flow in flow_dict.items():
                        if "value" in flow and flow["value"] is not None:
                            comp_usage[flow_name] = flow["value"]

                if comp_usage:
                    grid_usage[comp_name] = comp_usage

        return grid_usage

    def validate_objective_contributions(self, objective_type: str) -> List[str]:
        """Validate that components have necessary data for the specified objective.

        Args:
            objective_type: Type of objective to validate

        Returns:
            List of validation warnings
        """
        warnings = []
        contributions = self.get_objective_contributions(objective_type)

        if not contributions:
            warnings.append(f"No components contribute to {objective_type} objective")

        # Check for missing data
        for comp_name, comp_data in contributions.items():
            for contrib_type, contrib_data in comp_data.items():
                if contrib_data.get("variable") is None:
                    warnings.append(f"Component {comp_name} {contrib_type} has no optimization variable")

        return warnings

    def __repr__(self):
        """String representation of system."""
        return f"System(id='{self.system_id}', " f"components={len(self.components)}, " f"flows={len(self.flows)})"
