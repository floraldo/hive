"""Water system components for EcoSystemiser.

This module provides water management components including storage,
demand, grid connection, and renewable sources.
"""

# Import all water components and their parameter models to register them
from EcoSystemiser.system_model.components.water_storage import WaterStorage, WaterStorageParams
from EcoSystemiser.system_model.components.water_demand import WaterDemand, WaterDemandParams
from EcoSystemiser.system_model.components.water_grid import WaterGrid, WaterGridParams
from EcoSystemiser.system_model.components.rainwater_source import RainwaterSource, RainwaterSourceParams

__all__ = [
    'WaterStorage', 'WaterStorageParams',
    'WaterDemand', 'WaterDemandParams',
    'WaterGrid', 'WaterGridParams',
    'RainwaterSource', 'RainwaterSourceParams'
]

# Component metadata for documentation
WATER_COMPONENTS = {
    'WaterStorage': {
        'description': 'Water storage tanks and reservoirs',
        'medium': 'water',
        'type': 'storage'
    },
    'WaterDemand': {
        'description': 'Water consumption patterns and demand',
        'medium': 'water',
        'type': 'consumption'
    },
    'WaterGrid': {
        'description': 'Municipal water supply and wastewater discharge',
        'medium': 'water',
        'type': 'transmission'
    },
    'RainwaterSource': {
        'description': 'Rainwater harvesting and collection',
        'medium': 'water',
        'type': 'generation'
    }
}