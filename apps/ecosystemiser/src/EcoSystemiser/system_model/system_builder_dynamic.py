"""Dynamic system builder using registry pattern for creating and configuring systems."""

import logging
from typing import Dict, Any, Optional
from pathlib import Path
import yaml
import json

# Import components to ensure they are registered
from system_model.components.energy import *
from system_model.components.shared.registry import COMPONENT_REGISTRY, get_component_class
from system_model.system import System

logger = logging.getLogger(__name__)


class DynamicSystemBuilder:
    """Builder class for constructing systems from configuration using registry pattern."""

    def __init__(self):
        """Initialize the dynamic system builder."""
        # No hardcoded component registry - uses the global registry!
        logger.info(f"Initialized with {len(COMPONENT_REGISTRY)} registered components: {list(COMPONENT_REGISTRY.keys())}")

    def create_component(self, component_type: str, params: Dict[str, Any], name: Optional[str] = None):
        """
        Create a component instance from type and parameters using registry pattern.

        Args:
            component_type: Type of component to create
            params: Dictionary of component parameters
            name: Optional component name (defaults to type)

        Returns:
            Component instance
        """
        # Get component class from registry
        component_class = get_component_class(component_type)

        # Use provided name or default to type
        component_name = name or component_type

        # Get the parameter class from the component
        params_class = component_class.PARAMS_MODEL

        # Create parameter object
        param_obj = params_class(**params)

        # Create component using DRY initialization
        component = component_class(name=component_name, params=param_obj)

        logger.debug(f"Created component: {component_name} of type {component_type}")
        return component

    def list_available_components(self) -> Dict[str, str]:
        """
        List all available component types and their descriptions.

        Returns:
            Dictionary mapping component type to description
        """
        available = {}
        for comp_type, comp_class in COMPONENT_REGISTRY.items():
            # Get component description from docstring or class name
            desc = comp_class.__doc__.split('\n')[0] if comp_class.__doc__ else f"{comp_type} component"
            available[comp_type] = desc

        return available

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

        # Create components dynamically
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

        # Create components using registry pattern
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

    def build_thermal_test_system(self, N: int = 24) -> System:
        """
        Build a comprehensive thermal test system with 8 components.

        Args:
            N: Number of timesteps

        Returns:
            Thermal test system with electrical and thermal components
        """
        import numpy as np

        system = System('thermal_test', N)

        # Create profiles
        # Solar profile (peak at midday)
        solar_profile = np.zeros(N)
        for t in range(N):
            if 6 <= t <= 18:  # Daylight hours
                solar_profile[t] = np.sin((t - 6) * np.pi / 12) * 8.0

        # Electrical demand profile
        power_demand = np.ones(N) * 1.5  # 1.5 kW baseload
        power_demand[7:9] = 3.0   # Morning peak
        power_demand[18:21] = 4.0  # Evening peak

        # Heat demand profile (higher in morning and evening)
        heat_demand = np.ones(N) * 2.0  # 2 kW baseload
        heat_demand[6:9] = 5.0    # Morning heating
        heat_demand[18:22] = 4.5  # Evening heating
        heat_demand[0:6] = 1.0    # Night setback
        heat_demand[22:24] = 1.0  # Night setback

        # ---- Electrical Components ----
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
            'P_max': 12
        })
        system.add_component(solar)

        power_load = self.create_component('PowerDemand', {
            'P_profile': power_demand.tolist(),
            'P_max': 6
        })
        system.add_component(power_load)

        # ---- Thermal Components ----
        heat_pump = self.create_component('HeatPump', {
            'COP': 3.5,
            'eta': 0.90,
            'P_max': 3
        })
        system.add_component(heat_pump)

        electric_boiler = self.create_component('ElectricBoiler', {
            'eta': 0.95,
            'P_max': 5
        })
        system.add_component(electric_boiler)

        heat_buffer = self.create_component('HeatBuffer', {
            'P_max': 4,
            'E_max': 20,
            'E_init': 10,
            'eta': 0.90
        })
        system.add_component(heat_buffer)

        heat_load = self.create_component('HeatDemand', {
            'H_profile': heat_demand.tolist(),
            'H_max': 6
        })
        system.add_component(heat_load)

        # ---- Electrical Connections ----
        system.connect('Grid', 'PowerDemand', 'electricity')
        system.connect('Grid', 'Battery', 'electricity')
        system.connect('Grid', 'HeatPump', 'electricity')
        system.connect('Grid', 'ElectricBoiler', 'electricity')
        system.connect('SolarPV', 'PowerDemand', 'electricity')
        system.connect('SolarPV', 'Battery', 'electricity')
        system.connect('SolarPV', 'HeatPump', 'electricity')
        system.connect('SolarPV', 'ElectricBoiler', 'electricity')
        system.connect('SolarPV', 'Grid', 'electricity')
        system.connect('Battery', 'PowerDemand', 'electricity')
        system.connect('Battery', 'HeatPump', 'electricity')
        system.connect('Battery', 'ElectricBoiler', 'electricity')
        system.connect('Battery', 'Grid', 'electricity')

        # ---- Thermal Connections ----
        system.connect('HeatPump', 'HeatDemand', 'heat')
        system.connect('HeatPump', 'HeatBuffer', 'heat')
        system.connect('ElectricBoiler', 'HeatDemand', 'heat')
        system.connect('ElectricBoiler', 'HeatBuffer', 'heat')
        system.connect('HeatBuffer', 'HeatDemand', 'heat')

        logger.info("Built thermal system with 8 components (4 electrical + 4 thermal)")
        return system


# Create a default instance for convenience
system_builder = DynamicSystemBuilder()