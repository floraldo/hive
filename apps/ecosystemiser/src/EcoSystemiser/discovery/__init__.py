"""Discovery Engine - Advanced optimization and uncertainty analysis for EcoSystemiser.

This module provides sophisticated algorithms for design space exploration
and uncertainty analysis, transforming EcoSystemiser into a complete
discovery engine for energy system optimization.
"""

from EcoSystemiser.algorithms.genetic_algorithm import GeneticAlgorithm, NSGAIIOptimizer
from EcoSystemiser.algorithms.monte_carlo import MonteCarloEngine
from EcoSystemiser.encoders.parameter_encoder import ParameterEncoder

__all__ = [
    'GeneticAlgorithm',
    'NSGAIIOptimizer',
    'MonteCarloEngine',
    'ParameterEncoder'
]