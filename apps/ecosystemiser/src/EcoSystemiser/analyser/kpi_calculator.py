"""KPI calculation module for system analysis."""
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, List
import json
from EcoSystemiser.hive_logging_adapter import get_logger
logger = get_logger(__name__)

class KPICalculator:
    """Calculate key performance indicators from simulation results."""

    def __init__(self):
        """Initialize KPI calculator."""
        self.results = None
        self.system_type = None

    def calculate_from_system(self, system) -> Dict[str, float]:
        """Calculate KPIs directly from a solved system object.

        Args:
            system: Solved System object

        Returns:
            Dictionary of calculated KPIs
        """
        kpis = {}

        # Determine system type
        self.system_type = self._detect_system_type(system)

        if self.system_type == "energy":
            kpis.update(self._calculate_energy_kpis(system))
        elif self.system_type == "water":
            kpis.update(self._calculate_water_kpis(system))

        # Add common KPIs
        kpis.update(self._calculate_common_kpis(system))

        return kpis

    def calculate_from_file(self, results_path: Path) -> Dict[str, float]:
        """Calculate KPIs from saved results file.

        Args:
            results_path: Path to results file (JSON or Parquet)

        Returns:
            Dictionary of calculated KPIs
        """
        # Load results
        if results_path.suffix == '.json':
            with open(results_path, 'r') as f:
                self.results = json.load(f)
        elif results_path.suffix == '.parquet':
            import pyarrow.parquet as pq
            self.results = pq.read_table(results_path).to_pydict()
        else:
            raise ValueError(f"Unsupported file format: {results_path.suffix}")

        # Calculate KPIs based on loaded data
        return self._calculate_kpis_from_dict(self.results)

    def _detect_system_type(self, system) -> str:
        """Detect whether system is energy or water based.

        Args:
            system: System object

        Returns:
            'energy' or 'water'
        """
        # Check component types and media
        media_counts = {}
        for comp in system.components.values():
            media = comp.medium
            media_counts[media] = media_counts.get(media, 0) + 1

        # Determine dominant medium
        if media_counts.get('electricity', 0) > media_counts.get('water', 0):
            return 'energy'
        else:
            return 'water'

    def _calculate_energy_kpis(self, system) -> Dict[str, float]:
        """Calculate energy-specific KPIs.

        Args:
            system: Energy system object

        Returns:
            Dictionary of energy KPIs
        """
        kpis = {}

        # Grid interaction metrics
        total_import = 0
        total_export = 0
        peak_import = 0
        peak_export = 0

        for comp in system.components.values():
            if comp.type == "transmission" and comp.medium == "electricity":
                # Grid import (draw)
                if 'P_draw' in comp.flows.get('source', {}):
                    flow = comp.flows['source']['P_draw']['value']
                    if isinstance(flow, np.ndarray):
                        total_import = float(np.sum(flow))
                        peak_import = float(np.max(flow))

                # Grid export (feed)
                if 'P_feed' in comp.flows.get('sink', {}):
                    flow = comp.flows['sink']['P_feed']['value']
                    if isinstance(flow, np.ndarray):
                        total_export = float(np.sum(flow))
                        peak_export = float(np.max(flow))

        kpis['total_grid_import_kwh'] = total_import
        kpis['total_grid_export_kwh'] = total_export
        kpis['peak_grid_import_kw'] = peak_import
        kpis['peak_grid_export_kw'] = peak_export
        kpis['net_grid_usage_kwh'] = total_import - total_export

        # Renewable generation metrics
        total_solar = 0
        total_generation = 0

        for comp in system.components.values():
            if comp.type == "generation":
                if hasattr(comp, 'profile') and comp.profile is not None:
                    gen = np.sum(comp.profile)
                    total_generation += gen
                    if 'solar' in comp.name.lower():
                        total_solar += gen

        kpis['total_generation_kwh'] = float(total_generation)
        kpis['total_solar_kwh'] = float(total_solar)

        # Self-consumption and self-sufficiency
        if total_generation > 0:
            self_consumed = total_generation - total_export
            kpis['self_consumption_rate'] = float(self_consumed / total_generation)
            kpis['renewable_fraction'] = float(total_generation / (total_generation + total_import))
        else:
            kpis['self_consumption_rate'] = 0.0
            kpis['renewable_fraction'] = 0.0

        # Storage utilization
        for comp in system.components.values():
            if comp.type == "storage" and comp.medium == "electricity":
                if hasattr(comp, 'E') and isinstance(comp.E, np.ndarray):
                    kpis[f'{comp.name}_avg_soc'] = float(np.mean(comp.E) / comp.E_max)
                    kpis[f'{comp.name}_cycles'] = self._calculate_battery_cycles(comp.E)

        return kpis

    def _calculate_water_kpis(self, system) -> Dict[str, float]:
        """Calculate water-specific KPIs.

        Args:
            system: Water system object

        Returns:
            Dictionary of water KPIs
        """
        kpis = {}

        # Water grid usage
        total_grid_water = 0
        for comp in system.components.values():
            if comp.type == "transmission" and comp.medium == "water":
                if 'W_draw' in comp.flows.get('source', {}):
                    flow = comp.flows['source']['W_draw']['value']
                    if isinstance(flow, np.ndarray):
                        total_grid_water = float(np.sum(flow))

        kpis['total_grid_water_m3'] = total_grid_water

        # Rainwater harvesting
        total_rainwater = 0
        for comp in system.components.values():
            if 'rainwater' in comp.name.lower():
                for flow_dict in comp.flows.values():
                    for flow in flow_dict.values():
                        if isinstance(flow['value'], np.ndarray):
                            total_rainwater += np.sum(flow['value'])

        kpis['total_rainwater_harvested_m3'] = float(total_rainwater)

        # Water storage utilization
        for comp in system.components.values():
            if comp.type == "storage" and comp.medium == "water":
                if hasattr(comp, 'E') and isinstance(comp.E, np.ndarray):
                    kpis[f'{comp.name}_avg_level'] = float(np.mean(comp.E))
                    kpis[f'{comp.name}_min_level'] = float(np.min(comp.E))
                    kpis[f'{comp.name}_max_level'] = float(np.max(comp.E))

        # Overflow and evaporation losses
        total_overflow = 0
        total_evaporation = 0

        for comp in system.components.values():
            if 'overflow' in comp.name.lower():
                for flow_dict in comp.flows.values():
                    for flow in flow_dict.values():
                        if isinstance(flow['value'], np.ndarray):
                            total_overflow += np.sum(flow['value'])

            if 'evaporation' in comp.name.lower():
                for flow_dict in comp.flows.values():
                    for flow in flow_dict.values():
                        if isinstance(flow['value'], np.ndarray):
                            total_evaporation += np.sum(flow['value'])

        kpis['total_overflow_m3'] = float(total_overflow)
        kpis['total_evaporation_m3'] = float(total_evaporation)

        # Water self-sufficiency
        if total_rainwater > 0:
            kpis['rainwater_utilization_rate'] = float(
                (total_rainwater - total_overflow) / total_rainwater
            )

        return kpis

    def _calculate_common_kpis(self, system) -> Dict[str, float]:
        """Calculate KPIs common to all system types.

        Args:
            system: System object

        Returns:
            Dictionary of common KPIs
        """
        kpis = {}

        # Economic KPIs
        total_capex = 0
        total_opex = 0

        for comp in system.components.values():
            if hasattr(comp, 'economic') and comp.economic:
                total_capex += comp.economic.capex
                total_opex += comp.economic.opex_fix

        kpis['total_capex_eur'] = float(total_capex)
        kpis['annual_opex_eur'] = float(total_opex)

        # Environmental KPIs
        total_embodied_co2 = 0

        for comp in system.components.values():
            if hasattr(comp, 'environmental') and comp.environmental:
                total_embodied_co2 += comp.environmental.co2_embodied

        kpis['total_embodied_co2_kg'] = float(total_embodied_co2)

        # System complexity metrics
        kpis['num_components'] = len(system.components)
        kpis['num_connections'] = len(system.flows)

        return kpis

    def _calculate_battery_cycles(self, energy_levels: np.ndarray) -> float:
        """Calculate equivalent full cycles for a battery.

        Args:
            energy_levels: Array of energy levels over time

        Returns:
            Number of equivalent full cycles
        """
        if len(energy_levels) < 2:
            return 0.0

        # Calculate energy throughput
        energy_changes = np.abs(np.diff(energy_levels))
        total_throughput = np.sum(energy_changes)

        # Assume one full cycle = 2 * E_max throughput
        # (full discharge + full charge)
        E_max = np.max(energy_levels)
        if E_max > 0:
            cycles = total_throughput / (2 * E_max)
        else:
            cycles = 0.0

        return float(cycles)

    def _calculate_kpis_from_dict(self, results_dict: Dict) -> Dict[str, float]:
        """Calculate KPIs from a results dictionary.

        Args:
            results_dict: Dictionary containing simulation results

        Returns:
            Dictionary of calculated KPIs
        """
        kpis = {}

        # Extract flow-based KPIs
        if 'flows' in results_dict:
            for flow_name, flow_data in results_dict['flows'].items():
                if 'value' in flow_data and isinstance(flow_data['value'], list):
                    values = np.array(flow_data['value'])
                    kpis[f'{flow_name}_total'] = float(np.sum(values))
                    kpis[f'{flow_name}_mean'] = float(np.mean(values))
                    kpis[f'{flow_name}_peak'] = float(np.max(values))

        # Extract component state KPIs
        if 'components' in results_dict:
            for comp_name, comp_data in results_dict['components'].items():
                if 'E' in comp_data and isinstance(comp_data['E'], list):
                    levels = np.array(comp_data['E'])
                    kpis[f'{comp_name}_avg_level'] = float(np.mean(levels))

        return kpis

    def generate_summary_report(self, kpis: Dict[str, float]) -> str:
        """Generate a human-readable summary report from KPIs.

        Args:
            kpis: Dictionary of calculated KPIs

        Returns:
            Formatted summary report string
        """
        report = []
        report.append("=" * 60)
        report.append("SIMULATION KPI SUMMARY REPORT")
        report.append("=" * 60)

        # Group KPIs by category
        categories = {
            'Grid Interaction': ['grid_import', 'grid_export', 'net_grid'],
            'Renewable Generation': ['solar', 'generation', 'renewable'],
            'Storage': ['soc', 'cycles', 'level'],
            'Economic': ['capex', 'opex', 'cost'],
            'Environmental': ['co2', 'carbon'],
            'Water': ['water', 'rainwater', 'overflow', 'evaporation']
        }

        for category, keywords in categories.items():
            category_kpis = {
                k: v for k, v in kpis.items()
                if any(kw in k.lower() for kw in keywords)
            }

            if category_kpis:
                report.append(f"\n{category}:")
                report.append("-" * 40)
                for key, value in category_kpis.items():
                    # Format the key nicely
                    display_key = key.replace('_', ' ').title()
                    # Format the value based on type
                    if 'rate' in key or 'fraction' in key:
                        display_value = f"{value:.1%}"
                    elif 'eur' in key or 'cost' in key:
                        display_value = f"€{value:,.2f}"
                    else:
                        display_value = f"{value:,.2f}"

                    report.append(f"  {display_key}: {display_value}")

        report.append("\n" + "=" * 60)
        return '\n'.join(report)