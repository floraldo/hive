"""Parameter encoding for system configurations in optimization."""

from typing import Dict, Any, List, Tuple, Optional, Union
import numpy as np
from dataclasses import dataclass
from pathlib import Path
import yaml
from copy import deepcopy

from EcoSystemiser.hive_logging_adapter import get_logger

logger = get_logger(__name__)


@dataclass
class ParameterSpec:
    """Specification for an optimizable parameter."""
    name: str
    component: str
    parameter_path: str  # e.g., "technical.capacity_nominal"
    bounds: Tuple[float, float]  # (min, max)
    parameter_type: str = "continuous"  # continuous, integer, categorical
    units: Optional[str] = None
    description: Optional[str] = None
    scaling: str = "linear"  # linear, log, normalized


@dataclass
class EncodingSpec:
    """Complete specification for parameter encoding."""
    parameters: List[ParameterSpec]
    objective_weights: Optional[Dict[str, float]] = None
    constraint_definitions: Optional[List[Dict[str, Any]]] = None

    @property
    def dimensions(self) -> int:
        """Number of optimization dimensions."""
        return len(self.parameters)

    @property
    def bounds(self) -> List[Tuple[float, float]]:
        """Parameter bounds for optimization."""
        return [param.bounds for param in self.parameters]

    def get_parameter_names(self) -> List[str]:
        """Get list of parameter names."""
        return [param.name for param in self.parameters]


