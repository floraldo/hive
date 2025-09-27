"""Discovery Engine - Advanced optimization and uncertainty analysis for EcoSystemiser.

This module provides sophisticated algorithms for design space exploration
and uncertainty analysis, transforming EcoSystemiser into a complete
discovery engine for energy system optimization.
"""

from .algorithms.genetic_algorithm import GeneticAlgorithm, NSGAIIOptimizer
from .algorithms.monte_carlo import MonteCarloEngine
from .encoders.parameter_encoder import ParameterEncoder

__all__ = [
    'GeneticAlgorithm',
    'NSGAIIOptimizer',
    'MonteCarloEngine',
    'ParameterEncoder'
]