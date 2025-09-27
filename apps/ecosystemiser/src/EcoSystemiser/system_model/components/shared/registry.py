"""Component Registry System for Dynamic Component Discovery.

This module implements a self-registering component pattern that allows
components to automatically register themselves for dynamic instantiation.
"""

from typing import Dict, Type, Optional
from EcoSystemiser.hive_logging_adapter import get_logger
logger = get_logger(__name__)

# The global registry dictionary - this is our central lookup table
COMPONENT_REGISTRY: Dict[str, Type["Component"]] = {}

def register_component(name: str):
    """
    A class decorator that registers a component blueprint in the global registry.

    This decorator enables plug-and-play extensibility. New components simply
    need to use this decorator and they become available to the system.

    Args:
        name: The string identifier for this component class (e.g., "Battery")

    Returns:
        The decorated class (unchanged)

    Example:
        @register_component("Battery")
        class Battery(Component):
            pass
    """
    def decorator(cls: Type["Component"]):
        if name in COMPONENT_REGISTRY:
            raise ValueError(f"Component '{name}' is already registered. "
                           f"Existing: {COMPONENT_REGISTRY[name]}, "
                           f"Attempted: {cls}")
        COMPONENT_REGISTRY[name] = cls
        logger.debug(f"Registered component: {name} -> {cls.__name__}")
        return cls
    return decorator

def get_component_class(name: str) -> Type["Component"]:
    """
    Retrieves a component class from the registry.

    Args:
        name: The registered name of the component

    Returns:
        The component class

    Raises:
        ValueError: If the component name is not found in the registry
    """
    if name not in COMPONENT_REGISTRY:
        available = list(COMPONENT_REGISTRY.keys())
        raise ValueError(f"Component class '{name}' not found in registry. "
                       f"Available components: {available}")
    return COMPONENT_REGISTRY[name]

def list_registered_components() -> Dict[str, str]:
    """
    Lists all registered components with their class names.

    Returns:
        Dictionary mapping component names to their class names
    """
    return {name: cls.__name__ for name, cls in COMPONENT_REGISTRY.items()}

def is_component_registered(name: str) -> bool:
    """
    Checks if a component is registered.

    Args:
        name: The component name to check

    Returns:
        True if the component is registered, False otherwise
    """
    return name in COMPONENT_REGISTRY

def clear_registry():
    """
    Clears the component registry (useful for testing).

    Warning: This should only be used in test environments.
    """
    global COMPONENT_REGISTRY
    COMPONENT_REGISTRY.clear()
    logger.warning("Component registry has been cleared")