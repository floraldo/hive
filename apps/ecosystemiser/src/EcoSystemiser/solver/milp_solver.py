"""MILP optimization solver using CVXPY - Version 2 with full implementation."""
from typing import Dict, Any
import cvxpy as cp
import numpy as np
import time
from EcoSystemiser.hive_logging_adapter import get_logger
from .base import BaseSolver, SolverResult

logger = get_logger(__name__)

class MILPSolver(BaseSolver):
    """Mixed Integer Linear Programming solver using CVXPY."""

    def __init__(self, system, config=None):
        super().__init__(system, config)
        self.problem = None
        self.objective_type = config.solver_specific.get('objective', 'min_cost') if config else 'min_cost'

    def prepare_system(self):
        """Initialize CVXPY variables for optimization."""
        logger.info("Preparing system for MILP optimization")

        # Initialize optimization variables for all components
        for comp in self.system.components.values():
            if hasattr(comp, 'add_optimization_vars'):
                comp.add_optimization_vars(self.system.N)
                logger.debug(f"Added optimization variables for {comp.name}")

        # Connect flow variables between components
        self._connect_flow_variables()

    def _connect_flow_variables(self):
        """Connect component variables to system flows - matching original Systemiser."""
        # First create variables for all system flows
        for flow_key, flow_data in self.system.flows.items():
            # Create a CVXPY variable for this flow
            flow_var = cp.Variable(
                self.system.N,
                nonneg=True,
                name=flow_key
            )
            flow_data['value'] = flow_var

            # Now update the input/output flow references in components
            source_comp = self.system.components.get(flow_data['source'])
            target_comp = self.system.components.get(flow_data['target'])

            # Determine prefix
            var_prefix = 'W' if flow_data['type'] == 'water' else 'P'

            # Update source component's output flow
            if source_comp and 'output' in source_comp.flows:
                output_key = f'{var_prefix}_{flow_data["target"]}'
                if output_key in source_comp.flows['output']:
                    source_comp.flows['output'][output_key]['value'] = flow_var

            # Update target component's input flow
            if target_comp and 'input' in target_comp.flows:
                input_key = f'{var_prefix}_{flow_data["source"]}'
                if input_key in target_comp.flows['input']:
                    target_comp.flows['input'][input_key]['value'] = flow_var

    def solve(self) -> SolverResult:
        """Solve the optimization problem."""
        start_time = time.time()

        try:
            # Prepare system
            self.prepare_system()

            # Create constraints
            constraints = self._create_constraints()

            # Create objective
            objective = self._create_objective()

            # Create and solve problem
            self.problem = cp.Problem(objective, constraints)

            # Select solver
            solver = self._select_solver()
            self.problem.solve(solver=solver, verbose=self.config.verbose)

            # Extract results
            self.extract_results()

            # Determine status
            if self.problem.status == 'optimal':
                status = 'optimal'
                message = 'Optimal solution found'
            elif self.problem.status == 'infeasible':
                status = 'infeasible'
                message = 'Problem is infeasible'
            else:
                status = 'error'
                message = f'Solver status: {self.problem.status}'

            result = SolverResult(
                status=status,
                objective_value=self.problem.value,
                solve_time=time.time() - start_time,
                message=message
            )

        except Exception as e:
            logger.error(f"Error in MILP solver: {e}")
            result = SolverResult(
                status="error",
                solve_time=time.time() - start_time,
                message=str(e)
            )

        self.result = result
        return result

    def _create_constraints(self):
        """Create all system constraints."""
        constraints = []

        # Component constraints
        for component in self.system.components.values():
            if hasattr(component, 'set_constraints'):
                comp_constraints = component.set_constraints()
                constraints.extend(comp_constraints)
                logger.debug(f"Added {len(comp_constraints)} constraints for {component.name}")

        # Energy balance constraints
        constraints.extend(self._create_balance_constraints())

        logger.info(f"Total constraints: {len(constraints)}")
        return constraints

    def _create_balance_constraints(self):
        """Create balance constraints for each timestep and medium type (electricity, heat, water)."""
        constraints = []

        for t in range(self.system.N):
            # Separate flows by medium type (electricity, heat, water)
            flows_by_type = {
                'electricity': {'generation': [], 'consumption': [], 'storage_charge': [],
                               'storage_discharge': [], 'import': [], 'export': []},
                'heat': {'generation': [], 'consumption': [], 'storage_charge': [],
                        'storage_discharge': [], 'import': [], 'export': []},
                'water': {'generation': [], 'consumption': [], 'storage_charge': [],
                         'storage_discharge': [], 'import': [], 'export': []}
            }

            for comp in self.system.components.values():
                # Get component medium type
                medium = getattr(comp, 'medium', 'electricity')

                # Generation components
                if comp.type == "generation":
                    for flow_name, flow in comp.flows.get('source', {}).items():
                        if isinstance(flow.get('value'), cp.Variable):
                            flow_type = flow.get('type', medium)
                            if flow_type in flows_by_type:
                                flows_by_type[flow_type]['generation'].append(flow['value'][t])

                # Consumption components
                elif comp.type == "consumption":
                    for flow_name, flow in comp.flows.get('sink', {}).items():
                        if isinstance(flow.get('value'), cp.Variable):
                            flow_type = flow.get('type', medium)
                            if flow_type in flows_by_type:
                                flows_by_type[flow_type]['consumption'].append(flow['value'][t])

                # Storage components
                elif comp.type == "storage":
                    # Check for electrical storage
                    if medium == 'electricity':
                        if hasattr(comp, 'P_cha') and comp.P_cha is not None:
                            flows_by_type['electricity']['storage_charge'].append(comp.P_cha[t])
                        if hasattr(comp, 'P_dis') and comp.P_dis is not None:
                            flows_by_type['electricity']['storage_discharge'].append(comp.P_dis[t])
                    # Check for thermal storage
                    elif medium == 'heat':
                        if hasattr(comp, 'P_cha') and comp.P_cha is not None:
                            flows_by_type['heat']['storage_charge'].append(comp.P_cha[t])
                        if hasattr(comp, 'P_dis') and comp.P_dis is not None:
                            flows_by_type['heat']['storage_discharge'].append(comp.P_dis[t])
                    # Check for water storage
                    elif medium == 'water':
                        if hasattr(comp, 'Q_in') and comp.Q_in is not None:
                            flows_by_type['water']['storage_charge'].append(comp.Q_in[t])
                        if hasattr(comp, 'Q_out') and comp.Q_out is not None:
                            flows_by_type['water']['storage_discharge'].append(comp.Q_out[t])

                # Grid components (electricity and water)
                elif comp.type == "transmission":
                    if medium == 'electricity':
                        if hasattr(comp, 'P_draw') and comp.P_draw is not None:
                            flows_by_type['electricity']['import'].append(comp.P_draw[t])
                        if hasattr(comp, 'P_feed') and comp.P_feed is not None:
                            flows_by_type['electricity']['export'].append(comp.P_feed[t])
                    elif medium == 'water':
                        if hasattr(comp, 'Q_import') and comp.Q_import is not None:
                            flows_by_type['water']['import'].append(comp.Q_import[t])
                        if hasattr(comp, 'Q_export') and comp.Q_export is not None:
                            flows_by_type['water']['export'].append(comp.Q_export[t])

                # Components that convert between energy types
                # Heat pumps and boilers consume electricity (sink) and produce heat (source)
                for flow_name, flow in comp.flows.get('sink', {}).items():
                    if isinstance(flow.get('value'), cp.Variable):
                        flow_type = flow.get('type', 'electricity')
                        if flow_type in flows_by_type and comp.type == "generation":
                            # This is electricity input to heat generators
                            flows_by_type[flow_type]['consumption'].append(flow['value'][t])

            # Create balance constraints for each medium type
            for medium_type, flows in flows_by_type.items():
                lhs = []
                rhs = []

                # Left hand side (sources)
                lhs.extend(flows['generation'])
                lhs.extend(flows['import'])
                lhs.extend(flows['storage_discharge'])

                # Right hand side (sinks)
                rhs.extend(flows['consumption'])
                rhs.extend(flows['export'])
                rhs.extend(flows['storage_charge'])

                # Only add constraint if there are flows for this medium type
                if lhs and rhs:
                    constraints.append(cp.sum(lhs) == cp.sum(rhs))

        return constraints

    def _create_objective(self):
        """Create optimization objective based on system contributions.

        The MILPSolver now aggregates component contributions from the System
        instead of implementing its own objective logic. This maintains clear
        separation of concerns.
        """
        # Validate that system has contributions for this objective
        warnings = self.system.validate_objective_contributions(self.objective_type)
        if warnings:
            for warning in warnings:
                logger.warning(warning)

        # Get component contributions from system
        contributions = self.system.get_objective_contributions(self.objective_type)

        if not contributions:
            logger.warning(f"No contributions for {self.objective_type}, creating zero objective")
            return cp.Minimize(0)

        # Aggregate contributions based on objective type
        if self.objective_type == "min_cost":
            return self._aggregate_cost_contributions(contributions)
        elif self.objective_type == "min_co2":
            return self._aggregate_emission_contributions(contributions)
        elif self.objective_type == "min_grid":
            return self._aggregate_grid_contributions(contributions)
        elif self.objective_type.startswith("multi_"):
            return self._aggregate_multi_objective_contributions(contributions)
        else:
            logger.warning(f"Unknown objective type: {self.objective_type}, using min_cost")
            return self._aggregate_cost_contributions(contributions)

    def _aggregate_cost_contributions(self, contributions: Dict[str, Any]):
        """Aggregate cost contributions from all components.

        Args:
            contributions: Component cost contributions from system

        Returns:
            CVXPY Minimize objective
        """
        total_cost = 0

        for comp_name, comp_costs in contributions.items():
            for cost_type, cost_data in comp_costs.items():
                rate = cost_data.get('rate', 0)
                variable = cost_data.get('variable')

                if variable is not None and rate != 0:
                    # Add cost contribution: rate * sum(variable)
                    if hasattr(variable, '__len__'):  # Array-like
                        total_cost += cp.sum(variable) * rate
                    else:  # Scalar
                        total_cost += variable * rate

                    logger.debug(f"Added {cost_type} from {comp_name}: rate={rate}")

        return cp.Minimize(total_cost)

    def _aggregate_emission_contributions(self, contributions: Dict[str, Any]):
        """Aggregate emission contributions from all components.

        Args:
            contributions: Component emission contributions from system

        Returns:
            CVXPY Minimize objective
        """
        total_emissions = 0

        for comp_name, comp_emissions in contributions.items():
            for emission_type, emission_data in comp_emissions.items():
                factor = emission_data.get('factor', 0)
                variable = emission_data.get('variable')

                if variable is not None and factor > 0:
                    # Add emission contribution: factor * sum(variable)
                    if hasattr(variable, '__len__'):  # Array-like
                        total_emissions += cp.sum(variable) * factor
                    else:  # Scalar
                        total_emissions += variable * factor

                    logger.debug(f"Added {emission_type} from {comp_name}: factor={factor} kg CO2/kWh")

        return cp.Minimize(total_emissions)

    def _aggregate_grid_contributions(self, contributions: Dict[str, Any]):
        """Aggregate grid usage contributions from transmission components.

        Args:
            contributions: Component grid usage contributions from system

        Returns:
            CVXPY Minimize objective
        """
        total_grid_usage = 0

        for comp_name, comp_usage in contributions.items():
            for usage_type, variable in comp_usage.items():
                if variable is not None:
                    # Add grid usage: sum(variable)
                    if hasattr(variable, '__len__'):  # Array-like
                        total_grid_usage += cp.sum(variable)
                    else:  # Scalar
                        total_grid_usage += variable

                    logger.debug(f"Added {usage_type} grid usage from {comp_name}")

        return cp.Minimize(total_grid_usage)

    def _aggregate_multi_objective_contributions(self, contributions: Dict[str, Any]):
        """Aggregate multiple objectives with weighted combination.

        Uses configured weights from config.objective_weights or parses from
        objective type name as fallback for backward compatibility.

        Args:
            contributions: Component contributions from system

        Returns:
            CVXPY Minimize objective with weighted combination
        """
        # First check if we have configured weights
        if self.config.objective_weights:
            # Use configured weights (preferred method)
            weights = self.config.objective_weights

            # Validate weights
            if not weights or sum(weights.values()) == 0:
                logger.error("Invalid objective weights configuration")
                return self._aggregate_cost_contributions(contributions)

            # Normalize weights if requested
            if self.config.normalize_objectives:
                total_weight = sum(weights.values())
                weights = {k: v/total_weight for k, v in weights.items()}

            # Build combined objective
            combined_objective = 0
            for obj_type, weight in weights.items():
                if weight > 0:
                    obj_value = self._get_single_objective_value(obj_type, contributions)
                    combined_objective += weight * obj_value
                    logger.debug(f"Added {weight:.1%} of {obj_type} to objective")

            logger.info(f"Multi-objective with configured weights: {weights}")
            return cp.Minimize(combined_objective)

        else:
            # Fallback: Parse from objective type name for backward compatibility
            parts = self.objective_type.split('_')
            if len(parts) < 5:
                logger.error(f"Invalid multi-objective format: {self.objective_type}")
                logger.info("Use config.objective_weights to specify weights properly")
                return self._aggregate_cost_contributions(contributions)

            obj1, obj2 = parts[1], parts[2]
            try:
                weight1, weight2 = float(parts[3]), float(parts[4])
                # Normalize weights
                total_weight = weight1 + weight2
                weight1, weight2 = weight1/total_weight, weight2/total_weight
            except (ValueError, ZeroDivisionError):
                logger.error(f"Invalid weights in multi-objective: {self.objective_type}")
                weight1, weight2 = 0.5, 0.5

            # Get individual objective values
            obj1_value = self._get_single_objective_value(obj1, contributions)
            obj2_value = self._get_single_objective_value(obj2, contributions)

            # Weighted combination
            combined_objective = weight1 * obj1_value + weight2 * obj2_value

            logger.info(f"Multi-objective (legacy format): {weight1:.1%} {obj1} + {weight2:.1%} {obj2}")
            return cp.Minimize(combined_objective)

    def _get_single_objective_value(self, objective_type: str, contributions: Dict[str, Any]):
        """Get objective value for single objective type."""
        if objective_type == "cost":
            cost_contribs = self.system.get_component_cost_contributions()
            total = 0
            for comp_costs in cost_contribs.values():
                for cost_data in comp_costs.values():
                    rate = cost_data.get('rate', 0)
                    variable = cost_data.get('variable')
                    if variable is not None and rate != 0:
                        if hasattr(variable, '__len__'):
                            total += cp.sum(variable) * rate
                        else:
                            total += variable * rate
            return total

        elif objective_type == "co2":
            emission_contribs = self.system.get_component_emission_contributions()
            total = 0
            for comp_emissions in emission_contribs.values():
                for emission_data in comp_emissions.values():
                    factor = emission_data.get('factor', 0)
                    variable = emission_data.get('variable')
                    if variable is not None and factor > 0:
                        if hasattr(variable, '__len__'):
                            total += cp.sum(variable) * factor
                        else:
                            total += variable * factor
            return total

        elif objective_type == "grid":
            grid_usage = self.system.get_component_grid_usage()
            total = 0
            for comp_usage in grid_usage.values():
                for variable in comp_usage.values():
                    if variable is not None:
                        if hasattr(variable, '__len__'):
                            total += cp.sum(variable)
                        else:
                            total += variable
            return total

        else:
            logger.warning(f"Unknown single objective type: {objective_type}")
            return 0

    def _select_solver(self):
        """Select appropriate solver based on availability."""
        try:
            # Try GLPK first (open source)
            import cvxpy.settings as s
            if s.GLPK in cp.installed_solvers():
                return cp.GLPK
        except:
            pass

        try:
            # Try CBC (open source)
            import cvxpy.settings as s
            if s.CBC in cp.installed_solvers():
                return cp.CBC
        except:
            pass

        # Fall back to default
        logger.info("Using default CVXPY solver")
        return None

    def extract_results(self):
        """Convert CVXPY variable values to numpy arrays."""
        if self.problem.status not in ['optimal', 'optimal_inaccurate']:
            logger.warning(f"Problem not optimal, status: {self.problem.status}")
            return

        logger.info("Extracting optimization results")

        # Extract component variable values
        for comp in self.system.components.values():
            # Battery storage levels
            if comp.type == "storage":
                if hasattr(comp, 'E_opt') and isinstance(comp.E_opt, cp.Variable):
                    comp.E = comp.E_opt.value
                    logger.debug(f"Extracted storage levels for {comp.name}")

                if hasattr(comp, 'P_cha') and isinstance(comp.P_cha, cp.Variable):
                    comp.P_charge = comp.P_cha.value

                if hasattr(comp, 'P_dis') and isinstance(comp.P_dis, cp.Variable):
                    comp.P_discharge = comp.P_dis.value

            # Grid flows
            elif comp.type == "transmission":
                if hasattr(comp, 'P_draw') and isinstance(comp.P_draw, cp.Variable):
                    comp.P_import = comp.P_draw.value

                if hasattr(comp, 'P_feed') and isinstance(comp.P_feed, cp.Variable):
                    comp.P_export = comp.P_feed.value

            # Generation
            elif comp.type == "generation":
                if hasattr(comp, 'P_out') and isinstance(comp.P_out, cp.Variable):
                    comp.P_generation = comp.P_out.value

            # Consumption
            elif comp.type == "consumption":
                if hasattr(comp, 'P_in') and isinstance(comp.P_in, cp.Variable):
                    comp.P_consumption = comp.P_in.value

        # Extract flow values
        for flow_key, flow_data in self.system.flows.items():
            if isinstance(flow_data['value'], cp.Variable):
                flow_data['value'] = flow_data['value'].value
                logger.debug(f"Extracted flow values for {flow_key}")

        logger.info("Result extraction complete")