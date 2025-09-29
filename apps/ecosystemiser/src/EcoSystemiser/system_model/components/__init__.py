from hive_logging import get_logger

logger = get_logger(__name__)

"""System components module."""

# Import all component classes for easy access
# Energy components
from .energy.battery import Battery, BatteryParams
from .energy.electric_boiler import ElectricBoiler, ElectricBoilerParams
from .energy.grid import Grid, GridParams
from .energy.heat_buffer import HeatBuffer, HeatBufferParams
from .energy.heat_demand import HeatDemand, HeatDemandParams
from .energy.heat_pump import HeatPump, HeatPumpParams
from .energy.power_demand import PowerDemand, PowerDemandParams
from .energy.solar_pv import SolarPV, SolarPVParams
from .shared.component import Component, ComponentParams
from .water.rainwater_source import RainwaterSource, RainwaterSourceParams
from .water.water_demand import WaterDemand, WaterDemandParams
from .water.water_grid import WaterGrid, WaterGridParams

# Water components
from .water.water_storage import WaterStorage, WaterStorageParams

__all__ = [
    "Component",
    "ComponentParams",
    "Battery",
    "BatteryParams",
    "Grid",
    "GridParams",
    "SolarPV",
    "SolarPVParams",
    "HeatPump",
    "HeatPumpParams",
    "PowerDemand",
    "PowerDemandParams",
    "HeatDemand",
    "HeatDemandParams",
    "ElectricBoiler",
    "ElectricBoilerParams",
    "HeatBuffer",
    "HeatBufferParams",
    "WaterStorage",
    "WaterStorageParams",
    "WaterDemand",
    "WaterDemandParams",
    "WaterGrid",
    "WaterGridParams",
    "RainwaterSource",
    "RainwaterSourceParams",
]
