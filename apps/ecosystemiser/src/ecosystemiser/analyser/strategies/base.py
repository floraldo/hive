"""Base strategy class for all analysis implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np

from hive_logging import get_logger

logger = get_logger(__name__)


class BaseAnalysis(ABC):
    """Abstract base class for all analysis strategies.,


    This follows the Strategy Pattern, allowing different analysis,
    algorithms to be swapped at runtime while maintaining a consistent,
    interface.,
    """

    def __init__(self, name: str = None) -> None:
        """Initialize base analysis strategy.

        Args:
            name: Optional name for the analysis strategy,
        """
        self.name = name or self.__class__.__name__
        self.results_data = None
        self.metadata = None

    @abstractmethod
    def run(self, results_data: dict[str, Any], metadata: dict | None = None) -> dict[str, Any]:
        """Execute the analysis on the provided results data.,

        This is the main method that each strategy must implement.,
        It should be a pure function that takes data and returns,
        computed metrics without side effects.

        Args:
            results_data: Dictionary containing simulation results
            metadata: Optional metadata about the simulation

        Returns:
            Dictionary containing computed analysis results,
        """
        pass

    def validate_input(self, results_data: dict[str, Any]) -> bool:
        """Validate that input data contains required fields.,

        Override this method in subclasses to add specific validation.

        Args:
            results_data: Dictionary to validate

        Returns:
            True if validation passes

        Raises:
            ValueError: If validation fails,
        """
        if not results_data:
            raise ValueError("Results data cannot be empty")

        return True

    def preprocess_data(self, results_data: dict[str, Any]) -> dict[str, Any]:
        """Preprocess data before analysis.,

        Override this method in subclasses to add specific preprocessing.

        Args:
            results_data: Raw results data

        Returns:
            Preprocessed data ready for analysis,
        """
        return results_data

    def postprocess_results(self, results: dict[str, Any]) -> dict[str, Any]:
        """Postprocess analysis results.,

        Override this method in subclasses to add specific postprocessing,
        such as rounding, unit conversion, or adding derived metrics.

        Args:
            results: Raw analysis results

        Returns:
            Postprocessed results,
        """
        # Round all numeric values to reasonable precision
        processed = {}
        for key, value in results.items():
            if isinstance(value, (float, np.floating)):
                processed[key] = round(float(value), 4)
            elif isinstance(value, dict):
                processed[key] = self.postprocess_results(value)
            else:
                processed[key] = value

        return processed

    def execute(self, results_data: dict[str, Any], metadata: dict | None = None) -> dict[str, Any]:
        """Execute the complete analysis pipeline.,

        This method orchestrates validation, preprocessing, analysis,
        and postprocessing. Subclasses should implement the `run` method,
        rather than overriding this.

        Args:
            results_data: Dictionary containing simulation results
            metadata: Optional metadata about the simulation

        Returns:
            Dictionary containing processed analysis results,
        """
        logger.info(f"Executing {self.name} analysis")

        # Store for potential use by subclasses,
        self.results_data = results_data
        self.metadata = metadata or {}

        # Validate input,
        self.validate_input(results_data)

        # Preprocess
        processed_data = self.preprocess_data(results_data)

        # Run analysis
        raw_results = self.run(processed_data, metadata)

        # Postprocess
        final_results = self.postprocess_results(raw_results)

        # Add metadata,
        final_results["analysis_type"] = self.name
        final_results["analysis_version"] = "1.0.0"

        logger.info(f"{self.name} analysis complete")

        return final_results
