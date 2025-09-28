"""Analyser Module - Data analysis engine for EcoSystemiser.

This module provides a headless computational engine that processes
simulation results and produces structured JSON data. It follows
the Strategy Pattern for extensible analysis capabilities.
"""

from EcoSystemiser.analyser.service import AnalyserService
from EcoSystemiser.analyser.factory import AnalyserFactory
from EcoSystemiser.analyser.worker import AnalyserWorker, AnalyserWorkerPool
from EcoSystemiser.analyser.strategies import (
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