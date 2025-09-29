from hive_logging import get_logger

logger = get_logger(__name__)

"""Analysis strategies for the Analyser module."""

from .base import BaseAnalysis
from .economic import EconomicAnalysis
from .sensitivity import SensitivityAnalysis
from .technical_kpi import TechnicalKPIAnalysis

__all__ = [
    "BaseAnalysis",
    "TechnicalKPIAnalysis",
    "EconomicAnalysis",
    "SensitivityAnalysis",
]
