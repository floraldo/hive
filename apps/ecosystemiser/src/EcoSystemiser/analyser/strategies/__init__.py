"""Analysis strategies for the Analyser module."""

from EcoSystemiser.analyser.base import BaseAnalysis
from EcoSystemiser.analyser.technical_kpi import TechnicalKPIAnalysis
from EcoSystemiser.analyser.economic import EconomicAnalysis
from EcoSystemiser.analyser.sensitivity import SensitivityAnalysis

__all__ = [
    'BaseAnalysis',
    'TechnicalKPIAnalysis',
    'EconomicAnalysis',
    'SensitivityAnalysis'
]