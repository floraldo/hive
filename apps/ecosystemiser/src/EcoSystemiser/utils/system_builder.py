"""Dynamic system builder for configuration-driven system assembly."""

from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import yaml
from ecosystemiser.component_data.repository import ComponentRepository

# Import all components to ensure they are registered
from ecosystemiser.system_model.components.energy import (
    Battery,
    BatteryParams,
    ElectricBoiler,
    ElectricBoilerParams,
    Grid,
    GridParams,
    HeatBuffer,
    HeatBufferParams,
    HeatDemand,
    HeatDemandParams,
    HeatPump,
    HeatPumpParams,
    PowerDemand,
    PowerDemandParams,
    SolarPV,
    SolarPVParams,
)
from ecosystemiser.system_model.components.shared.registry import (
    COMPONENT_REGISTRY,
    get_component_class,
)
from ecosystemiser.system_model.system import System
from hive_logging import get_logger

logger = get_logger(__name__)


class SystemBuilder:
    """Build System objects from configuration files using dynamic registry pattern."""

    def __init__(self, config_path: Path, component_repo: ComponentRepository):
        """Initialize dynamic system builder.

        Args:
            config_path: Path to system configuration YAML
            component_repo: Repository for component data
        """
        self.config_path = Path(config_path)
        self.component_repo = component_repo

        # Log available components from registry
        available_components = list(COMPONENT_REGISTRY.keys())
        logger.info(
            f"Initialized SystemBuilder with {len(available_components)} registered components: {available_components}"
        )

    def list_available_components(self) -> Dict[str, str]:
        """List all available component types and their descriptions.

        Returns:
            Dictionary mapping component type to description
        """
        available = {}
        for comp_type, comp_class in COMPONENT_REGISTRY.items():
            # Get component description from docstring or class name
            desc = (
                comp_class.__doc__.split("\n")[0]
                if comp_class.__doc__
                else f"{comp_type} component"
            )
            available[comp_type] = desc

        return available

    def build(self) -> System:
        """Build complete system from configuration.

        Returns:
            Configured System object
        """
        # Load system configuration
        with open(self.config_path, "r") as f:
            config = yaml.safe_load(f)

        # Validate configuration structure
        self._validate_config(config)

        # Create system
        system = System(config["system_id"], config.get("timesteps", 24))

        # Add components
        for comp_config in config["components"]:
            component = self._create_component(comp_config, system.N)
            system.add_component(component)

        # Create connections
        for conn in config["connections"]:
            system.connect(
                conn["from"], conn["to"], conn["type"], conn.get("bidirectional", False)
            )

        logger.info(
            f"Built system '{system.system_id}' with {len(system.components)} components"
        )
        return system

    def _validate_config(self, config: Dict[str, Any]):
        """Validate system configuration structure.

        Args:
            config: System configuration dictionary

        Raises:
            ValueError: If configuration is invalid
        """
        required_keys = ["system_id", "components", "connections"]
        for key in required_keys:
            if key not in config:
                raise ValueError(f"Missing required configuration key: {key}")

        if not isinstance(config["components"], list):
            raise ValueError("'components' must be a list")

        if not isinstance(config["connections"], list):
            raise ValueError("'connections' must be a list")

    def _create_component(self, comp_config: Dict[str, Any], n: int):
        """Create a component instance from configuration.

        Args:
            comp_config: Component configuration
            n: Number of timesteps

        Returns:
            Component instance
        """
        name = comp_config.get("name")
        if not name:
            raise ValueError("Component must have a 'name'")

        # Determine if using component library or inline definition
        if "component_id" in comp_config:
            # Load from component library
            comp_data = self.component_repo.get_component_data(
                comp_config["component_id"]
            )

            # Standardize on 'component_class' key
            comp_class_name = comp_data.get("component_class")
            if not comp_class_name:
                raise ValueError(
                    f"Component data for {comp_config['component_id']} missing 'component_class'"
                )

            # Merge any override parameters from config
            params_dict = comp_data.copy()
            if "params" in comp_config:
                params_dict.update(comp_config["params"])
        else:
            # Inline definition - standardize on 'component_class' key
            comp_class_name = comp_config.get("component_class")
            if not comp_class_name:
                raise ValueError(f"Component {name} must specify 'component_class'")

            params_dict = comp_config.get("params", {})

        # Get component class from registry (DYNAMIC - NO HARDCODING!)
        try:
            ComponentClass = get_component_class(comp_class_name)
        except ValueError as e:
            available = list(COMPONENT_REGISTRY.keys())
            raise ValueError(
                f"Unknown component class: {comp_class_name}. Available: {available}"
            ) from e

        # Get the parameter class from the component
        if hasattr(ComponentClass, "PARAMS_MODEL"):
            ParamsModel = ComponentClass.PARAMS_MODEL
        else:
            # Fallback for components that don't have PARAMS_MODEL
            param_class_name = f"{comp_class_name}Params"
            module = ComponentClass.__module__
            import importlib

            component_module = importlib.import_module(module)
            ParamsModel = getattr(component_module, param_class_name)

        # Create params instance with validation
        try:
            params = ParamsModel(**params_dict)
        except Exception as e:
            raise ValueError(
                f"Invalid parameters for {comp_class_name} component '{name}': {e}"
            )

        # Create component using registry pattern
        return ComponentClass(name, params, n)

    def assign_profiles(self, system: System, profiles: Dict[str, Any]):
        """Assign loaded profiles to system components.

        Args:
            system: System object
            profiles: Dictionary of profile data
        """
        for comp_name, component in system.components.items():
            # Check if component needs a profile
            if hasattr(component, "technical") and component.technical:
                profile_name = getattr(component.technical, "profile_name", None)

                if profile_name and profile_name in profiles:
                    # Assign profile to component
                    profile_data = profiles[profile_name]

                    if isinstance(profile_data, np.ndarray):
                        component.profile = profile_data
                    elif isinstance(profile_data, list):
                        component.profile = np.array(profile_data)
                    else:
                        logger.warning(
                            f"Profile {profile_name} has unexpected type: {type(profile_data)}"
                        )

                    logger.debug(
                        f"Assigned profile '{profile_name}' to component '{comp_name}'"
                    )

    def create_minimal_test_system(self, N: int = 24) -> System:
        """Create a minimal test system for validation.

        Args:
            N: Number of timesteps

        Returns:
            Minimal test system with 4 components
        """
        import numpy as np

        system = System("minimal_test", N)

        # Create simple profiles
        solar_profile = np.zeros(N)
        for t in range(N):
            if 6 <= t <= 18:  # Daylight hours
                solar_profile[t] = np.sin((t - 6) * np.pi / 12) * 5.0

        demand_profile = np.ones(N) * 1.0  # 1 kW baseload
        demand_profile[7:9] = 2.0  # Morning peak
        demand_profile[18:21] = 2.5  # Evening peak

        # Create components using dynamic registry
        grid_class = get_component_class("Grid")
        grid_params = grid_class.PARAMS_MODEL(
            P_max=100, import_tariff=0.25, feed_in_tariff=0.08
        )
        grid = grid_class("Grid", grid_params, N)
        system.add_component(grid)

        battery_class = get_component_class("Battery")
        battery_params = battery_class.PARAMS_MODEL(
            P_max=5, E_max=10, E_init=5, eta_charge=0.95, eta_discharge=0.95
        )
        battery = battery_class("Battery", battery_params, N)
        system.add_component(battery)

        solar_class = get_component_class("SolarPV")
        solar_params = solar_class.PARAMS_MODEL(
            P_profile=solar_profile.tolist(), P_max=10
        )
        solar = solar_class("SolarPV", solar_params, N)
        system.add_component(solar)

        demand_class = get_component_class("PowerDemand")
        demand_params = demand_class.PARAMS_MODEL(
            P_profile=demand_profile.tolist(), P_max=5
        )
        demand = demand_class("PowerDemand", demand_params, N)
        system.add_component(demand)

        # Create connections
        system.connect("Grid", "PowerDemand", "electricity")
        system.connect("Grid", "Battery", "electricity")
        system.connect("SolarPV", "PowerDemand", "electricity")
        system.connect("SolarPV", "Battery", "electricity")
        system.connect("SolarPV", "Grid", "electricity")
        system.connect("Battery", "PowerDemand", "electricity")
        system.connect("Battery", "Grid", "electricity")

        logger.info(
            "Built minimal test system with 4 components using dynamic registry"
        )
        return system
