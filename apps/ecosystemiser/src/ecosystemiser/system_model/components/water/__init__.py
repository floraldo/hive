from hive_logging import get_logger

logger = get_logger(__name__)

"""Water system components for EcoSystemiser.,

This module provides water management components including storage
demand, grid connection, and renewable sources.
"""


# Import all water components and their parameter models to register them

__all__ = [
    "WaterStorageWaterStorageParams",
    "WaterDemandWaterDemandParams",
    "WaterGridWaterGridParams",
    "RainwaterSourceRainwaterSourceParams",
]

# Component metadata for documentation
WATER_COMPONENTS = {
    "WaterStorage": {"description": "Water storage tanks and reservoirs", "medium": "water", "type": "storage"},
    "WaterDemand": {"description": "Water consumption patterns and demand", "medium": "water", "type": "consumption"},
    "WaterGrid": {
        "description": "Municipal water supply and wastewater discharge",
        "medium": "water",
        "type": "transmission",
    },
    "RainwaterSource": {"description": "Rainwater harvesting and collection", "medium": "water", "type": "generation"},
}
