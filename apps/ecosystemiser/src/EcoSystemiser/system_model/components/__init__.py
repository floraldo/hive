"""System components module."""

# Import all component classes for easy access
from .shared.component import Component, ComponentParams

# Energy components
from .energy.battery import Battery, BatteryParams
from .energy.grid import Grid, GridParams
from .energy.solar_pv import SolarPV, SolarPVParams
from .energy.heat_pump import HeatPump, HeatPumpParams
from .energy.power_demand import PowerDemand, PowerDemandParams
from .energy.heat_demand import HeatDemand, HeatDemandParams
from .energy.electric_boiler import ElectricBoiler, ElectricBoilerParams
from .energy.heat_buffer import HeatBuffer, HeatBufferParams

# Water components
from .water.water_storage import WaterStorage, WaterStorageParams
from .water.water_demand import WaterDemand, WaterDemandParams
from .water.water_grid import WaterGrid, WaterGridParams
from .water.rainwater_source import RainwaterSource, RainwaterSourceParams

__all__ = [
    'Component', 'ComponentParams',
    'Battery', 'BatteryParams',
    'Grid', 'GridParams',
    'SolarPV', 'SolarPVParams',
    'HeatPump', 'HeatPumpParams',
    'PowerDemand', 'PowerDemandParams',
    'HeatDemand', 'HeatDemandParams',
    'ElectricBoiler', 'ElectricBoilerParams',
    'HeatBuffer', 'HeatBufferParams',
    'WaterStorage', 'WaterStorageParams',
    'WaterDemand', 'WaterDemandParams',
    'WaterGrid', 'WaterGridParams',
    'RainwaterSource', 'RainwaterSourceParams',
]