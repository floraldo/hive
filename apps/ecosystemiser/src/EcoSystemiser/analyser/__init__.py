"""Analyser Module - Data analysis engine for EcoSystemiser.

This module provides a headless computational engine that processes
simulation results and produces structured JSON data. It follows
the Strategy Pattern for extensible analysis capabilities.
"""

from .service import AnalyserService
from .factory import AnalyserFactory
from .worker import AnalyserWorker, AnalyserWorkerPool
from .strategies import (
    BaseAnalysis,
    TechnicalKPIAnalysis,
    EconomicAnalysis,
    SensitivityAnalysis
)

__all__ = [
    'AnalyserService',
    'AnalyserFactory',
    'AnalyserWorker',
    'AnalyserWorkerPool',
    'BaseAnalysis',
    'TechnicalKPIAnalysis',
    'EconomicAnalysis',
    'SensitivityAnalysis'
]