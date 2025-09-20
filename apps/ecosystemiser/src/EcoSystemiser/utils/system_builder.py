"""System builder for configuration-driven system assembly."""
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
import numpy as np
import logging

from ..system_model.system import System
from ..component_data.repository import ComponentRepository

logger = logging.getLogger(__name__)

class SystemBuilder:
    """Build System objects from configuration files."""

    # Component class registry - manual for now, can be automated later
    COMPONENT_CLASSES = {}

    def __init__(self, config_path: Path, component_repo: ComponentRepository):
        """Initialize system builder.

        Args:
            config_path: Path to system configuration YAML
            component_repo: Repository for component data
        """
        self.config_path = Path(config_path)
        self.component_repo = component_repo
        self._load_component_classes()

    def _load_component_classes(self):
        """Load component classes dynamically.

        Future: This could scan the components directory automatically.
        For now, we import manually.
        """
        # Import all component classes
        try:
            from ..system_model.components.energy.battery import Battery, BatteryParams
            from ..system_model.components.energy.grid import Grid, GridParams
            from ..system_model.components.energy.solar_pv import SolarPV, SolarPVParams
            from ..system_model.components.energy.power_demand import PowerDemand, PowerDemandParams

            # Register classes with their params models
            self.COMPONENT_CLASSES.update({
                'Battery': (Battery, BatteryParams),
                'Grid': (Grid, GridParams),
                'SolarPV': (SolarPV, SolarPVParams),
                'PowerDemand': (PowerDemand, PowerDemandParams),
                # Add more as they're created
            })
        except ImportError as e:
            logger.warning(f"Could not import some component classes: {e}")

    def build(self) -> System:
        """Build complete system from configuration.

        Returns:
            Configured System object
        """
        # Load system configuration
        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)

        # Validate configuration structure
        self._validate_config(config)

        # Create system
        system = System(config['system_id'], config.get('timesteps', 24))

        # Add components
        for comp_config in config['components']:
            component = self._create_component(comp_config, system.N)
            system.add_component(component)

        # Create connections
        for conn in config['connections']:
            system.connect(
                conn['from'],
                conn['to'],
                conn['type'],
                conn.get('bidirectional', False)
            )

        logger.info(f"Built system '{system.system_id}' with {len(system.components)} components")
        return system

    def _validate_config(self, config: Dict[str, Any]):
        """Validate system configuration structure.

        Args:
            config: System configuration dictionary

        Raises:
            ValueError: If configuration is invalid
        """
        required_keys = ['system_id', 'components', 'connections']
        for key in required_keys:
            if key not in config:
                raise ValueError(f"Missing required configuration key: {key}")

        if not isinstance(config['components'], list):
            raise ValueError("'components' must be a list")

        if not isinstance(config['connections'], list):
            raise ValueError("'connections' must be a list")

    def _create_component(self, comp_config: Dict[str, Any], n: int):
        """Create a component instance from configuration.

        Args:
            comp_config: Component configuration
            n: Number of timesteps

        Returns:
            Component instance
        """
        name = comp_config.get('name')
        if not name:
            raise ValueError("Component must have a 'name'")

        # Determine if using component library or inline definition
        if 'component_id' in comp_config:
            # Load from component library
            comp_data = self.component_repo.get_component_data(comp_config['component_id'])

            # Standardize on 'component_class' key
            comp_class_name = comp_data.get('component_class')
            if not comp_class_name:
                raise ValueError(f"Component data for {comp_config['component_id']} missing 'component_class'")

            # Merge any override parameters from config
            params_dict = comp_data.copy()
            if 'params' in comp_config:
                params_dict.update(comp_config['params'])
        else:
            # Inline definition - standardize on 'component_class' key
            comp_class_name = comp_config.get('component_class')
            if not comp_class_name:
                raise ValueError(f"Component {name} must specify 'component_class'")

            params_dict = comp_config.get('params', {})

        # Get component class and params model
        if comp_class_name not in self.COMPONENT_CLASSES:
            available = ', '.join(self.COMPONENT_CLASSES.keys())
            raise ValueError(f"Unknown component class: {comp_class_name}. Available: {available}")

        ComponentClass, ParamsModel = self.COMPONENT_CLASSES[comp_class_name]

        # Create params instance with validation
        try:
            params = ParamsModel(**params_dict)
        except Exception as e:
            raise ValueError(f"Invalid parameters for {comp_class_name} component '{name}': {e}")

        # Create component
        return ComponentClass(name, params, n)

    def assign_profiles(self, system: System, profiles: Dict[str, Any]):
        """Assign loaded profiles to system components.

        Args:
            system: System object
            profiles: Dictionary of profile data
        """
        for comp_name, component in system.components.items():
            # Check if component needs a profile
            if hasattr(component, 'technical') and component.technical:
                profile_name = getattr(component.technical, 'profile_name', None)

                if profile_name and profile_name in profiles:
                    # Assign profile to component
                    profile_data = profiles[profile_name]

                    if isinstance(profile_data, np.ndarray):
                        component.profile = profile_data
                    elif isinstance(profile_data, list):
                        component.profile = np.array(profile_data)
                    else:
                        logger.warning(f"Profile {profile_name} has unexpected type: {type(profile_data)}")

                    logger.debug(f"Assigned profile '{profile_name}' to component '{comp_name}'")

    @classmethod
    def register_component_class(cls, name: str, component_class, params_model):
        """Register a new component class.

        Args:
            name: Class name identifier
            component_class: Component class
            params_model: Pydantic model for parameters
        """
        cls.COMPONENT_CLASSES[name] = (component_class, params_model)