"""MILP optimization solver using CVXPY - Version 2 with full implementation."""
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

        # Initialize optimization variables for all components
        for comp in self.system.components.values():
            if hasattr(comp, 'add_optimization_vars'):
                comp.add_optimization_vars(self.system.N)
                logger.debug(f"Added optimization variables for {comp.name}")

        # Connect flow variables between components
        self._connect_flow_variables()

    def _connect_flow_variables(self):
        """Connect component variables to system flows."""
        for flow_key, flow_data in self.system.flows.items():
            source_comp = self.system.components.get(flow_data['source'])
            target_comp = self.system.components.get(flow_data['target'])

            # Find matching flow variable in components
            flow_var = None

            # Check source component output flows
            if source_comp:
                for flow_name, flow_info in source_comp.flows.get('source', {}).items():
                    if isinstance(flow_info.get('value'), cp.Variable):
                        flow_var = flow_info['value']
                        break

            # Check target component input flows
            if not flow_var and target_comp:
                for flow_name, flow_info in target_comp.flows.get('sink', {}).items():
                    if isinstance(flow_info.get('value'), cp.Variable):
                        flow_var = flow_info['value']
                        break

            # Create new variable if needed
            if flow_var is None:
                flow_var = cp.Variable(
                    self.system.N,
                    nonneg=True,
                    name=flow_key
                )

            flow_data['value'] = flow_var

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
        """Create energy balance constraints for each timestep."""
        constraints = []

        for t in range(self.system.N):
            # Collect all generation, consumption, and storage flows
            generation = []
            consumption = []
            storage_charge = []
            storage_discharge = []
            grid_import = []
            grid_export = []

            for comp in self.system.components.values():
                # Generation components
                if comp.type == "generation":
                    for flow in comp.flows.get('source', {}).values():
                        if isinstance(flow.get('value'), cp.Variable):
                            generation.append(flow['value'][t])

                # Consumption components
                elif comp.type == "consumption":
                    for flow in comp.flows.get('sink', {}).values():
                        if isinstance(flow.get('value'), cp.Variable):
                            consumption.append(flow['value'][t])

                # Storage components
                elif comp.type == "storage":
                    if hasattr(comp, 'P_cha') and comp.P_cha is not None:
                        storage_charge.append(comp.P_cha[t])
                    if hasattr(comp, 'P_dis') and comp.P_dis is not None:
                        storage_discharge.append(comp.P_dis[t])

                # Grid components
                elif comp.type == "transmission":
                    if hasattr(comp, 'P_draw') and comp.P_draw is not None:
                        grid_import.append(comp.P_draw[t])
                    if hasattr(comp, 'P_feed') and comp.P_feed is not None:
                        grid_export.append(comp.P_feed[t])

            # Energy balance: generation + imports + discharge = consumption + exports + charge
            lhs = []
            rhs = []

            if generation:
                lhs.extend(generation)
            if grid_import:
                lhs.extend(grid_import)
            if storage_discharge:
                lhs.extend(storage_discharge)

            if consumption:
                rhs.extend(consumption)
            if grid_export:
                rhs.extend(grid_export)
            if storage_charge:
                rhs.extend(storage_charge)

            if lhs and rhs:
                constraints.append(cp.sum(lhs) == cp.sum(rhs))

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

        for comp in self.system.components.values():
            if comp.type == "transmission" and hasattr(comp, 'import_tariff'):
                # Grid import costs
                if hasattr(comp, 'P_draw') and comp.P_draw is not None:
                    cost += cp.sum(comp.P_draw) * comp.import_tariff

                # Grid export revenue (negative cost)
                if hasattr(comp, 'P_feed') and comp.P_feed is not None:
                    cost -= cp.sum(comp.P_feed) * comp.feed_in_tariff

            # Add other operational costs if available
            # e.g., maintenance, fuel costs, etc.

        return cp.Minimize(cost)

    def _objective_min_co2(self):
        """Minimize CO2 emissions."""
        co2 = 0

        # Grid emissions (assuming grid has carbon intensity)
        grid_carbon_intensity = 0.5  # kg CO2/kWh (example value)

        for comp in self.system.components.values():
            if comp.type == "transmission":
                if hasattr(comp, 'P_draw') and comp.P_draw is not None:
                    co2 += cp.sum(comp.P_draw) * grid_carbon_intensity

        return cp.Minimize(co2)

    def _objective_min_grid(self):
        """Minimize grid usage (both import and export)."""
        grid_usage = 0

        for comp in self.system.components.values():
            if comp.type == "transmission":
                if hasattr(comp, 'P_draw') and comp.P_draw is not None:
                    grid_usage += cp.sum(comp.P_draw)
                if hasattr(comp, 'P_feed') and comp.P_feed is not None:
                    grid_usage += cp.sum(comp.P_feed)

        return cp.Minimize(grid_usage)

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