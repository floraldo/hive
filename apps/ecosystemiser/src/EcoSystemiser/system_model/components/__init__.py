"""System components module."""

# Import all component classes for easy access
from .shared.component import Component, ComponentParams
from .shared.economic_params import EconomicParamsModel
from .shared.environmental_params import EnvironmentalParamsModel

# Energy components
from .energy.battery import Battery, BatteryParams
from .energy.grid import Grid, GridParams
from .energy.solar_pv import SolarPV, SolarPVParams

# Water components - these will auto-register via decorators
from .water.water_storage import WaterStorage, WaterStorageParams
from .water.water_demand import WaterDemand, WaterDemandParams
from .water.water_grid import WaterGrid, WaterGridParams
from .water.rainwater_source import RainwaterSource, RainwaterSourceParams

__all__ = [
    'Component', 'ComponentParams',
    'EconomicParamsModel', 'EnvironmentalParamsModel',
    'Battery', 'BatteryParams',
    'Grid', 'GridParams',
    'SolarPV', 'SolarPVParams',
    'WaterStorage', 'WaterStorageParams',
    'WaterDemand', 'WaterDemandParams',
    'WaterGrid', 'WaterGridParams',
    'RainwaterSource', 'RainwaterSourceParams',
]