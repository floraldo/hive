"""System components module."""

# Import all component classes for easy access
from EcoSystemiser.system_model.shared.component import Component, ComponentParams
from EcoSystemiser.system_model.shared.economic_params import EconomicParamsModel
from EcoSystemiser.system_model.shared.environmental_params import EnvironmentalParamsModel

# Energy components
from EcoSystemiser.system_model.energy.battery import Battery, BatteryParams
from EcoSystemiser.system_model.energy.grid import Grid, GridParams
from EcoSystemiser.system_model.energy.solar_pv import SolarPV, SolarPVParams

# Water components - these will auto-register via decorators
from EcoSystemiser.system_model.water.water_storage import WaterStorage, WaterStorageParams
from EcoSystemiser.system_model.water.water_demand import WaterDemand, WaterDemandParams
from EcoSystemiser.system_model.water.water_grid import WaterGrid, WaterGridParams
from EcoSystemiser.system_model.water.rainwater_source import RainwaterSource, RainwaterSourceParams

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