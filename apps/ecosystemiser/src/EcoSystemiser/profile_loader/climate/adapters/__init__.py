"""Climate data source adapters"""

from EcoSystemiser.profile_loader.climate.adapters.base import BaseAdapter
from EcoSystemiser.profile_loader.climate.adapters.nasa_power import NASAPowerAdapter
from EcoSystemiser.profile_loader.climate.adapters.meteostat import MeteostatAdapter
from EcoSystemiser.profile_loader.climate.adapters.pvgis import PVGISAdapter
from EcoSystemiser.profile_loader.climate.adapters.era5 import ERA5Adapter
from EcoSystemiser.profile_loader.climate.adapters.file_epw import FileEPWAdapter

__all__ = [
    "BaseAdapter", 
    "NASAPowerAdapter",
    "MeteostatAdapter",
    "PVGISAdapter",
    "ERA5Adapter",
    "FileEPWAdapter"
]