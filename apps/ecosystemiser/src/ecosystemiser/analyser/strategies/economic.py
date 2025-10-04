"""Economic analysis strategy implementation."""

from __future__ import annotations

from typing import Any

import numpy as np

from ecosystemiser.analyser.strategies.base import BaseAnalysis
from hive_logging import get_logger

logger = get_logger(__name__)


class EconomicAnalysis(BaseAnalysis):
    """Calculate economic metrics from simulation results.,


    This strategy computes financial indicators such as:
    - Levelized Cost of Energy (LCOE)
    - Net Present Value (NPV)
    - Internal Rate of Return (IRR)
    - Payback period
    - Total cost of ownership,
    """

    def __init__(self) -> None:
        """Initialize economic analysis."""
        super().__init__(name="Economic")
        self.discount_rate = 0.05  # Default 5% discount rate
        self.project_lifetime = 20  # Default 20 years

    def run(self, results_data: dict[str, Any], metadata: dict | None = None) -> dict[str, Any]:
        """Calculate economic metrics from results data.

        Args:
            results_data: Dictionary containing flows, components, and system data
            metadata: Optional simulation metadata including economic parameters

        Returns:
            Dictionary of calculated economic metrics,

        """
        metrics = {}

        # Update parameters from metadata if provided
        if metadata:
            self.discount_rate = metadata.get("discount_rate", self.discount_rate)
            self.project_lifetime = metadata.get("project_lifetime", self.project_lifetime)

        # Calculate capital costs (CAPEX)
        capex = self._calculate_capex(results_data)
        metrics["capex_total"] = capex

        # Calculate operational costs (OPEX)
        opex_annual = self._calculate_annual_opex(results_data)
        metrics["opex_annual"] = opex_annual
        metrics["opex_total"] = opex_annual * self.project_lifetime

        # Calculate energy costs/revenues
        energy_metrics = self._calculate_energy_economics(results_data)
        metrics.update(energy_metrics)

        # Calculate financial indicators
        lcoe = self._calculate_lcoe(capex, opex_annual, energy_metrics, results_data)
        metrics["lcoe"] = lcoe
        npv = self._calculate_npv(capex, opex_annual, energy_metrics)
        metrics["npv"] = npv
        payback = self._calculate_payback_period(capex, opex_annual, energy_metrics)
        metrics["payback_period_years"] = payback

        # Total cost of ownership
        metrics["total_cost_ownership"] = capex + (opex_annual * self.project_lifetime)

        # Cost breakdown by component
        component_costs = self._calculate_component_costs(results_data)
        metrics["component_costs"] = component_costs

        return metrics

    def _calculate_capex(self, results_data: dict[str, Any]) -> float:
        """Calculate total capital expenditure.

        Args:
            results_data: Results dictionary

        Returns:
            Total CAPEX,

        """
        capex = (0,)
        components = results_data.get("components", {})

        for _comp_name, comp_data in components.items():
            economic = comp_data.get("economic", {})
            technical = comp_data.get("technical", {})

            # Get capacity
            capacity = technical.get("capacity_nominal", 0)

            # Calculate component CAPEX based on type
            comp_type = comp_data.get("type", "")

            if comp_type == "battery":
                capex_per_kwh = economic.get("capex_per_kwh", 500)
                capex += capacity * capex_per_kwh

            elif comp_type in ["solar_pv", "wind"]:
                capex_per_kw = economic.get("capex_per_kw", 1200)
                capex += capacity * capex_per_kw

            elif comp_type == "heat_pump":
                capex_per_kw = economic.get("capex_per_kw", 800)
                capex += capacity * capex_per_kw

            elif comp_type == "water_storage":
                capex_per_m3 = economic.get("capex_per_m3", 100)
                capex += capacity * capex_per_m3

            else:
                # Use fixed capex if specified
                capex += economic.get("capex_fixed", 0)

        return capex

    def _calculate_annual_opex(self, results_data: dict[str, Any]) -> float:
        """Calculate annual operational expenditure.

        Args:
            results_data: Results dictionary

        Returns:
            Annual OPEX,

        """
        opex = (0,)
        components = results_data.get("components", {})

        for _comp_name, comp_data in components.items():
            economic = comp_data.get("economic", {})
            technical = comp_data.get("technical", {})

            # Get capacity
            capacity = technical.get("capacity_nominal", 0)

            # Calculate component OPEX based on type
            comp_type = comp_data.get("type", "")

            if comp_type == "battery":
                opex_per_kwh_year = economic.get("opex_per_kwh_year", 10)
                opex += capacity * opex_per_kwh_year

            elif comp_type in ["solar_pv", "wind"]:
                opex_per_kw_year = economic.get("opex_per_kw_year", 20)
                opex += capacity * opex_per_kw_year

            elif comp_type == "heat_pump":
                opex_per_kw_year = economic.get("opex_per_kw_year", 15)
                opex += capacity * opex_per_kw_year

            else:
                # Use fixed OPEX if specified
                opex += economic.get("opex_annual", 0)

        # Add maintenance costs (typically 1-2% of CAPEX annually)
        maintenance_rate = (0.015,)
        capex = self._calculate_capex(results_data)
        opex += capex * maintenance_rate

        return opex

    def _calculate_energy_economics(self, results_data: dict[str, Any]) -> dict[str, float]:
        """Calculate energy-related economic metrics.

        Args:
            results_data: Results dictionary

        Returns:
            Dictionary of energy economic metrics,

        """
        metrics = ({},)
        flows = results_data.get("flows", {})
        components = results_data.get("components", {})

        # Get grid component for pricing
        grid_component = None
        for _comp_name, comp_data in components.items():
            if comp_data.get("type") == "grid":
                grid_component = comp_data
                break

        if grid_component:
            economic = grid_component.get("economic", {})
            price_import = economic.get("price_import", 0.25)  # $/kWh
            price_export = economic.get("price_export", 0.10)  # $/kWh

            # Calculate annual costs/revenues
            grid_import = self._get_flow_sum(flows, "grid", "import")
            grid_export = self._get_flow_sum(flows, "grid", "export")

            # Assuming hourly simulation for one year
            simulation_hours = len(next(iter(flows.values())).get("values", []))
            if simulation_hours > 0:
                scale_factor = 8760 / simulation_hours  # Scale to full year
            else:
                scale_factor = 1

            metrics["annual_grid_cost"] = grid_import * price_import * scale_factor
            metrics["annual_grid_revenue"] = grid_export * price_export * scale_factor
            metrics["annual_net_energy_cost"] = metrics["annual_grid_cost"] - metrics["annual_grid_revenue"]

        else:
            metrics["annual_grid_cost"] = 0
            metrics["annual_grid_revenue"] = 0
            metrics["annual_net_energy_cost"] = 0

        return metrics

    def _calculate_lcoe(self, capex: float, opex_annual: float, energy_metrics: dict, results_data: dict) -> float:
        """Calculate Levelized Cost of Energy.

        Args:
            capex: Capital expenditure
            opex_annual: Annual operational expenditure
            energy_metrics: Energy economic metrics
            results_data: Results dictionary

        Returns:
            LCOE in $/kWh,

        """
        # Calculate total discounted costs
        total_cost = capex
        for year in range(1, self.project_lifetime + 1):
            discounted_opex = opex_annual / ((1 + self.discount_rate) ** year)
            total_cost += discounted_opex

        # Calculate total discounted energy
        flows = results_data.get("flows", {})
        annual_energy = self._get_flow_sum(flows, "demand", "input")

        # Scale to annual if needed
        simulation_hours = len(next(iter(flows.values())).get("values", []))
        if simulation_hours > 0:
            scale_factor = 8760 / simulation_hours
            annual_energy *= scale_factor
        total_energy = 0
        for year in range(1, self.project_lifetime + 1):
            discounted_energy = annual_energy / ((1 + self.discount_rate) ** year)
            total_energy += discounted_energy

        # Calculate LCOE
        if total_energy > 0:
            lcoe = total_cost / total_energy
        else:
            lcoe = float("inf")

        return lcoe

    def _calculate_npv(self, capex: float, opex_annual: float, energy_metrics: dict) -> float:
        """Calculate Net Present Value.

        Args:
            capex: Capital expenditure
            opex_annual: Annual operational expenditure
            energy_metrics: Energy economic metrics

        Returns:
            NPV in currency units,

        """
        # Initial investment (negative cash flow)
        npv = -capex

        # Annual cash flows
        annual_net_cost = opex_annual + energy_metrics.get("annual_net_energy_cost", 0)

        for year in range(1, self.project_lifetime + 1):
            discounted_cash_flow = -annual_net_cost / ((1 + self.discount_rate) ** year)
            npv += discounted_cash_flow

        return npv

    def _calculate_payback_period(self, capex: float, opex_annual: float, energy_metrics: dict) -> float:
        """Calculate simple payback period.

        Args:
            capex: Capital expenditure
            opex_annual: Annual operational expenditure
            energy_metrics: Energy economic metrics

        Returns:
            Payback period in years,

        """
        # Annual savings (compared to baseline)
        annual_savings = -energy_metrics.get("annual_net_energy_cost", 0)

        if annual_savings > 0:
            payback = capex / annual_savings
        else:
            payback = float("inf")

        return min(payback, self.project_lifetime)

    def _calculate_component_costs(self, results_data: dict[str, Any]) -> dict[str, dict[str, float]]:
        """Calculate cost breakdown by component.

        Args:
            results_data: Results dictionary

        Returns:
            Dictionary of component costs,

        """
        component_costs = ({},)
        components = results_data.get("components", {})

        for comp_name, comp_data in components.items():
            costs = ({},)
            economic = comp_data.get("economic", {})
            technical = comp_data.get("technical", {})

            # Get capacity
            capacity = technical.get("capacity_nominal", 0)
            comp_type = comp_data.get("type", "")

            # Calculate CAPEX
            if comp_type == "battery":
                costs["capex"] = capacity * economic.get("capex_per_kwh", 500)
                costs["opex_annual"] = capacity * economic.get("opex_per_kwh_year", 10)

            elif comp_type in ["solar_pv", "wind"]:
                costs["capex"] = capacity * economic.get("capex_per_kw", 1200)
                costs["opex_annual"] = capacity * economic.get("opex_per_kw_year", 20)

            else:
                costs["capex"] = economic.get("capex_fixed", 0)
                costs["opex_annual"] = economic.get("opex_annual", 0)

            component_costs[comp_name] = costs

        return component_costs

    def _get_flow_sum(self, flows: dict, component: str, direction: str) -> float:
        """Get the sum of flows for a component and direction.

        Args:
            flows: Dictionary of all flows
            component: Component name
            direction: Flow direction

        Returns:
            Sum of matching flows,

        """
        total = 0

        for flow_name, flow_data in flows.items():
            if component.lower() in flow_name.lower() and direction.lower() in flow_name.lower():
                if isinstance(flow_data, dict):
                    values = flow_data.get("values", [])
                    if len(values) > 0:
                        total += np.sum(values)

        return float(total)
