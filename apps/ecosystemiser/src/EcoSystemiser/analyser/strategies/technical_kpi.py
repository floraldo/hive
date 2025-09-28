"""Technical KPI analysis strategy implementation."""

from typing import Dict, Any, Optional
import numpy as np
import pandas as pd

from ecosystemiser.analyser.strategies.base import BaseAnalysis
from hive_logging import get_logger

logger = get_logger(__name__)


class TechnicalKPIAnalysis(BaseAnalysis):
    """Calculate technical key performance indicators from simulation results.

    This strategy computes core technical metrics such as:
    - Grid self-sufficiency
    - Renewable fraction
    - Battery cycles
    - System efficiency
    - Peak demand reduction
    """

    def __init__(self):
        """Initialize technical KPI analysis."""
        super().__init__(name="TechnicalKPI")

    def run(self, results_data: Dict[str, Any], metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Calculate technical KPIs from results data.

        Args:
            results_data: Dictionary containing flows, components, and system data
            metadata: Optional simulation metadata

        Returns:
            Dictionary of calculated technical KPIs
        """
        kpis = {}

        # Detect system type from components
        system_type = self._detect_system_type(results_data)

        if system_type == "energy":
            kpis.update(self._calculate_energy_kpis(results_data))
        elif system_type == "water":
            kpis.update(self._calculate_water_kpis(results_data))
        elif system_type == "mixed":
            kpis.update(self._calculate_energy_kpis(results_data))
            kpis.update(self._calculate_water_kpis(results_data))

        # Calculate common KPIs
        kpis.update(self._calculate_common_kpis(results_data))

        return kpis

    def _detect_system_type(self, results_data: Dict[str, Any]) -> str:
        """Detect the type of system from components.

        Args:
            results_data: Results dictionary

        Returns:
            System type: 'energy', 'water', or 'mixed'
        """
        components = results_data.get('components', {})

        has_energy = any(
            comp.get('type') in ['battery', 'solar_pv', 'grid', 'generator']
            for comp in components.values()
        )

        has_water = any(
            comp.get('type') in ['water_storage', 'water_demand', 'rainwater_source']
            for comp in components.values()
        )

        if has_energy and has_water:
            return "mixed"
        elif has_energy:
            return "energy"
        elif has_water:
            return "water"
        else:
            return "unknown"

    def _calculate_energy_kpis(self, results_data: Dict[str, Any]) -> Dict[str, float]:
        """Calculate energy-specific KPIs.

        Args:
            results_data: Results dictionary

        Returns:
            Dictionary of energy KPIs
        """
        kpis = {}
        flows = results_data.get('flows', {})
        components = results_data.get('components', {})

        # Grid import/export
        grid_import = self._get_flow_sum(flows, 'grid', direction='import')
        grid_export = self._get_flow_sum(flows, 'grid', direction='export')

        # Renewable generation
        solar_gen = self._get_flow_sum(flows, 'solar_pv', direction='output')
        wind_gen = self._get_flow_sum(flows, 'wind', direction='output')
        renewable_gen = solar_gen + wind_gen

        # Demand
        total_demand = self._get_flow_sum(flows, 'demand', direction='input')

        # Calculate KPIs
        if total_demand > 0:
            kpis['grid_self_sufficiency'] = max(0, 1 - (grid_import / total_demand))
            kpis['renewable_fraction'] = min(1, renewable_gen / total_demand)
        else:
            kpis['grid_self_sufficiency'] = 0
            kpis['renewable_fraction'] = 0

        kpis['grid_import_total'] = grid_import
        kpis['grid_export_total'] = grid_export
        kpis['renewable_generation_total'] = renewable_gen
        kpis['total_demand'] = total_demand

        # Battery metrics
        battery_kpis = self._calculate_battery_kpis(flows, components)
        kpis.update(battery_kpis)

        # Peak shaving
        peak_kpis = self._calculate_peak_shaving_kpis(flows)
        kpis.update(peak_kpis)

        return kpis

    def _calculate_water_kpis(self, results_data: Dict[str, Any]) -> Dict[str, float]:
        """Calculate water-specific KPIs.

        Args:
            results_data: Results dictionary

        Returns:
            Dictionary of water KPIs
        """
        kpis = {}
        flows = results_data.get('flows', {})

        # Water sources
        rainwater = self._get_flow_sum(flows, 'rainwater', direction='output')
        mains_water = self._get_flow_sum(flows, 'water_grid', direction='import')

        # Water demand
        water_demand = self._get_flow_sum(flows, 'water_demand', direction='input')

        # Calculate KPIs
        if water_demand > 0:
            kpis['rainwater_utilization'] = min(1, rainwater / water_demand)
            kpis['water_self_sufficiency'] = max(0, 1 - (mains_water / water_demand))
        else:
            kpis['rainwater_utilization'] = 0
            kpis['water_self_sufficiency'] = 0

        kpis['total_water_demand'] = water_demand
        kpis['rainwater_collected'] = rainwater
        kpis['mains_water_used'] = mains_water

        return kpis

    def _calculate_common_kpis(self, results_data: Dict[str, Any]) -> Dict[str, float]:
        """Calculate common KPIs applicable to all systems.

        Args:
            results_data: Results dictionary

        Returns:
            Dictionary of common KPIs
        """
        kpis = {}

        # Solver metrics
        solver_metrics = results_data.get('solver_metrics', {})
        kpis['objective_value'] = solver_metrics.get('objective_value', 0)
        kpis['solve_time'] = solver_metrics.get('solve_time', 0)
        kpis['solver_status'] = solver_metrics.get('status', 'unknown')

        # System efficiency (if applicable)
        total_input = 0
        total_output = 0

        flows = results_data.get('flows', {})
        for flow_name, flow_data in flows.items():
            if isinstance(flow_data, dict):
                values = flow_data.get('values', [])
                if len(values) > 0:
                    if 'input' in flow_name.lower():
                        total_input += np.sum(values)
                    elif 'output' in flow_name.lower():
                        total_output += np.sum(values)

        if total_input > 0:
            kpis['system_efficiency'] = min(1, total_output / total_input)
        else:
            kpis['system_efficiency'] = 0

        return kpis

    def _calculate_battery_kpis(self, flows: Dict, components: Dict) -> Dict[str, float]:
        """Calculate battery-specific KPIs.

        Args:
            flows: Flow data dictionary
            components: Components dictionary

        Returns:
            Dictionary of battery KPIs
        """
        kpis = {}

        # Find battery component
        battery = None
        for comp_name, comp_data in components.items():
            if comp_data.get('type') == 'battery':
                battery = comp_data
                break

        if not battery:
            return kpis

        # Battery charge/discharge
        battery_charge = self._get_flow_sum(flows, 'battery', direction='charge')
        battery_discharge = self._get_flow_sum(flows, 'battery', direction='discharge')

        # Calculate cycles (simplified: total throughput / capacity)
        capacity = battery.get('technical', {}).get('capacity_nominal', 0)
        if capacity > 0:
            kpis['battery_cycles'] = (battery_charge + battery_discharge) / (2 * capacity)
        else:
            kpis['battery_cycles'] = 0

        # Round-trip efficiency
        if battery_charge > 0:
            kpis['battery_efficiency'] = battery_discharge / battery_charge
        else:
            kpis['battery_efficiency'] = 0

        kpis['battery_charge_total'] = battery_charge
        kpis['battery_discharge_total'] = battery_discharge

        return kpis

    def _calculate_peak_shaving_kpis(self, flows: Dict) -> Dict[str, float]:
        """Calculate peak shaving KPIs.

        Args:
            flows: Flow data dictionary

        Returns:
            Dictionary of peak shaving KPIs
        """
        kpis = {}

        # Get grid import time series
        grid_flow = None
        for flow_name, flow_data in flows.items():
            if 'grid' in flow_name.lower() and 'import' in flow_name.lower():
                if isinstance(flow_data, dict):
                    grid_flow = flow_data.get('values', [])
                break

        if grid_flow and len(grid_flow) > 0:
            grid_array = np.array(grid_flow)
            kpis['peak_demand'] = float(np.max(grid_array))
            kpis['average_demand'] = float(np.mean(grid_array))

            if kpis['average_demand'] > 0:
                kpis['peak_to_average_ratio'] = kpis['peak_demand'] / kpis['average_demand']
            else:
                kpis['peak_to_average_ratio'] = 0

            # Load factor (average / peak)
            if kpis['peak_demand'] > 0:
                kpis['load_factor'] = kpis['average_demand'] / kpis['peak_demand']
            else:
                kpis['load_factor'] = 0

        return kpis

    def _get_flow_sum(self, flows: Dict, component: str, direction: str = None) -> float:
        """Get the sum of flows for a component.

        Args:
            flows: Dictionary of all flows
            component: Component name to filter
            direction: Optional direction filter ('input', 'output', 'charge', 'discharge', 'import', 'export')

        Returns:
            Sum of matching flows
        """
        total = 0

        for flow_name, flow_data in flows.items():
            # Check if flow involves the component
            if component.lower() not in flow_name.lower():
                continue

            # Check direction if specified
            if direction:
                if direction.lower() not in flow_name.lower():
                    continue

            # Sum the flow values
            if isinstance(flow_data, dict):
                values = flow_data.get('values', [])
                if len(values) > 0:
                    total += np.sum(values)
            elif isinstance(flow_data, (list, np.ndarray)):
                total += np.sum(flow_data)

        return float(total)