class ParameterEncoder:
    """Encodes and decodes parameters for optimization algorithms.

    This class handles the conversion between human-readable system
    configurations and the numerical parameter vectors used by
    optimization algorithms.
    """

    def __init__(self, encoding_spec: EncodingSpec):
        """Initialize parameter encoder.

        Args:
            encoding_spec: Specification for parameter encoding
        """
        self.spec = encoding_spec
        self.parameter_map = {param.name: param for param in self.spec.parameters}

    def encode(self, config: Dict[str, Any]) -> np.ndarray:
        """Encode system configuration to parameter vector.

        Args:
            config: System configuration dictionary

        Returns:
            Encoded parameter vector
        """
        vector = np.zeros(self.spec.dimensions)

        for i, param_spec in enumerate(self.spec.parameters):
            try:
                # Extract value from config
                value = self._extract_parameter_value(config, param_spec)

                # Apply scaling and bounds
                encoded_value = self._encode_parameter(value, param_spec)
                vector[i] = encoded_value

            except Exception as e:
                logger.warning(f"Failed to encode parameter {param_spec.name}: {e}")
                # Use middle of bounds as default
                vector[i] = (param_spec.bounds[0] + param_spec.bounds[1]) / 2

        return vector

    def decode(self, vector: np.ndarray, base_config: Dict[str, Any]) -> Dict[str, Any]:
        """Decode parameter vector to system configuration.

        Args:
            vector: Parameter vector from optimization
            base_config: Base configuration to modify

        Returns:
            Updated system configuration
        """
        if len(vector) != self.spec.dimensions:
            raise ValueError(f"Vector dimension {len(vector)} doesn't match "
                           f"expected {self.spec.dimensions}")

        # Create deep copy to avoid modifying original
        config = deepcopy(base_config)

        for i, param_spec in enumerate(self.spec.parameters):
            try:
                # Decode parameter value
                decoded_value = self._decode_parameter(vector[i], param_spec)

                # Update configuration
                self._set_parameter_value(config, param_spec, decoded_value)

            except Exception as e:
                logger.warning(f"Failed to decode parameter {param_spec.name}: {e}")
                continue

        return config

    def _extract_parameter_value(self, config: Dict[str, Any],
                                param_spec: ParameterSpec) -> float:
        """Extract parameter value from configuration.

        Args:
            config: System configuration
            param_spec: Parameter specification

        Returns:
            Parameter value
        """
        # Navigate through nested dictionaries
        value = config

        # First find the component
        if 'components' in config and param_spec.component in config['components']:
            value = config['components'][param_spec.component]
        else:
            raise ValueError(f"Component {param_spec.component} not found")

        # Then navigate the parameter path
        path_parts = param_spec.parameter_path.split('.')
        for part in path_parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                raise ValueError(f"Parameter path {param_spec.parameter_path} not found")

        # Convert to float
        try:
            return float(value)
        except (ValueError, TypeError):
            raise ValueError(f"Parameter {param_spec.name} is not numeric: {value}")

    def _set_parameter_value(self, config: Dict[str, Any],
                           param_spec: ParameterSpec, value: float):
        """Set parameter value in configuration.

        Args:
            config: System configuration to modify
            param_spec: Parameter specification
            value: New parameter value
        """
        # Ensure components section exists
        if 'components' not in config:
            config['components'] = {}

        # Ensure component exists
        if param_spec.component not in config['components']:
            config['components'][param_spec.component] = {}

        # Navigate to the parameter location
        current = config['components'][param_spec.component]
        path_parts = param_spec.parameter_path.split('.')

        # Navigate to parent of final key
        for part in path_parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]

        # Set the final value
        final_key = path_parts[-1]

        # Convert value based on parameter type
        if param_spec.parameter_type == "integer":
            current[final_key] = int(round(value))
        else:
            current[final_key] = float(value)

    def _encode_parameter(self, value: float, param_spec: ParameterSpec) -> float:
        """Encode a single parameter value.

        Args:
            value: Raw parameter value
            param_spec: Parameter specification

        Returns:
            Encoded value within bounds
        """
        min_val, max_val = param_spec.bounds

        # Apply scaling
        if param_spec.scaling == "log":
            if value <= 0:
                value = min_val
            value = np.log10(value)
            min_val = np.log10(max(min_val, 1e-10))
            max_val = np.log10(max_val)
        elif param_spec.scaling == "normalized":
            # Already handled by bounds
            pass

        # Ensure within bounds
        encoded = np.clip(value, min_val, max_val)
        return encoded

    def _decode_parameter(self, encoded_value: float, param_spec: ParameterSpec) -> float:
        """Decode a single parameter value.

        Args:
            encoded_value: Encoded parameter value
            param_spec: Parameter specification

        Returns:
            Decoded parameter value
        """
        min_val, max_val = param_spec.bounds
        value = encoded_value

        # Apply inverse scaling
        if param_spec.scaling == "log":
            value = 10 ** value
        elif param_spec.scaling == "normalized":
            # Scale from [0,1] to [min,max]
            value = min_val + value * (max_val - min_val)

        # Ensure within original bounds
        value = np.clip(value, min_val, max_val)

        return value

    def validate_vector(self, vector: np.ndarray) -> bool:
        """Validate that parameter vector is within bounds.

        Args:
            vector: Parameter vector to validate

        Returns:
            True if valid, False otherwise
        """
        if len(vector) != self.spec.dimensions:
            return False

        for i, param_spec in enumerate(self.spec.parameters):
            min_val, max_val = param_spec.bounds
            if not (min_val <= vector[i] <= max_val):
                return False

        return True

    def get_parameter_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all parameters.

        Returns:
            Dictionary with parameter information
        """
        info = {}
        for param in self.spec.parameters:
            info[param.name] = {
                'component': param.component,
                'parameter_path': param.parameter_path,
                'bounds': param.bounds,
                'type': param.parameter_type,
                'units': param.units,
                'description': param.description,
                'scaling': param.scaling
            }
        return info


class SystemConfigEncoder(ParameterEncoder):
    """Specialized encoder for EcoSystemiser system configurations.

    This class provides predefined parameter specifications for common
    energy system components and automatically detects optimizable
    parameters from system configurations.
    """

    # Predefined parameter specifications for common components
    COMPONENT_PARAMETERS = {
        'battery': [
            ParameterSpec(
                name='battery_capacity',
                component='battery',
                parameter_path='technical.capacity_nominal',
                bounds=(0, 1000),
                units='kWh',
                description='Battery storage capacity'
            ),
            ParameterSpec(
                name='battery_power',
                component='battery',
                parameter_path='technical.power_nominal',
                bounds=(0, 500),
                units='kW',
                description='Battery power rating'
            )
        ],
        'solar_pv': [
            ParameterSpec(
                name='solar_capacity',
                component='solar_pv',
                parameter_path='technical.capacity_nominal',
                bounds=(0, 2000),
                units='kW',
                description='Solar PV capacity'
            )
        ],
        'wind': [
            ParameterSpec(
                name='wind_capacity',
                component='wind',
                parameter_path='technical.capacity_nominal',
                bounds=(0, 1000),
                units='kW',
                description='Wind turbine capacity'
            )
        ],
        'heat_pump': [
            ParameterSpec(
                name='heat_pump_capacity',
                component='heat_pump',
                parameter_path='technical.capacity_nominal',
                bounds=(0, 100),
                units='kW',
                description='Heat pump capacity'
            )
        ]
    }

    @classmethod
    def from_config(cls, config_path: Union[str, Path],
                   component_selection: Optional[List[str]] = None,
                   custom_bounds: Optional[Dict[str, Tuple[float, float]]] = None) -> 'SystemConfigEncoder':
        """Create encoder from system configuration file.

        Args:
            config_path: Path to system configuration YAML file
            component_selection: List of components to optimize (None = all)
            custom_bounds: Custom bounds for parameters

        Returns:
            SystemConfigEncoder instance
        """
        # Load configuration
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        # Detect available components
        available_components = set()
        if 'components' in config:
            available_components = set(config['components'].keys())

        # Build parameter list
        parameters = []
        for component, param_specs in cls.COMPONENT_PARAMETERS.items():
            if component in available_components:
                if component_selection is None or component in component_selection:
                    for param_spec in param_specs:
                        # Apply custom bounds if provided
                        if custom_bounds and param_spec.name in custom_bounds:
                            param_spec = dataclass.replace(
                                param_spec,
                                bounds=custom_bounds[param_spec.name]
                            )
                        parameters.append(param_spec)

        if not parameters:
            raise ValueError("No optimizable parameters found in configuration")

        logger.info(f"Created encoder with {len(parameters)} parameters: "
                   f"{[p.name for p in parameters]}")

        encoding_spec = EncodingSpec(parameters=parameters)
        return cls(encoding_spec)

    @classmethod
    def from_parameter_list(cls, parameter_definitions: List[Dict[str, Any]]) -> 'SystemConfigEncoder':
        """Create encoder from parameter definition list.

        Args:
            parameter_definitions: List of parameter definition dictionaries

        Returns:
            SystemConfigEncoder instance
        """
        parameters = []
        for param_def in parameter_definitions:
            param_spec = ParameterSpec(**param_def)
            parameters.append(param_spec)

        encoding_spec = EncodingSpec(parameters=parameters)
        return cls(encoding_spec)

    def suggest_bounds_from_config(self, config: Dict[str, Any],
                                  scaling_factor: float = 2.0) -> Dict[str, Tuple[float, float]]:
        """Suggest parameter bounds based on current configuration values.

        Args:
            config: System configuration
            scaling_factor: Factor to scale current values for bounds

        Returns:
            Dictionary of suggested bounds
        """
        suggested_bounds = {}

        for param_spec in self.spec.parameters:
            try:
                current_value = self._extract_parameter_value(config, param_spec)
                if current_value > 0:
                    min_bound = current_value / scaling_factor
                    max_bound = current_value * scaling_factor
                    suggested_bounds[param_spec.name] = (min_bound, max_bound)
                else:
                    # Use default bounds for zero values
                    suggested_bounds[param_spec.name] = param_spec.bounds

            except Exception as e:
                logger.warning(f"Could not extract value for {param_spec.name}: {e}")
                suggested_bounds[param_spec.name] = param_spec.bounds

        return suggested_bounds