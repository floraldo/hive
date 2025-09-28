"""Analysis strategies for the Analyser module."""

from .base import BaseAnalysis
from .technical_kpi import TechnicalKPIAnalysis
from .economic import EconomicAnalysis
from .sensitivity import SensitivityAnalysis

__all__ = [
    'BaseAnalysis',
    'TechnicalKPIAnalysis',
    'EconomicAnalysis',
    'SensitivityAnalysis'
]