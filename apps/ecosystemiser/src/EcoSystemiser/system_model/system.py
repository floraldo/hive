"""System class - container for components and flows."""
import numpy as np
import cvxpy as cp
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

class System:
    """Container class for system components and their connections."""

    def __init__(self, system_id: str, n: int = 24):
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
            'electricity': {'unit': 'kWh', 'color': '#FFA500'},  # Orange
            'heat': {'unit': 'kWh', 'color': '#FF0000'},        # Red
            'water': {'unit': 'm³', 'color': '#0000FF'}         # Blue
        }

        # Tracking totals (for objective functions)
        self.total_energy = 0
        self.total_co2 = 0
        self.total_cost = 0

    def add_component(self, component):
        """Add a component to the system.

        Args:
            component: Component instance to add
        """
        self.components[component.name] = component
        logger.debug(f"Added component: {component.name} ({component.type})")

    def remove_component(self, component_name: str):
        """Remove a component from the system.

        Args:
            component_name: Name of component to remove
        """
        if component_name in self.components:
            self.components.pop(component_name)
            # Also remove associated flows
            flows_to_remove = [
                k for k, v in self.flows.items()
                if v['source'] == component_name or v['target'] == component_name
            ]
            for flow_key in flows_to_remove:
                del self.flows[flow_key]

            logger.debug(f"Removed component: {component_name}")

    def connect(self, component1_name: str, component2_name: str,
                flow_type: str, bidirectional: bool = False):
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
        var_prefix = 'W' if flow_type == 'water' else 'P'

        # Create flow dictionary entry
        flow_key = f'{component1_name}_{var_prefix}_{component2_name}'
        flow = {
            'source': component1_name,
            'target': component2_name,
            'type': flow_type,
            'unit': self.flow_types[flow_type]['unit'],
            'color': self.flow_types[flow_type]['color'],
            'value': np.zeros(self.N)  # Initialize as numpy array
        }

        # Add to system flows
        self.flows[flow_key] = flow

        # Add references to component flow dictionaries
        # Source component outputs to target
        if 'output' not in component1.flows:
            component1.flows['output'] = {}
        component1.flows['output'][f'{var_prefix}_{component2_name}'] = flow

        # Target component receives input from source
        if 'input' not in component2.flows:
            component2.flows['input'] = {}
        component2.flows['input'][f'{var_prefix}_{component1_name}'] = flow

        # Handle special component types
        if component1.type == 'transmission':
            if 'source' not in component1.flows:
                component1.flows['source'] = {}
            component1.flows['source'][f'{var_prefix}_draw'] = flow

        if component2.type == 'transmission':
            if 'sink' not in component2.flows:
                component2.flows['sink'] = {}
            component2.flows['sink'][f'{var_prefix}_feed'] = flow

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
        return {
            k: v for k, v in self.flows.items()
            if v['type'] == flow_type
        }

    def get_component_by_type(self, component_type: str) -> List:
        """Get all components of a specific type.

        Args:
            component_type: Type of component to filter

        Returns:
            List of components of the specified type
        """
        return [
            comp for comp in self.components.values()
            if comp.type == component_type
        ]

    def validate_connections(self) -> List[str]:
        """Validate that all components have appropriate connections.

        Returns:
            List of validation issues (empty if valid)
        """
        issues = []

        for comp_name, component in self.components.items():
            # Check that generation components have outputs
            if component.type == 'generation':
                has_output = any(
                    f['source'] == comp_name for f in self.flows.values()
                )
                if not has_output:
                    issues.append(f"Generation component {comp_name} has no output connections")

            # Check that consumption components have inputs
            elif component.type == 'consumption':
                has_input = any(
                    f['target'] == comp_name for f in self.flows.values()
                )
                if not has_input:
                    issues.append(f"Consumption component {comp_name} has no input connections")

        return issues

    def get_system_info(self) -> Dict[str, Any]:
        """Get summary information about the system.

        Returns:
            Dictionary with system information
        """
        info = {
            'system_id': self.system_id,
            'timesteps': self.N,
            'num_components': len(self.components),
            'num_flows': len(self.flows),
            'component_types': {},
            'flow_types': {}
        }

        # Count components by type
        for component in self.components.values():
            comp_type = component.type
            info['component_types'][comp_type] = info['component_types'].get(comp_type, 0) + 1

        # Count flows by type
        for flow in self.flows.values():
            flow_type = flow['type']
            info['flow_types'][flow_type] = info['flow_types'].get(flow_type, 0) + 1

        return info

    def prepare_for_optimization(self):
        """Prepare system for optimization solving.

        This method initializes CVXPY variables for flows and calls
        add_optimization_vars on all components.
        """
        # Convert flow values to CVXPY variables
        for flow_key, flow_data in self.flows.items():
            if not isinstance(flow_data['value'], cp.Variable):
                flow_data['value'] = cp.Variable(
                    self.N,
                    nonneg=True,
                    name=flow_key
                )

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

    def set_objective(self, objective_type: str):
        """Set the optimization objective.

        Args:
            objective_type: Type of objective ('min_cost', 'min_co2', 'min_grid')
        """
        if objective_type == "min_cost":
            self.objective = self._create_cost_objective()
        elif objective_type == "min_co2":
            self.objective = self._create_co2_objective()
        elif objective_type == "min_grid":
            self.objective = self._create_grid_objective()
        else:
            raise ValueError(f"Unknown objective type: {objective_type}")

    def _create_cost_objective(self):
        """Create cost minimization objective."""
        cost = 0

        # Add operational costs from all flows
        for component in self.components.values():
            if hasattr(component, 'economic') and component.economic:
                # Variable costs based on flows
                for flow_dict in component.flows.values():
                    for flow in flow_dict.values():
                        if isinstance(flow['value'], cp.Variable):
                            cost += cp.sum(flow['value']) * component.economic.opex_var

        return cp.Minimize(cost)

    def _create_co2_objective(self):
        """Create CO2 minimization objective."""
        co2 = 0

        for component in self.components.values():
            if hasattr(component, 'environmental') and component.environmental:
                # CO2 from operations
                for flow_dict in component.flows.values():
                    for flow in flow_dict.values():
                        if isinstance(flow['value'], cp.Variable):
                            co2 += cp.sum(flow['value']) * component.environmental.co2_operational

        return cp.Minimize(co2)

    def _create_grid_objective(self):
        """Create grid usage minimization objective."""
        grid_usage = 0

        for component in self.components.values():
            if component.type == "transmission" and component.medium == "electricity":
                for flow_dict in component.flows.values():
                    for flow in flow_dict.values():
                        if isinstance(flow['value'], cp.Variable):
                            grid_usage += cp.sum(flow['value'])

        return cp.Minimize(grid_usage)

    def __repr__(self):
        """String representation of system."""
        return (f"System(id='{self.system_id}', "
                f"components={len(self.components)}, "
                f"flows={len(self.flows)})")