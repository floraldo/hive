"""System builder for creating and configuring systems from specifications."""

import logging
from typing import Dict, Any, Optional
from pathlib import Path
import yaml
import json

from component_model.battery import Battery, BatteryParams
from component_model.grid import Grid, GridParams
from component_model.solar_pv import SolarPV, SolarPVParams
from component_model.power_demand import PowerDemand, PowerDemandParams
from system_model.system import System

logger = logging.getLogger(__name__)


class SystemBuilder:
    """Builder class for constructing systems from configuration."""

    def __init__(self):
        """Initialize the system builder."""
        self.component_registry = {
            'Battery': (Battery, BatteryParams),
            'Grid': (Grid, GridParams),
            'SolarPV': (SolarPV, SolarPVParams),
            'PowerDemand': (PowerDemand, PowerDemandParams),
        }

    def create_component(self, component_type: str, params: Dict[str, Any], name: Optional[str] = None):
        """
        Create a component instance from type and parameters.

        Args:
            component_type: Type of component to create
            params: Dictionary of component parameters
            name: Optional component name (defaults to type)

        Returns:
            Component instance
        """
        if component_type not in self.component_registry:
            raise ValueError(f"Unknown component type: {component_type}")

        component_class, params_class = self.component_registry[component_type]

        # Use provided name or default to type
        component_name = name or component_type

        # Create parameter object
        param_obj = params_class(**params)

        # Create component
        component = component_class(name=component_name, params=param_obj)

        logger.debug(f"Created component: {component_name} of type {component_type}")
        return component

    def build_system_from_config(self, config_path: Path) -> System:
        """
        Build a complete system from a configuration file.

        Args:
            config_path: Path to YAML or JSON configuration file

        Returns:
            Configured System instance
        """
        # Load configuration
        with open(config_path, 'r') as f:
            if config_path.suffix == '.yaml' or config_path.suffix == '.yml':
                config = yaml.safe_load(f)
            else:
                config = json.load(f)

        # Create system
        system_config = config.get('system', {})
        system = System(
            name=system_config.get('name', 'default_system'),
            N=system_config.get('timesteps', 24)
        )

        # Create components
        components_config = config.get('components', {})
        for comp_name, comp_config in components_config.items():
            comp_type = comp_config.pop('type')
            component = self.create_component(comp_type, comp_config, name=comp_name)
            system.add_component(component)

        # Create connections
        connections = config.get('connections', [])
        for conn in connections:
            system.connect(
                conn['source'],
                conn['target'],
                conn.get('medium', 'electricity')
            )

        logger.info(f"Built system '{system.name}' with {len(system.components)} components")
        return system

    def build_minimal_test_system(self, N: int = 24) -> System:
        """
        Build a minimal test system with 4 components for validation.

        Args:
            N: Number of timesteps

        Returns:
            Minimal test system
        """
        import numpy as np

        system = System('minimal_test', N)

        # Create simple profiles
        # Solar profile (peak at midday)
        solar_profile = np.zeros(N)
        for t in range(N):
            if 6 <= t <= 18:  # Daylight hours
                solar_profile[t] = np.sin((t - 6) * np.pi / 12) * 5.0

        # Demand profile (baseload + peaks)
        demand_profile = np.ones(N) * 1.0  # 1 kW baseload
        demand_profile[7:9] = 2.0   # Morning peak
        demand_profile[18:21] = 2.5  # Evening peak

        # Create components
        grid = self.create_component('Grid', {
            'P_max': 100,
            'import_tariff': 0.25,
            'feed_in_tariff': 0.08
        })
        system.add_component(grid)

        battery = self.create_component('Battery', {
            'P_max': 5,
            'E_max': 10,
            'E_init': 5,
            'eta_charge': 0.95,
            'eta_discharge': 0.95
        })
        system.add_component(battery)

        solar = self.create_component('SolarPV', {
            'P_profile': solar_profile.tolist(),
            'P_max': 10
        })
        system.add_component(solar)

        demand = self.create_component('PowerDemand', {
            'P_profile': demand_profile.tolist(),
            'P_max': 5
        })
        system.add_component(demand)

        # Create connections
        system.connect('Grid', 'PowerDemand', 'electricity')
        system.connect('Grid', 'Battery', 'electricity')
        system.connect('SolarPV', 'PowerDemand', 'electricity')
        system.connect('SolarPV', 'Battery', 'electricity')
        system.connect('SolarPV', 'Grid', 'electricity')
        system.connect('Battery', 'PowerDemand', 'electricity')
        system.connect('Battery', 'Grid', 'electricity')

        logger.info("Built minimal test system with 4 components")
        return system