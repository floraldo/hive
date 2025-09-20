"""MILP optimization solver using CVXPY."""
import cvxpy as cp
import numpy as np
import time
import logging
from .base import BaseSolver, SolverResult

logger = logging.getLogger(__name__)

class MILPSolver(BaseSolver):
    """Mixed Integer Linear Programming solver using CVXPY."""

    def __init__(self, system, config=None):
        super().__init__(system, config)
        self.problem = None
        self.objective_type = config.solver_specific.get('objective', 'min_cost') if config else 'min_cost'

    def prepare_system(self):
        """Initialize CVXPY variables for optimization."""
        logger.info("Preparing system for MILP optimization")

        # Ensure all flows have CVXPY variables
        for flow_key, flow_data in self.system.flows.items():
            if not isinstance(flow_data['value'], cp.Variable):
                flow_data['value'] = cp.Variable(
                    self.system.N,
                    nonneg=True,
                    name=flow_key
                )

        # Initialize storage variables
        for comp in self.system.components.values():
            if comp.type == "storage":
                # Call the placeholder method for future refactoring
                comp.add_optimization_vars()

                # For now, ensure E is a cvxpy variable
                if not hasattr(comp, 'E_opt'):
                    comp.E_opt = cp.Variable(
                        self.system.N,
                        nonneg=True,
                        name=f'{comp.name}_E'
                    )

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

            # Select solver based on availability
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
            comp_constraints = component.set_constraints()
            constraints.extend(comp_constraints)

        # System-level constraints (if any)
        if hasattr(self.system, 'system_constraints'):
            constraints.extend(self.system.system_constraints)

        # Energy balance constraints for each timestep
        for t in range(self.system.N):
            constraints.extend(self._create_balance_constraints(t))

        return constraints

    def _create_balance_constraints(self, t):
        """Create energy/water balance constraints for timestep t."""
        constraints = []

        # Group components by medium
        media_components = {}
        for comp in self.system.components.values():
            if comp.medium not in media_components:
                media_components[comp.medium] = []
            media_components[comp.medium].append(comp)

        # Create balance for each medium
        for medium, components in media_components.items():
            inflows = []
            outflows = []

            for comp in components:
                # Sum all flows into this component
                for flow_name, flow in comp.flows.get('input', {}).items():
                    if flow['type'] == medium and isinstance(flow['value'], cp.Variable):
                        inflows.append(flow['value'][t])

                for flow_name, flow in comp.flows.get('sink', {}).items():
                    if flow['type'] == medium and isinstance(flow['value'], cp.Variable):
                        inflows.append(flow['value'][t])

                # Sum all flows out of this component
                for flow_name, flow in comp.flows.get('output', {}).items():
                    if flow['type'] == medium and isinstance(flow['value'], cp.Variable):
                        outflows.append(flow['value'][t])

                for flow_name, flow in comp.flows.get('source', {}).items():
                    if flow['type'] == medium and isinstance(flow['value'], cp.Variable):
                        outflows.append(flow['value'][t])

            # Balance constraint: inflows == outflows
            if inflows and outflows:
                constraints.append(cp.sum(inflows) == cp.sum(outflows))

        return constraints

    def _create_objective(self):
        """Create optimization objective based on configuration."""
        if self.objective_type == "min_cost":
            return self._objective_min_cost()
        elif self.objective_type == "min_co2":
            return self._objective_min_co2()
        elif self.objective_type == "min_grid":
            return self._objective_min_grid()
        else:
            logger.warning(f"Unknown objective type: {self.objective_type}, using min_cost")
            return self._objective_min_cost()

    def _objective_min_cost(self):
        """Minimize total operational cost."""
        cost = 0

        # Grid costs
        for comp_name, comp in self.system.components.items():
            if comp.type == "transmission" and comp.medium == "electricity":
                # Import costs
                if 'P_draw' in comp.flows.get('source', {}):
                    flow = comp.flows['source']['P_draw']['value']
                    if isinstance(flow, cp.Variable):
                        cost += cp.sum(flow) * getattr(comp, 'import_tariff', 0.25)

                # Export revenue (negative cost)
                if 'P_feed' in comp.flows.get('sink', {}):
                    flow = comp.flows['sink']['P_feed']['value']
                    if isinstance(flow, cp.Variable):
                        cost -= cp.sum(flow) * getattr(comp, 'feed_in_tariff', 0.08)

        return cp.Minimize(cost)

    def _objective_min_co2(self):
        """Minimize CO2 emissions."""
        co2 = 0

        for comp in self.system.components.values():
            if hasattr(comp, 'environmental') and comp.environmental:
                co2_rate = comp.environmental.co2_operational
                # Sum all output flows from this component
                for flow_dict in comp.flows.values():
                    for flow in flow_dict.values():
                        if isinstance(flow['value'], cp.Variable):
                            co2 += cp.sum(flow['value']) * co2_rate

        return cp.Minimize(co2)

    def _objective_min_grid(self):
        """Minimize grid usage (both import and export)."""
        grid_usage = 0

        for comp in self.system.components.values():
            if comp.type == "transmission" and comp.medium == "electricity":
                # Penalize both import and export
                for flow_dict in comp.flows.values():
                    for flow in flow_dict.values():
                        if isinstance(flow['value'], cp.Variable):
                            grid_usage += cp.sum(flow['value'])

        return cp.Minimize(grid_usage)

    def _select_solver(self):
        """Select appropriate solver based on availability."""
        try:
            # Try GLPK first (open source)
            return cp.GLPK
        except:
            try:
                # Try CBC (open source)
                return cp.CBC
            except:
                # Fall back to default
                return None

    def extract_results(self):
        """Convert CVXPY variable values to numpy arrays."""
        if self.problem.status not in ['optimal', 'optimal_inaccurate']:
            logger.warning(f"Problem not optimal, status: {self.problem.status}")
            return

        # Extract flow values
        for flow_key, flow_data in self.system.flows.items():
            if isinstance(flow_data['value'], cp.Variable):
                flow_data['value'] = flow_data['value'].value

        # Extract storage levels
        for comp in self.system.components.values():
            if comp.type == "storage":
                if hasattr(comp, 'E_opt') and isinstance(comp.E_opt, cp.Variable):
                    comp.E = comp.E_opt.value