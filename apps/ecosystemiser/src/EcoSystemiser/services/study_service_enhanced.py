"""Enhanced StudyService with complete parametric sweep implementation.

This module extends the StudyService with full parameter application support,
enabling true exploration of design spaces for the intelligent co-pilot vision.
"""

import copy
from typing import Any, Dict, List

from hive_logging import get_logger

logger = get_logger(__name__)


def apply_parameter_to_config(
    config_dict: Dict[str, Any], component_name: str, parameter_path: str, value: Any
) -> Dict[str, Any]:
    """Apply a parameter value to a system configuration dictionary.

    Args:
        config_dict: System configuration dictionary
        component_name: Name of the component to modify
        parameter_path: Dot-notation path to parameter (e.g., "technical.capacity_nominal")
        value: New value for the parameter

    Returns:
        Modified configuration dictionary
    """
    # Deep copy to avoid modifying original
    config = copy.deepcopy(config_dict)

    # Find the component in the configuration
    components = config.get("components", [])
    component_found = False

    for component in components:
        if component.get("name") == component_name:
            component_found = True

            # Navigate the parameter path
            path_parts = parameter_path.split(".")
            current = component

            # Navigate to the parent of the final key
            for part in path_parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]

            # Set the final value
            final_key = path_parts[-1]
            old_value = current.get(final_key, "NOT_SET")
            current[final_key] = value

            logger.debug(f"Updated {component_name}.{parameter_path}: {old_value} -> {value}")
            break

    if not component_found:
        logger.warning(f"Component '{component_name}' not found in configuration")

    return config


def generate_parameter_report(parameter_settings: Dict[str, Any], results: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a report for a parametric sweep result.

    Args:
        parameter_settings: Dictionary of parameter settings used
        results: Simulation results including KPIs

    Returns:
        Report dictionary with parameter influence analysis
    """
    report = {
        "parameters": parameter_settings,
        "kpis": results.get("kpis", {}),
        "solver_metrics": results.get("solver_metrics", {}),
        "sensitivity_score": 0.0,
    }

    # Calculate sensitivity score based on KPI variance
    if "kpis" in results:
        # Simple sensitivity metric: sum of normalized KPI values
        kpi_values = [v for v in results["kpis"].values() if isinstance(v, (int, float))]
        if kpi_values:
            report["sensitivity_score"] = sum(kpi_values) / len(kpi_values)

    return report


class ParametricSweepEnhancement:
    """Enhanced parametric sweep capabilities for StudyService."""

    @staticmethod
    def create_battery_capacity_sweep(
        base_capacity: float, num_points: int = 5, range_factor: float = 2.0
    ) -> List[float]:
        """Create a sweep of battery capacity values.

        Args:
            base_capacity: Base battery capacity in kWh
            num_points: Number of points to sweep
            range_factor: Factor to determine sweep range (e.g., 2.0 = 0.5x to 2x base)

        Returns:
            List of capacity values to sweep
        """
        import numpy as np

        min_capacity = base_capacity / range_factor
        max_capacity = base_capacity * range_factor

        return list(np.linspace(min_capacity, max_capacity, num_points))

    @staticmethod
    def create_solar_capacity_sweep(base_capacity: float, num_points: int = 5) -> List[float]:
        """Create a sweep of solar PV capacity values.

        Args:
            base_capacity: Base solar capacity in kW
            num_points: Number of points to sweep

        Returns:
            List of capacity values to sweep
        """
        import numpy as np

        # Solar typically sweeps from 0 to 2x base capacity
        return list(np.linspace(0, base_capacity * 2, num_points))

    @staticmethod
    def create_efficiency_sweep(num_points: int = 5) -> List[float]:
        """Create a sweep of efficiency values.

        Args:
            num_points: Number of points to sweep

        Returns:
            List of efficiency values (0.7 to 0.98)
        """
        import numpy as np

        return list(np.linspace(0.7, 0.98, num_points))

    @staticmethod
    def analyze_parameter_influence(study_result: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze the influence of parameters on KPIs.

        Args:
            study_result: Complete study result with all simulations

        Returns:
            Analysis report with parameter sensitivities
        """
        analysis = {
            "parameter_sensitivities": {},
            "optimal_configuration": None,
            "pareto_frontier": [],
            "recommendations": [],
        }

        if not study_result.get("all_results"):
            return analysis

        # Extract parameter variations and KPIs
        param_values = {}
        kpi_values = {}

        for result in study_result["all_results"]:
            if result.get("status") in ["optimal", "feasible"]:
                # Get parameter settings
                params = result.get("output_config", {}).get("parameter_settings", {})
                for param_name, param_value in params.items():
                    if param_name not in param_values:
                        param_values[param_name] = []
                    param_values[param_name].append(param_value)

                # Get KPIs
                kpis = result.get("kpis", {})
                for kpi_name, kpi_value in kpis.items():
                    if kpi_name not in kpi_values:
                        kpi_values[kpi_name] = []
                    kpi_values[kpi_name].append(kpi_value)

        # Calculate sensitivities
        import numpy as np

        for param_name, values in param_values.items():
            if len(set(values)) > 1:  # Parameter was varied
                param_sensitivity = {}

                for kpi_name, kpi_vals in kpi_values.items():
                    if len(kpi_vals) == len(values):
                        # Calculate correlation coefficient
                        if all(isinstance(v, (int, float)) for v in values):
                            correlation = np.corrcoef(values, kpi_vals)[0, 1]
                            param_sensitivity[kpi_name] = float(correlation)

                analysis["parameter_sensitivities"][param_name] = param_sensitivity

        # Find optimal configuration (lowest cost)
        best_cost = float("inf")
        best_config = None

        for result in study_result["all_results"]:
            if result.get("status") in ["optimal", "feasible"]:
                cost = result.get("kpis", {}).get("total_cost", float("inf"))
                if cost < best_cost:
                    best_cost = cost
                    best_config = result.get("output_config", {}).get("parameter_settings", {})

        analysis["optimal_configuration"] = best_config

        # Generate recommendations
        if analysis["parameter_sensitivities"]:
            # Find most influential parameters
            max_sensitivity = 0
            most_influential = None

            for param, sensitivities in analysis["parameter_sensitivities"].items():
                avg_sensitivity = np.mean([abs(s) for s in sensitivities.values()])
                if avg_sensitivity > max_sensitivity:
                    max_sensitivity = avg_sensitivity
                    most_influential = param

            if most_influential:
                analysis["recommendations"].append(
                    f"Parameter '{most_influential}' has the highest impact on system performance"
                )
                analysis["recommendations"].append(f"Consider fine-tuning '{most_influential}' for optimization")

        return analysis
