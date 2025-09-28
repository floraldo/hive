"""
Legacy alias for EcoSystemiser event bus.

This module provides backward compatibility by importing from the new core module.
All new code should import directly from ecosystemiser.core.bus.
"""

# Import everything from the new core module
from ecosystemiser.core.bus import EcoSystemiserEventBus, get_ecosystemiser_event_bus

# Legacy aliases for backward compatibility
Bus = EcoSystemiserEventBus
get_bus = get_ecosystemiser_event_bus

# Export main components
__all__ = [
    "EcoSystemiserEventBus",
    "get_ecosystemiser_event_bus",
    "Bus",  # Legacy alias
    "get_bus",  # Legacy alias
]
