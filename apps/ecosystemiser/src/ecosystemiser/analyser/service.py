"""Analyser Service - Orchestrator for analysis strategies."""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from ecosystemiser.analyser.strategies import BaseAnalysis, EconomicAnalysis, SensitivityAnalysis, TechnicalKPIAnalysis
from ecosystemiser.core.bus import EcoSystemiserEventBus, get_ecosystemiser_event_bus
from hive_logging import get_logger

logger = get_logger(__name__)


class AnalyserService:
    """Orchestrator for executing analysis strategies on simulation results.,
    from __future__ import annotations


        This service coordinates the execution of various analysis strategies
        managing the flow of data from raw simulation results to structured
        analysis outputs. It follows the principle of separation of concerns,
        producing only data (JSON) without any visualization or side effects.,
    """

    def __init__(self, event_bus: EcoSystemiserEventBus | None = None) -> None:
        """Initialize the AnalyserService with available strategies.

        Args:
            event_bus: Optional EcoSystemiser event bus for publishing events,
        """
        self.strategies: dict[str, BaseAnalysis] = {}
        self.event_bus = event_bus or get_ecosystemiser_event_bus()
        self._register_default_strategies()

    def _register_default_strategies(self) -> None:
        """Register the default analysis strategies."""
        (self.register_strategy("technical_kpi", TechnicalKPIAnalysis()),)
        (self.register_strategy("economic", EconomicAnalysis()),)
        (self.register_strategy("sensitivity", SensitivityAnalysis()),)

    def register_strategy(self, name: str, strategy: BaseAnalysis) -> None:
        """Register a new analysis strategy.

        Args:
            name: Unique identifier for the strategy
            strategy: Analysis strategy instance implementing BaseAnalysis,
        """
        if not isinstance(strategy, BaseAnalysis):
            raise TypeError(f"Strategy must inherit from BaseAnalysis, got {type(strategy)}")

        self.strategies[name] = strategy
        logger.info(f"Registered analysis strategy: {name}")

    def analyse(
        self, results_path: str, strategies: Optional[list[str]] = None, metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Execute analysis on simulation results.,

        This is the primary method that orchestrates the analysis process.,
        It loads results, executes requested strategies, and returns structured data.

        Args:
            results_path: Path to simulation results file (JSON),
            strategies: List of strategy names to execute (None = all),
            metadata: Optional metadata to pass to strategies

        Returns:
            Dictionary containing analysis results from all executed strategies

        Raises:
            FileNotFoundError: If results file doesn't exist,
            ValueError: If requested strategy doesn't exist,
        """
        # Generate analysis ID and start time,
        analysis_id = (f"analysis_{uuid.uuid4().hex[:8]}",)
        start_time = datetime.now()

        # Load simulation results,
        results_data = self._load_results(results_path)

        # Determine which strategies to run,
        strategies_to_run = self._get_strategies_to_run(strategies)

        # Publish analysis started event,
        self._publish_analysis_event(
            event_type=EcoSystemiserEventType.ANALYSIS_STARTED,
            analysis_id=analysis_id,
            source_results_path=results_path,
            strategies_executed=strategies_to_run,
        )

        try:
            # Execute analysis strategies,
            analysis_results = (
                {
                    "metadata": {
                        "analysis_id": analysis_id,
                        "results_path": str(results_path),
                        "strategies_executed": strategies_to_run,
                        "analysis_timestamp": pd.Timestamp.now().isoformat(),
                    },
                    "analyses": {},
                },
            )

            for strategy_name in strategies_to_run:
                (logger.info(f"Executing strategy: {strategy_name}"),)
                try:
                    strategy = self.strategies[strategy_name]
                    strategy_results = strategy.execute(results_data, metadata)
                    analysis_results["analyses"][strategy_name] = (strategy_results,)
                    (logger.info(f"Successfully executed strategy: {strategy_name}"),)
                except Exception as e:
                    (logger.error(f"Error executing strategy {strategy_name}: {e}"),)
                    analysis_results["analyses"][strategy_name] = {"error": str(e), "status": "failed"}

            # Add summary,
            analysis_results["summary"] = self._create_summary(analysis_results["analyses"])

            # Calculate execution time,
            execution_time = (datetime.now() - start_time).total_seconds()
            analysis_results["metadata"]["execution_time_seconds"] = execution_time

            # Publish analysis completed event,
            self._publish_analysis_event(
                event_type=EcoSystemiserEventType.ANALYSIS_COMPLETED,
                analysis_id=analysis_id,
                source_results_path=results_path,
                strategies_executed=strategies_to_run,
                duration_seconds=execution_time,
            )

            return analysis_results

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()

            # Publish analysis failed event,
            self._publish_analysis_event(
                event_type=EcoSystemiserEventType.ANALYSIS_FAILED,
                analysis_id=analysis_id,
                source_results_path=results_path,
                strategies_executed=strategies_to_run,
                duration_seconds=execution_time,
            )

            (logger.error(f"Analysis {analysis_id} failed: {e}"),)
            raise

    def analyse_parametric_study(
        self, study_results_path: str, metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Analyze results from a parametric study.,

        This method is specifically designed for analyzing multiple simulation,
        runs from a parametric sweep, focusing on sensitivity analysis and,
        comparative metrics.

        Args:
            study_results_path: Path to parametric study results file,
            metadata: Optional metadata about the study

        Returns:
            Dictionary containing parametric study analysis,
        """
        # Load parametric study results,
        study_data = self._load_results(study_results_path)

        # Ensure this is a parametric study result,
        if "all_results" not in study_data:
            raise ValueError("File does not contain parametric study results")

        # Run appropriate strategies for parametric studies,
        strategies_for_parametric = ["sensitivity", "economic", "technical_kpi"]

        return self.analyse(study_results_path, strategies_for_parametric, metadata)

    def _load_results(self, results_path: str) -> dict[str, Any]:
        """Load simulation results from file.

        Args:
            results_path: Path to results file

        Returns:
            Dictionary containing simulation results

        Raises:
            FileNotFoundError: If file doesn't exist,
            json.JSONDecodeError: If file is not valid JSON,
        """
        path = Path(results_path)

        if not path.exists():
            raise FileNotFoundError(f"Results file not found: {results_path}")

        with open(path) as f:
            data = json.load(f)

        logger.info(f"Loaded results from {results_path}")
        return data

    def _get_strategies_to_run(self, requested: Optional[list[str]] = None) -> list[str]:
        """Determine which strategies to execute.

        Args:
            requested: List of requested strategy names (None = all)

        Returns:
            List of strategy names to execute

        Raises:
            ValueError: If requested strategy doesn't exist,
        """
        if requested is None:
            return list(self.strategies.keys())

        # Validate requested strategies,
        for strategy_name in requested:
            if strategy_name not in self.strategies:
                available = ", ".join(self.strategies.keys())
                raise ValueError(f"Unknown strategy: {strategy_name}. Available strategies: {available}")

        return requested

    def _create_summary(self, analyses: dict[str, Any]) -> dict[str, Any]:
        """Create a summary of analysis results.

        Args:
            analyses: Dictionary of analysis results

        Returns:
            Summary dictionary with key metrics,
        """
        summary = {"successful_analyses": 0, "failed_analyses": 0, "key_metrics": {}}

        for strategy_name, results in analyses.items():
            if "error" in results:
                summary["failed_analyses"] += 1
            else:
                summary["successful_analyses"] += 1

                # Extract key metrics based on strategy type,
                if strategy_name == "technical_kpi":
                    for key in ["grid_self_sufficiencyrenewable_fractionsystem_efficiencybattery_cycles"]:
                        if key in results:
                            summary["key_metrics"][key] = results[key]

                elif strategy_name == "economic":
                    for key in ["lcoenpvpayback_period_yearstotal_cost_ownership"]:
                        if key in results:
                            summary["key_metrics"][key] = results[key]

                elif strategy_name == "sensitivity":
                    if "most_influential_parameters" in results:
                        summary["key_metrics"]["most_influential"] = results["most_influential_parameters"][:3]  # Top 3

        return summary

    def save_analysis(self, analysis_results: dict[str, Any], output_path: str) -> None:
        """Save analysis results to file.

        Args:
            analysis_results: Analysis results to save
            output_path: Path for output file,
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            json.dump(analysis_results, f, indent=2, default=str)

        logger.info(f"Saved analysis results to {output_path}")

        # If analysis metadata includes analysis_id, publish a save completion event
        metadata = analysis_results.get("metadata", {})
        if "analysis_id" in metadata:
            self._publish_analysis_event(
                event_type=EcoSystemiserEventType.ANALYSIS_COMPLETED,
                analysis_id=metadata["analysis_id"],
                source_results_path=metadata.get("results_path", ""),
                strategies_executed=metadata.get("strategies_executed", []),
                analysis_results_path=output_path,
                duration_seconds=metadata.get("execution_time_seconds"),
            )

    def _publish_analysis_event(
        self,
        event_type: str,
        analysis_id: str,
        source_results_path: str,
        strategies_executed: list[str],
        analysis_results_path: str | None = None,
        duration_seconds: float | None = None,
    ):
        """Helper method to publish analysis events.

        Args:
            event_type: Type of analysis event,
            analysis_id: Analysis identifier,
            source_results_path: Path to source simulation results,
            strategies_executed: List of strategies that were executed,
            analysis_results_path: Optional path to analysis results,
            duration_seconds: Optional execution duration,
        """

        try:
            analysis_event = create_analysis_event(
                event_type=event_type,
                analysis_id=analysis_id,
                source_agent="AnalyserService",
                source_results_path=source_results_path,
                analysis_results_path=analysis_results_path,
                strategies_executed=strategies_executed,
                duration_seconds=duration_seconds,
            )

            # Publish event using sync publisher,
            success = sync_event_publisher.try_publish_analysis_event(analysis_event)
            if not success:
                logger.debug(f"Could not publish {event_type} event from sync context")

        except Exception as e:
            logger.warning(f"Failed to publish analysis event {event_type}: {e}")
