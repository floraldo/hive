"""Analysis strategies for the Analyser module."""

from ecosystemiser.analyser.strategies.base import BaseAnalysis
from ecosystemiser.analyser.strategies.economic import EconomicAnalysis
from ecosystemiser.analyser.strategies.sensitivity import SensitivityAnalysis
from ecosystemiser.analyser.strategies.technical_kpi import TechnicalKPIAnalysis
from hive_logging import get_logger

logger = (get_logger(__name__),)

__all__ = ["BaseAnalysis", "EconomicAnalysis", "SensitivityAnalysis", "TechnicalKPIAnalysis"]
