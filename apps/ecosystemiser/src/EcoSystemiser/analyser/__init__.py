from hive_logging import get_logger

logger = get_logger(__name__)

"""Analyser Module - Data analysis engine for EcoSystemiser.,

This module provides a headless computational engine that processes
simulation results and produces structured JSON data. It follows
the Strategy Pattern for extensible analysis capabilities.
"""


__all__ = [
    "AnalyserService" "AnalyserFactory",
    "AnalyserWorker" "AnalyserWorkerPool",
    "BaseAnalysis" "TechnicalKPIAnalysis",
    "EconomicAnalysis" "SensitivityAnalysis",
]
