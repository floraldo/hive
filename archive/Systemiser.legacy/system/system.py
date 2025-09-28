import cvxpy as cp
import pandas as pd
import time
import numpy as np
import logging
from hive_logging import get_logger

logger = get_logger(__name__)

# from model import Battery, Grid, HeatBuffer, HeatDemand, HeatPump, PowerDemand, SolarPV
# from model import EconomicParameters
# from model import EnvironmentalParameters

system_logger = logging.getLogger("system")


class System:
    def __init__(self, system_id, n=1):
        self.components = {}
        self.system_id = system_id
        self.N = n
        self.constraints = []
        self.flows = {}
        self.objective = None
        self.problem = None
        self.total_energy = 0
        self.total_co2 = 0
        self.total_cost = 0
        self.flow_types = {
            "electricity": {"unit": "kWh", "color": "#FFA500"},  # Orange
            "heat": {"unit": "kWh", "color": "#FF0000"},  # Red
            "water": {"unit": "m³", "color": "#0000FF"},  # Blue
        }
        self.system_constraints = []  # New list for system-level constraints

    # Component Management
    def initialize_component(
        self, component_name, technical_params_df, economic_params_df, environmental_params_df, profiles
    ):
        from model import EconomicParameters, EnvironmentalParameters
        from model import Battery, Grid, HeatBuffer, HeatDemand, HeatPump, PowerDemand, SolarPV, System

        # Prepare TechnicalParameters object for the component
        technical_params = technical_params_df.loc[component_name].to_dict()
        technical_params = {k: v for k, v in technical_params.items() if pd.notna(v)}  # ignore NaN values

        # If component_name is in profiles, add the profile to the technical parameters
        if component_name in profiles:
            technical_params["P_profile"] = profiles[component_name]

        # Prepare EconomicParameters object for the component
        economic_params = economic_params_df.loc[component_name].to_dict()
        economic_params = {k: v for k, v in economic_params.items() if pd.notna(v)}  # ignore NaN values

        # Create instance of EconomicParameters
        economic_params_obj = EconomicParameters(
            **economic_params,
        )

        # Prepare EnvironmentalParameters object for the component
        environmental_params = environmental_params_df.loc[component_name].to_dict()
        environmental_params = {k: v for k, v in environmental_params.items() if pd.notna(v)}  # ignore NaN values

        # Create instance of EnvironmentalParameters
        environmental_params_obj = EnvironmentalParameters(**environmental_params)

        # Create the component and set its parameters
        component_class = eval(component_name)
        component = component_class(
            component_name,
            **technical_params,
            economic=economic_params_obj,
            environmental=environmental_params_obj,
            n=self.N,
        )

        # Add the component to the system
        self.add_component(component)

    def add_component(self, component):
        self.components[component.name] = component
        # component.N = self.N

    def remove_component(self, component_name):
        self.components.pop(component_name)

    def connect(self, component1_name, component2_name, flow_type, bidirectional=False, print_connection=True):
        if flow_type not in self.flow_types:
            raise ValueError(f"Invalid flow type. Must be one of: {list(self.flow_types.keys())}")

        component1 = self.components[component1_name]
        component2 = self.components[component2_name]

        # Add source and target to the flow dict
        flow = {
            "source": component1_name,
            "target": component2_name,
            "type": flow_type,
            "unit": self.flow_types[flow_type]["unit"],
            "color": self.flow_types[flow_type]["color"],
            "value": cp.Variable(
                component1.N,
                nonneg=True,
                name=f'{component1.name}_{"W" if flow_type=="water" else "P"}_{component2.name}',
            ),
        }

        component1.flows["output"][f'{"W" if flow_type=="water" else "P"}_{component2_name}'] = flow
        component2.flows["input"][f'{"W" if flow_type=="water" else "P"}_{component1_name}'] = flow

        # Add flow to the system
        self.flows[f'{component1.name}_{"W" if flow_type=="water" else "P"}_{component2.name}'] = flow

        if print_connection:
            logger.info(f"Connected {component1_name} to {component2_name} with {flow_type}")

        if bidirectional:
            self.connect(
                component2_name, component1_name, flow_type, bidirectional=False, print_connection=print_connection
            )

    # System Optimization
    def create_balance_constraints(self, print_constraints=False, return_constraints=False):
        """Create system constraints and optionally return them."""
        constraints_info = []

        for component in self.components.values():
            new_constraints = component.set_constraints()
            self.constraints += new_constraints

            if return_constraints:
                # Capture constraint info in readable format
                for c in new_constraints:
                    constraints_info.append(
                        {
                            "component": component.name,
                            "type": component.type,
                            "expression": str(c),
                            "variables": [str(v) for v in c.variables()],
                        }
                    )

        if print_constraints:
            self.print_all_constraints()

        return constraints_info if return_constraints else None

    def print_all_constraints(self):
        logger.info("\n---Constraints---")
        for component in self.components.values():
            component.print_constraints()

    def set_objective(self, objective):
        objective_functions = {
            "min_energy": lambda: self.total_energy,
            "min_CO2": lambda: self.total_co2,
            "min_peak_power": lambda: cp.max(
                self.components["Grid"].flows["source"]["P_draw"]["value"]
                + self.components["Grid"].flows["sink"]["P_feed"]["value"]
            ),
            "min_cost": lambda: self.total_cost
            # You will add your own functions for renewable and storage utilization
        }

        try:
            self.objective = cp.Minimize(objective_functions[objective]())
        except KeyError:
            raise ValueError(f"Invalid objective. Choose from {list(objective_functions.keys())}")

    def add_system_constraint(self, constraint):
        """Add a system-level constraint.

        Args:
            constraint: A CVXPY constraint expression
        """
        self.system_constraints.append(constraint)

    def create_problem(self):
        """Create optimization problem combining component and system constraints."""
        # Combine component constraints and system constraints
        all_constraints = self.constraints + self.system_constraints
        self.problem = cp.Problem(self.objective, all_constraints)

    def solve(self):
        start_time = time.time()
        self.problem.solve(solver=cp.GLPK)
        logger.info(f"Time taken for optimization: {time.time() - start_time} seconds")
        logger.info("Problem status: ", self.problem.status)

    def convert_results_to_numeric(self):
        for component_name, component in self.components.items():
            for flow_dir, flows in component.flows.items():
                for flow_name, flow in flows.items():
                    if isinstance(flow["value"], cp.Variable):
                        component.flows[flow_dir][flow_name]["value"] = flow["value"].value
            if component.type == "storage":
                if isinstance(component.E, cp.Variable):
                    component.E = component.E.value

    def aggregate_component_results(self, components, result_type):
        if result_type not in ["technical_results", "economical_results", "environmental_results"]:
            raise ValueError(
                "Invalid result type. Choose 'technical_results', 'economical_results', or 'environmental_results'."
            )

        aggregated_results = {}

        for name, component in components.items():
            results = getattr(component, result_type, None)
            if results is None:
                raise ValueError(f"Result type '{result_type}' not found in component '{name}'.")
            aggregated_results[name] = results

        return pd.DataFrame.from_dict(aggregated_results, orient="index")

    def run(self, method="optimization"):
        """Run the system using specified method with performance monitoring."""
        start_time = time.time()

        try:
            if method == "optimization":
                self._run_optimization()
            elif method == "rule_based":
                self._run_rule_based()
            else:
                raise ValueError("Invalid method. Choose 'optimization' or 'rule_based'")

            performance = {
                "method": method,
                "runtime": time.time() - start_time,
                "feasible": self._check_feasibility(method),
            }

            return performance

        except Exception as e:
            system_logger.exception(f"Error running {method} method")
            raise

    def _run_optimization(self):
        """Run system using optimization."""
        self.create_balance_constraints()
        if self.objective is None:
            raise ValueError("No objective function set for optimization method.")
        self.create_problem()
        self.solve()
        self.convert_results_to_numeric()

    def _run_rule_based(self):
        """Run system using rule-based control."""
        from model.controllers.rule_engine import RuleEngine

        # Convert all CVXPY variables to numpy arrays for rule-based control
        for component in self.components.values():
            for flow_type in component.flows.values():
                for flow in flow_type.values():
                    if isinstance(flow["value"], cp.Variable):
                        flow["value"] = np.zeros(self.N)
            if component.type == "storage":
                if isinstance(component.E, cp.Variable):
                    component.E = np.zeros(self.N)

        engine = RuleEngine(self)

        # Initialize storage components
        for component in self.components.values():
            if component.type == "storage":
                component.E[0] = component.E_init

        # Process each timestep
        for t in range(self.N):
            self._update_storage_levels(t)
            for rule in engine.rules:
                rule.func(t)

    def _check_feasibility(self, method):
        """Check if solution is feasible."""
        if method == "optimization":
            return hasattr(self, "problem") and self.problem.status == "optimal"
        return len(self.validate_rule_based_solution()) == 0

    def _update_storage_levels(self, t):
        """Update storage levels for timestep t."""
        if t == 0:
            return

        for component in self.components.values():
            if component.type == "storage":
                component.E[t] = component.E[t - 1]

    def print_component_results(self):
        logger.info("Component Technical Results:")
        logger.info(self.component_technicals)

        logger.info("\nComponent Economic Results:")
        logger.info(self.component_economics)

        logger.info("\nComponent Environmental Results:")
        logger.info(self.component_environmentals)

    def debug_component(self, component_name, timestep=0):
        """Debug helper for a single component."""
        component = self.components[component_name]
        logger.info(f"\n=== {component.name} at timestep {timestep} ===")
        logger.info(f"Type: {component.type}")
        logger.info(f"W_max: {component.W_max if hasattr(component, 'W_max') else 'N/A'}")

        # Print flows at timestep
        logger.info("\nFlows:")
        for flow_type in ["input", "output", "source", "sink"]:
            if flow_type in component.flows:
                logger.info(f"\n{flow_type.upper()}:")
                for name, flow in component.flows[flow_type].items():
                    value = None
                    if isinstance(flow["value"], cp.Variable):
                        value = flow["value"][timestep].value if hasattr(flow["value"], "value") else "Not solved"
                    elif isinstance(flow["value"], np.ndarray):
                        value = flow["value"][timestep]
                    logger.info(f"  {name} = {value}")

        # Print relevant constraints
        logger.info("\nConstraints affecting timestep {}:".format(timestep))
        for constraint in component.constraints:
            if f"[{timestep}]" in str(constraint):
                logger.info(f"  {constraint}")

    def debug_system_flows(self, timestep=0):
        """Debug helper for system-level flows."""
        logger.info("\n=== System Flow Analysis ===")
        logger.info(f"Timestep: {timestep}")

        for flow_name, flow in self.flows.items():
            value = None
            if isinstance(flow["value"], cp.Variable):
                value = flow["value"][timestep].value if hasattr(flow["value"], "value") else "Not solved"
            elif isinstance(flow["value"], np.ndarray):
                value = flow["value"][timestep]

            logger.info(f"\n{flow['source']} -> {flow['target']}:")
            logger.info(f"  Value: {value}")
            logger.info(f"  Type: {flow['type']}")

    def debug_water_system(self, timestep=0):
        """Comprehensive debug helper for water system."""
        logger.debug("\n=== Water System Debug ===")
        logger.info(f"Timestep: {timestep}")

        # Debug storage components
        for name, component in self.components.items():
            if component.type == "storage":
                self.debug_component(name, timestep)

        # Debug system flows
        self.debug_system_flows(timestep)

        # Print balance equations
        logger.info("\nBalance Equations:")
        for component_name, component in self.components.items():
            if component.type == "storage":
                input_flows = []
                output_flows = []

                # Handle both cvxpy Variables and numpy arrays
                for flow in component.flows["input"].values():
                    if isinstance(flow["value"], cp.Variable):
                        value = flow["value"][timestep].value if hasattr(flow["value"], "value") else None
                        if value is not None:
                            input_flows.append(-value)
                    elif isinstance(flow["value"], np.ndarray):
                        input_flows.append(-flow["value"][timestep])

                for flow in component.flows["output"].values():
                    if isinstance(flow["value"], cp.Variable):
                        value = flow["value"][timestep].value if hasattr(flow["value"], "value") else None
                        if value is not None:
                            output_flows.append(value)
                    elif isinstance(flow["value"], np.ndarray):
                        output_flows.append(flow["value"][timestep])

                if input_flows or output_flows:
                    logger.info(f"\n{component_name}:")
                    logger.info(f"  Sum of inputs: {[-f for f in input_flows]}")
                    logger.info(f"  Sum of outputs: {output_flows}")

    def construct_problem(self):
        """Construct the optimization problem."""
        if self.objective is None:
            raise ValueError("Objective function must be set before constructing problem")

        constraints = []
        for component in self.components.values():
            if hasattr(component, "set_constraints"):
                constraints.extend(component.set_constraints())

        self.problem = cp.Problem(self.objective, constraints)
        return self.problem

    def validate_rule_based_solution(self):
        """Validate the rule-based solution meets constraints."""
        violations = []

        for component in self.components.values():
            # Check storage bounds
            if component.type == "storage":
                if any(e < 0 or e > component.E_max for e in component.E):
                    violations.append(f"{component.name} storage bounds violated")

            # Check flow bounds
            for flow_dict in component.flows.values():
                for flow in flow_dict.values():
                    if hasattr(flow, "max") and any(v > flow.max for v in flow["value"]):
                        violations.append(f"Flow bound violated in {component.name}")

        return violations

    def get_system_constraints(self):
        """Extract constraints from the problem after formulation."""
        if not hasattr(self, "problem") or self.problem is None:
            return []

        constraints_info = []
        seen = set()  # Track unique constraints

        for constraint in self.problem.constraints:
            constraint_str = str(constraint)
            if constraint_str not in seen:
                seen.add(constraint_str)
                constraints_info.append(
                    {"expression": constraint_str, "variables": [str(v) for v in constraint.variables()]}
                )

        return constraints_info
