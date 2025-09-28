"""Factory for creating analysis strategies dynamically."""

from typing import Dict, Any, Type, Optional
from ecosystemiser.analyser.strategies import BaseAnalysis
from ecosystemiser.analyser.strategies.technical_kpi import TechnicalKPIAnalysis
from ecosystemiser.analyser.strategies.economic import EconomicAnalysis
from ecosystemiser.analyser.strategies.sensitivity import SensitivityAnalysis
from ecosystemiser.hive_logging_adapter import get_logger

logger = get_logger(__name__)


class AnalyserFactory:
    """Factory for creating analysis strategy instances.

    This factory enables dynamic creation of analysis strategies,
    supporting both built-in strategies and custom implementations.
    """

    # Registry of available strategy classes
    _strategies: Dict[str, Type[BaseAnalysis]] = {
        'technical_kpi': TechnicalKPIAnalysis,
        'economic': EconomicAnalysis,
        'sensitivity': SensitivityAnalysis
    }

    @classmethod
    def register_strategy(cls, name: str, strategy_class: Type[BaseAnalysis]):
        """Register a custom analysis strategy.

        Args:
            name: Unique identifier for the strategy
            strategy_class: Class implementing BaseAnalysis

        Raises:
            TypeError: If strategy_class doesn't inherit from BaseAnalysis
        """
        if not issubclass(strategy_class, BaseAnalysis):
            raise TypeError(
                f"Strategy class must inherit from BaseAnalysis, "
                f"got {strategy_class}"
            )

        cls._strategies[name] = strategy_class
        logger.info(f"Registered strategy class: {name}")

    @classmethod
    def create_strategy(cls, name: str, config: Optional[Dict[str, Any]] = None) -> BaseAnalysis:
        """Create an analysis strategy instance.

        Args:
            name: Name of the strategy to create
            config: Optional configuration for the strategy

        Returns:
            Instance of the requested strategy

        Raises:
            ValueError: If strategy name is not registered
        """
        if name not in cls._strategies:
            available = ', '.join(cls._strategies.keys())
            raise ValueError(
                f"Unknown strategy: {name}. "
                f"Available strategies: {available}"
            )

        strategy_class = cls._strategies[name]

        # Create instance with configuration if supported
        if config:
            # Check if the strategy accepts configuration
            try:
                instance = strategy_class(**config)
            except TypeError:
                # Strategy doesn't accept configuration
                instance = strategy_class()
                logger.debug(f"Strategy {name} doesn't accept configuration")
        else:
            instance = strategy_class()

        logger.info(f"Created strategy instance: {name}")
        return instance

    @classmethod
    def create_all_strategies(cls, config: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, BaseAnalysis]:
        """Create instances of all registered strategies.

        Args:
            config: Optional configuration dictionary with strategy-specific configs

        Returns:
            Dictionary mapping strategy names to instances
        """
        strategies = {}
        config = config or {}

        for name in cls._strategies:
            strategy_config = config.get(name)
            strategies[name] = cls.create_strategy(name, strategy_config)

        return strategies

    @classmethod
    def get_available_strategies(cls) -> Dict[str, str]:
        """Get information about available strategies.

        Returns:
            Dictionary mapping strategy names to descriptions
        """
        info = {}
        for name, strategy_class in cls._strategies.items():
            # Extract docstring as description
            doc = strategy_class.__doc__ or "No description available"
            # Get first line of docstring
            description = doc.strip().split('\n')[0]
            info[name] = description

        return info

    @classmethod
    def create_strategy_for_system_type(cls, system_type: str) -> Dict[str, BaseAnalysis]:
        """Create appropriate strategies based on system type.

        Args:
            system_type: Type of system ('energy', 'water', 'mixed')

        Returns:
            Dictionary of relevant strategy instances
        """
        strategies = {}

        if system_type == 'energy':
            strategies['technical_kpi'] = cls.create_strategy('technical_kpi')
            strategies['economic'] = cls.create_strategy('economic')
            strategies['sensitivity'] = cls.create_strategy('sensitivity')

        elif system_type == 'water':
            # For water systems, still use technical KPIs (it handles water metrics)
            strategies['technical_kpi'] = cls.create_strategy('technical_kpi')
            strategies['economic'] = cls.create_strategy('economic')

        elif system_type == 'mixed':
            # For mixed systems, use all strategies
            strategies = cls.create_all_strategies()

        else:
            # Default to all strategies
            strategies = cls.create_all_strategies()
            logger.warning(f"Unknown system type: {system_type}, using all strategies")

        return strategies