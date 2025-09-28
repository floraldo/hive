"""Climate data source adapters"""

from ecosystemiser.profile_loader.climate.adapters.base import BaseAdapter
from ecosystemiser.profile_loader.climate.adapters.era5 import ERA5Adapter
from ecosystemiser.profile_loader.climate.adapters.file_epw import FileEPWAdapter
from ecosystemiser.profile_loader.climate.adapters.meteostat import MeteostatAdapter
from ecosystemiser.profile_loader.climate.adapters.nasa_power import NASAPowerAdapter
from ecosystemiser.profile_loader.climate.adapters.pvgis import PVGISAdapter

__all__ = [
    "BaseAdapter",
    "NASAPowerAdapter",
    "MeteostatAdapter",
    "PVGISAdapter",
    "ERA5Adapter",
    "FileEPWAdapter",
]
