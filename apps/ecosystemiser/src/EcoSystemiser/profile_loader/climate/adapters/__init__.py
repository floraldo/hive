"""Climate data source adapters"""

from EcoSystemiser.profile_loader.climate.base import BaseAdapter
from EcoSystemiser.profile_loader.climate.nasa_power import NASAPowerAdapter
from EcoSystemiser.profile_loader.climate.meteostat import MeteostatAdapter
from EcoSystemiser.profile_loader.climate.pvgis import PVGISAdapter
from EcoSystemiser.profile_loader.climate.era5 import ERA5Adapter
from EcoSystemiser.profile_loader.climate.file_epw import FileEPWAdapter

__all__ = [
    "BaseAdapter", 
    "NASAPowerAdapter",
    "MeteostatAdapter",
    "PVGISAdapter",
    "ERA5Adapter",
    "FileEPWAdapter"
]