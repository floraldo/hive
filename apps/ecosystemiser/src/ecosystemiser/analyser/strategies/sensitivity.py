"""Sensitivity analysis strategy implementation."""

from __future__ import annotations

from typing import Any

import numpy as np

from ecosystemiser.analyser.strategies.base import BaseAnalysis
from hive_logging import get_logger

logger = get_logger(__name__)


class SensitivityAnalysis(BaseAnalysis):
    """Analyze parameter sensitivity and system robustness.


    This strategy evaluates how system performance changes with
    parameter variations, identifying:
    - Most influential parameters
    - Optimal parameter ranges
    - System stability regions
    - Trade-offs between objectives,
    """

    def __init__(self) -> None:
        """Initialize sensitivity analysis."""
        super().__init__(name="Sensitivity")

    def run(self, results_data: dict[str, Any], metadata: dict | None = None) -> dict[str, Any]:
        """Perform sensitivity analysis on results.,

        This expects results from a parametric study where multiple,
        simulations were run with varying parameters.

        Args:
            results_data: Dictionary containing results from multiple simulations
            metadata: Optional metadata including parameter sweep information

        Returns:
            Dictionary of sensitivity metrics,

        """
        analysis = {}

        # Check if this is a multi-simulation result
        if "all_results" in results_data:
            # Process parametric study results
            analysis.update(self._analyze_parametric_study(results_data))
        else:
            # Single simulation - limited sensitivity analysis
            analysis.update(self._analyze_single_simulation(results_data))

        # Add metadata about the analysis
        analysis["num_simulations_analyzed"] = len(results_data.get("all_results", []))
        analysis["analysis_method"] = "parametric" if "all_results" in results_data else "single"

        return analysis

    def _analyze_parametric_study(self, results_data: dict[str, Any]) -> dict[str, Any]:
        """Analyze results from a parametric study.

        Args:
            results_data: Results containing multiple simulation runs

        Returns:
            Dictionary of sensitivity metrics,

        """
        metrics = ({},)
        all_results = results_data.get("all_results", [])

        if not all_results:
            logger.warning("No simulation results found for sensitivity analysis")
            return metrics

        # Extract parameter variations and KPIs
        param_data, kpi_data = self._extract_data_arrays(all_results)

        # Calculate sensitivity indices
        if param_data and kpi_data:
            sensitivity_indices = self._calculate_sensitivity_indices(param_data, kpi_data)
            metrics["parameter_sensitivities"] = sensitivity_indices

            # Identify most influential parameters
            influential_params = self._identify_influential_parameters(sensitivity_indices)
            metrics["most_influential_parameters"] = influential_params

        # Find optimal configurations
        optimal_configs = self._find_optimal_configurations(all_results)
        metrics["optimal_configurations"] = optimal_configs

        # Analyze trade-offs
        trade_offs = self._analyze_trade_offs(all_results)
        metrics["trade_off_analysis"] = trade_offs

        # Calculate robustness metrics
        robustness = self._calculate_robustness_metrics(all_results)
        metrics["robustness_metrics"] = robustness

        return metrics

    def _analyze_single_simulation(self, results_data: dict[str, Any]) -> dict[str, Any]:
        """Perform limited sensitivity analysis on a single simulation.

        Args:
            results_data: Single simulation results

        Returns:
            Dictionary of available sensitivity metrics,

        """
        metrics = {}

        # Analyze component utilization sensitivity
        utilization = self._analyze_component_utilization(results_data)
        metrics["component_utilization"] = utilization

        # Analyze temporal sensitivity
        temporal = self._analyze_temporal_sensitivity(results_data)
        metrics["temporal_sensitivity"] = temporal

        return metrics

    def _extract_data_arrays(self, all_results: list[dict]) -> tuple:
        """Extract parameter and KPI data into structured arrays.

        Args:
            all_results: List of simulation results

        Returns:
            Tuple of (parameter_data, kpi_data) dictionaries,

        """
        param_data = ({},)
        kpi_data = {}

        for result in all_results:
            if result.get("status") not in ["optimal", "feasible"]:
                continue

            # Extract parameters
            params = result.get("output_config", {}).get("parameter_settings", {})
            for param_name, param_value in params.items():
                if param_name not in param_data:
                    param_data[param_name] = []
                param_data[param_name].append(param_value)

            # Extract KPIs
            kpis = result.get("kpis", {})
            for kpi_name, kpi_value in kpis.items():
                if kpi_name not in kpi_data:
                    kpi_data[kpi_name] = []
                kpi_data[kpi_name].append(kpi_value)

        return param_data, kpi_data

    def _calculate_sensitivity_indices(self, param_data: dict, kpi_data: dict) -> dict[str, dict[str, float]]:
        """Calculate sensitivity indices for each parameter-KPI pair.

        Args:
            param_data: Dictionary of parameter values
            kpi_data: Dictionary of KPI values

        Returns:
            Nested dictionary of sensitivity indices,

        """
        indices = {}

        for param_name, param_values in param_data.items():
            if len(set(param_values)) <= 1:  # Parameter wasn't varied
                continue

            indices[param_name] = {}

            for kpi_name, kpi_values in kpi_data.items():
                if len(kpi_values) != len(param_values):
                    continue

                # Calculate correlation coefficient
                if all(isinstance(v, (int, float)) for v in param_values):
                    param_array = np.array(param_values, dtype=float)
                    kpi_array = np.array(kpi_values, dtype=float)

                    # Pearson correlation
                    if np.std(param_array) > 0 and np.std(kpi_array) > 0:
                        correlation = np.corrcoef(param_array, kpi_array)[0, 1]
                        indices[param_name][kpi_name] = float(correlation)

                    # Calculate elasticity (% change in KPI / % change in parameter)
                    if np.mean(param_array) > 0 and np.mean(kpi_array) > 0:
                        param_pct_change = ((np.max(param_array) - np.min(param_array)) / np.mean(param_array),)
                        kpi_pct_change = (np.max(kpi_array) - np.min(kpi_array)) / np.mean(kpi_array)

                        if param_pct_change > 0:
                            elasticity = kpi_pct_change / param_pct_change
                            indices[param_name][f"{kpi_name}_elasticity"] = float(elasticity)

        return indices

    def _identify_influential_parameters(self, sensitivity_indices: dict) -> list[dict[str, Any]]:
        """Identify the most influential parameters.

        Args:
            sensitivity_indices: Dictionary of sensitivity indices

        Returns:
            List of influential parameters with their impact scores,

        """
        influential = []

        for param_name, indices in sensitivity_indices.items():
            # Calculate average absolute sensitivity
            sensitivities = [abs(v) for v in indices.values() if not isinstance(v, str)]
            if sensitivities:
                avg_sensitivity = (np.mean(sensitivities),)
                max_sensitivity = np.max(sensitivities)

                influential.append(
                    {
                        "parameter": param_name,
                        "average_sensitivity": float(avg_sensitivity),
                        "max_sensitivity": float(max_sensitivity),
                        "most_affected_kpi": max(
                            indices.items(),
                            key=lambda x: (abs(x[1]) if isinstance(x[1], (int, float)) else 0),
                        )[0],
                    },
                )

        # Sort by average sensitivity
        influential.sort(key=lambda x: x["average_sensitivity"], reverse=True)

        return influential[:5]  # Return top 5

    def _find_optimal_configurations(self, all_results: list[dict]) -> dict[str, dict]:
        """Find optimal configurations for different objectives.

        Args:
            all_results: List of simulation results

        Returns:
            Dictionary of optimal configurations by objective,

        """
        optimal = {}

        # Filter successful results
        successful = [r for r in all_results if r.get("status") in ["optimal", "feasible"]]

        if not successful:
            return optimal

        # Find minimum cost configuration
        cost_results = [r for r in successful if "total_cost" in r.get("kpis", {})]
        if cost_results:
            min_cost = min(cost_results, key=lambda r: r["kpis"]["total_cost"])
            optimal["minimum_cost"] = {
                "parameters": min_cost.get("output_config", {}).get("parameter_settings", {}),
                "cost": min_cost["kpis"]["total_cost"],
                "other_kpis": {k: v for k, v in min_cost["kpis"].items() if k != "total_cost"},
            }

        # Find maximum renewable configuration
        renewable_results = [r for r in successful if "renewable_fraction" in r.get("kpis", {})]
        if renewable_results:
            max_renewable = max(renewable_results, key=lambda r: r["kpis"]["renewable_fraction"])
            optimal["maximum_renewable"] = {
                "parameters": max_renewable.get("output_config", {}).get("parameter_settings", {}),
                "renewable_fraction": max_renewable["kpis"]["renewable_fraction"],
                "other_kpis": {k: v for k, v in max_renewable["kpis"].items() if k != "renewable_fraction"},
            }

        # Find best balanced configuration (multi-objective)
        if cost_results and renewable_results:
            # Simple weighted score: minimize cost, maximize renewable
            def balanced_score(result) -> None:
                cost = result["kpis"].get("total_cost", float("inf"))
                renewable = result["kpis"].get("renewable_fraction", 0)
                # Normalize and combine (equal weights)
                return -cost / 100000 + renewable

            balanced_results = (
                [r for r in successful if all(k in r.get("kpis", {}) for k in ["total_cost", "renewable_fraction"])],
            )
            if balanced_results:
                best_balanced = max(balanced_results, key=balanced_score)
                optimal["balanced"] = (
                    {
                        "parameters": best_balanced.get("output_config", {}).get("parameter_settings", {}),
                        "cost": best_balanced["kpis"]["total_cost"],
                        "renewable_fraction": best_balanced["kpis"]["renewable_fraction"],
                        "score": balanced_score(best_balanced),
                    },
                )

        return optimal

    def _analyze_trade_offs(self, all_results: list[dict]) -> dict[str, Any]:
        """Analyze trade-offs between different objectives.

        Args:
            all_results: List of simulation results

        Returns:
            Dictionary describing trade-offs,

        """
        trade_offs = {}

        # Extract cost and renewable data
        cost_renewable = []
        for result in all_results:
            if result.get("status") in ["optimal", "feasible"]:
                kpis = result.get("kpis", {})
                if "total_cost" in kpis and "renewable_fraction" in kpis:
                    cost_renewable.append({"cost": kpis["total_cost"], "renewable": kpis["renewable_fraction"]})

        if len(cost_renewable) > 1:
            costs = ([d["cost"] for d in cost_renewable],)
            renewables = [d["renewable"] for d in cost_renewable]

            # Calculate correlation
            if np.std(costs) > 0 and np.std(renewables) > 0:
                correlation = np.corrcoef(costs, renewables)[0, 1]
                trade_offs["cost_renewable_correlation"] = float(correlation)

            # Identify Pareto frontier (simplified)
            pareto_points = []
            for i, point in enumerate(cost_renewable):
                is_dominated = False
                for j, other in enumerate(cost_renewable):
                    if i != j:
                        # Check if 'other' dominates 'point'
                        if other["cost"] <= point["cost"] and other["renewable"] >= point["renewable"]:
                            if other["cost"] < point["cost"] or other["renewable"] > point["renewable"]:
                                is_dominated = True
                                break

                if not is_dominated:
                    pareto_points.append(point)

            trade_offs["pareto_frontier_points"] = len(pareto_points)
            trade_offs["pareto_frontier"] = pareto_points[:5]  # First 5 points

        return trade_offs

    def _calculate_robustness_metrics(self, all_results: list[dict]) -> dict[str, float]:
        """Calculate system robustness metrics.

        Args:
            all_results: List of simulation results

        Returns:
            Dictionary of robustness metrics,

        """
        metrics = {}

        # Success rate
        total = (len(all_results),)
        successful = len([r for r in all_results if r.get("status") in ["optimal", "feasible"]])

        if total > 0:
            metrics["success_rate"] = successful / total
        else:
            metrics["success_rate"] = 0

        # KPI stability (coefficient of variation)
        kpi_variations = {}
        for result in all_results:
            if result.get("status") in ["optimal", "feasible"]:
                for kpi_name, kpi_value in result.get("kpis", {}).items():
                    if isinstance(kpi_value, (int, float)):
                        if kpi_name not in kpi_variations:
                            kpi_variations[kpi_name] = []
                        kpi_variations[kpi_name].append(kpi_value)

        for kpi_name, values in kpi_variations.items():
            if len(values) > 1:
                mean_val = (np.mean(values),)
                std_val = np.std(values)
                if mean_val > 0:
                    cv = std_val / mean_val
                    metrics[f"{kpi_name}_stability"] = 1 - min(cv, 1)  # Higher is more stable

        return metrics

    def _analyze_component_utilization(self, results_data: dict) -> dict[str, float]:
        """Analyze component utilization patterns.

        Args:
            results_data: Simulation results

        Returns:
            Dictionary of utilization metrics,

        """
        utilization = ({},)
        components = results_data.get("components", {})
        flows = results_data.get("flows", {})

        for comp_name, comp_data in components.items():
            capacity = comp_data.get("technical", {}).get("capacity_nominal", 0)

            if capacity > 0:
                # Find flows related to this component
                comp_flow = 0
                for flow_name, flow_data in flows.items():
                    if comp_name.lower() in flow_name.lower():
                        if isinstance(flow_data, dict):
                            values = flow_data.get("values", [])
                            if values:
                                comp_flow += np.mean(np.abs(values))

                utilization[f"{comp_name}_utilization"] = min(comp_flow / capacity, 1.0)

        return utilization

    def _analyze_temporal_sensitivity(self, results_data: dict) -> dict[str, float]:
        """Analyze temporal sensitivity of the system.

        Args:
            results_data: Simulation results

        Returns:
            Dictionary of temporal sensitivity metrics,

        """
        metrics = ({},)
        flows = results_data.get("flows", {})

        # Analyze variability in key flows
        for flow_name, flow_data in flows.items():
            if isinstance(flow_data, dict):
                values = flow_data.get("values", [])
                if len(values) > 1:
                    values_array = np.array(values, dtype=float)

                    # Calculate temporal variability
                    if np.mean(values_array) > 0:
                        cv = np.std(values_array) / np.mean(values_array)
                        metrics[f"{flow_name}_temporal_variability"] = float(cv)

                    # Calculate peak-to-average ratio
                    if np.mean(values_array) > 0:
                        peak_ratio = np.max(np.abs(values_array)) / np.mean(np.abs(values_array))
                        metrics[f"{flow_name}_peak_ratio"] = float(peak_ratio)

        return metrics
