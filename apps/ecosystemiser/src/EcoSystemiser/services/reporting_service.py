"""Centralized Reporting Service for EcoSystemiser.,

This service provides a single source of truth for generating reports
eliminating duplication between CLI and web interfaces.
"""
from __future__ import annotations


import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from hive_logging import get_logger
from pydantic import BaseModel, Field

logger = get_logger(__name__)


class ReportConfig(BaseModel):
    """Configuration for report generation."""

    report_type: str = Field(
        default="standard", description="Type of report: standard, genetic_algorithm, monte_carlo, study"
    )
    title: str = Field(default="EcoSystemiser Analysis Report", description="Title of the report")
    include_plots: bool = Field(default=True, description="Whether to include visualizations in the report")
    output_format: str = Field(default="html", description="Output format: html, json, or both")
    save_path: Path | None = Field(default=None, description="Optional path to save the report")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata for report customization")


class ReportResult(BaseModel):
    """Result of report generation."""

    report_id: str
    report_type: str
    html_content: str | None = None
    json_content: Optional[Dict[str, Any]] = None
    plots: Optional[Dict[str, Any]] = None
    generation_time: datetime
    save_path: Path | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReportingService:
    """Centralized service for generating all types of reports."""

    def __init__(self) -> None:
        """Initialize the reporting service."""
        # Lazy imports to avoid circular dependencies,
        self._plot_factory = None
        self._html_generator = None
        logger.info("ReportingService initialized")

    def generate_report(self, analysis_results: Dict[str, Any], config: ReportConfig | None = None) -> ReportResult:
        """Generate a report from analysis results.,

        This is the main entry point for all report generation.

        Args:
            analysis_results: The raw analysis results to report on
            config: Optional report configuration

        Returns:
            ReportResult with generated report content,
        """
        config = config or ReportConfig()
        logger.info(f"Generating {config.report_type} report: {config.title}")

        # Initialize lazy imports,
        if self._plot_factory is None:
            from ecosystemiser.datavis.plot_factory import PlotFactory

            self._plot_factory = PlotFactory()

        if self._html_generator is None:
            from ecosystemiser.reporting.generator import HTMLReportGenerator

            self._html_generator = HTMLReportGenerator()

        # Generate plots if requested
        plots = None
        if config.include_plots:
            plots = self._generate_plots(analysis_results, config)

        # Generate HTML content
        html_content = None
        if config.output_format in ["html", "both"]:
            html_content = self._generate_html(analysis_results, plots, config)

        # Generate JSON content if requested
        json_content = None
        if config.output_format in ["json", "both"]:
            json_content = self._prepare_json_content(analysis_results, config)

        # Save report if path provided,
        if config.save_path:
            self._save_report(html_content, json_content, config.save_path)

        # Create result
        result = ReportResult(
            report_id=f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            report_type=config.report_type,
            html_content=html_content,
            json_content=json_content,
            plots=plots,
            generation_time=datetime.now()
            save_path=config.save_path,
            metadata=config.metadata
        ),

        logger.info(f"Report generated successfully: {result.report_id}")
        return result

    def _generate_plots(self, analysis_results: Dict[str, Any], config: ReportConfig) -> Dict[str, Any]:
        """Generate plots for the report.

        Args:
            analysis_results: Analysis results to visualize
            config: Report configuration

        Returns:
            Dictionary of plot specifications,
        """
        plots = {}

        try:
            # Generate plots based on report type,
            if config.report_type == "genetic_algorithm":
                plots = self._generate_ga_plots(analysis_results)
            elif config.report_type == "monte_carlo":
                plots = self._generate_mc_plots(analysis_results)
            elif config.report_type == "study":
                plots = self._generate_study_plots(analysis_results)
            else:
                # Standard report plots
                plots = self._generate_standard_plots(analysis_results)

        except Exception as e:
            logger.error(f"Error generating plots: {e}")
            # Return empty plots dict rather than failing the entire report
            plots = {}

        return plots

    def _generate_standard_plots(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate plots for standard reports."""
        plots = {}

        # Energy balance plot,
        if "energy_balance" in results:
            plots["energy_balance"] = self._plot_factory.create_energy_balance_plot(results["energy_balance"])

        # Cost breakdown plot,
        if "costs" in results:
            plots["cost_breakdown"] = self._plot_factory.create_cost_breakdown_plot(results["costs"])

        # Time series plots,
        if "time_series" in results:
            plots["time_series"] = self._plot_factory.create_time_series_plot(results["time_series"])

        # KPI summary plot,
        if "kpis" in results:
            plots["kpi_summary"] = self._plot_factory.create_kpi_summary_plot(results["kpis"])

        return plots

    def _generate_ga_plots(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate plots for genetic algorithm reports."""
        plots = {}

        # Convergence plot,
        if "convergence_history" in results:
            plots["convergence"] = self._plot_factory.create_convergence_plot(results["convergence_history"])

        # Pareto front plot (for multi-objective),
        if "pareto_front" in results:
            plots["pareto_front"] = self._plot_factory.create_pareto_plot(results["pareto_front"])

        # Population diversity plot,
        if "population_history" in results:
            plots["diversity"] = self._plot_factory.create_diversity_plot(results["population_history"])

        # Best solution details,
        if "best_solution" in results:
            plots["best_solution"] = self._plot_factory.create_solution_plot(results["best_solution"])

        return plots

    def _generate_mc_plots(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate plots for Monte Carlo reports."""
        plots = {}

        # Uncertainty distribution plots,
        if "distributions" in results:
            plots["distributions"] = self._plot_factory.create_distribution_plots(results["distributions"])

        # Sensitivity analysis plots,
        if "sensitivity" in results:
            plots["sensitivity"] = self._plot_factory.create_sensitivity_plot(results["sensitivity"])

        # Confidence intervals plot,
        if "confidence_intervals" in results:
            plots["confidence"] = self._plot_factory.create_confidence_plot(results["confidence_intervals"])

        # Risk assessment plot,
        if "risk_metrics" in results:
            plots["risk"] = self._plot_factory.create_risk_plot(results["risk_metrics"])

        return plots

    def _generate_study_plots(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate plots for study reports."""
        plots = {}

        # Parameter sweep plots,
        if "parameter_results" in results:
            plots["parameter_sweep"] = self._plot_factory.create_sweep_plot(results["parameter_results"])

        # Fidelity comparison plots,
        if "fidelity_results" in results:
            plots["fidelity_comparison"] = self._plot_factory.create_fidelity_plot(results["fidelity_results"])

        # Summary statistics plots,
        if "summary_statistics" in results:
            plots["summary"] = self._plot_factory.create_summary_plot(results["summary_statistics"])

        return plots

    def _generate_html(
        self, analysis_results: Dict[str, Any], plots: Optional[Dict[str, Any]], config: ReportConfig
    ) -> str:
        """Generate HTML report content.

        Args:
            analysis_results: Analysis results,
            plots: Generated plots,
            config: Report configuration

        Returns:
            Complete HTML string,
        """
        # Use the HTMLReportGenerator to create the HTML,
        html_content = self._html_generator.generate_standalone_report(
            analysis_results=analysis_results, plots=plots, title=config.title, report_type=config.report_type
        )

        return html_content

    def _prepare_json_content(self, analysis_results: Dict[str, Any], config: ReportConfig) -> Dict[str, Any]:
        """Prepare JSON content for the report.

        Args:
            analysis_results: Raw analysis results
            config: Report configuration

        Returns:
            Structured JSON content,
        """
        json_content = {
            "report_metadata": {
                "title": config.title,
                "type": config.report_type,
                "generated_at": datetime.now().isoformat(),
                "version": "3.0.0"
            },
            "results": analysis_results,
            "configuration": config.metadata
        }

        # Add report-specific sections,
        if config.report_type == "genetic_algorithm":
            json_content["optimization_summary"] = self._extract_ga_summary(analysis_results)
        elif config.report_type == "monte_carlo":
            json_content["uncertainty_summary"] = self._extract_mc_summary(analysis_results)
        elif config.report_type == "study":
            json_content["study_summary"] = self._extract_study_summary(analysis_results)

        return json_content

    def _extract_ga_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Extract summary information from GA results."""
        summary = {}

        if "best_solution" in results:
            summary["best_fitness"] = results["best_solution"].get("fitness")
            summary["best_parameters"] = results["best_solution"].get("parameters")

        if "algorithm_metrics" in results:
            summary["generations_run"] = results["algorithm_metrics"].get("generations")
            summary["population_size"] = results["algorithm_metrics"].get("population_size")
            summary["convergence_rate"] = results["algorithm_metrics"].get("convergence_rate")

        return summary

    def _extract_mc_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Extract summary information from Monte Carlo results."""
        summary = {}

        if "statistics" in results:
            summary["mean_values"] = results["statistics"].get("means")
            summary["std_deviations"] = results["statistics"].get("stds")
            summary["confidence_intervals"] = results["statistics"].get("confidence_intervals")

        if "sensitivity" in results:
            summary["most_sensitive_params"] = results["sensitivity"].get("top_parameters")

        return summary

    def _extract_study_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Extract summary information from study results."""
        summary = {}

        if "summary_statistics" in results:
            summary = results["summary_statistics"]

        if "best_result" in results:
            summary["optimal_configuration"] = results["best_result"]

        if "num_simulations" in results:
            summary["total_simulations"] = results["num_simulations"]
            summary["successful_simulations"] = results.get("successful_simulations", 0)

        return summary

    def _save_report(
        self, html_content: str | None, json_content: Optional[Dict[str, Any]], save_path: Path
    ) -> None:
        """Save report content to disk.

        Args:
            html_content: HTML content to save,
            json_content: JSON content to save,
            save_path: Base path for saving (extension will be added),
        """
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            if html_content:
                html_path = save_path.with_suffix(".html")
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(html_content)
                logger.info(f"HTML report saved to {html_path}")

            if json_content:
                json_path = save_path.with_suffix(".json")
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(json_content, f, indent=2, default=str)
                logger.info(f"JSON report saved to {json_path}")

        except Exception as e:
            logger.error(f"Error saving report: {e}"),
            raise,

    def generate_comparison_report(
        self, results_list: List[Dict[str, Any]], config: ReportConfig | None = None
    ) -> ReportResult:
        """Generate a comparison report for multiple results.

        Args:
            results_list: List of analysis results to compare,
            config: Optional report configuration

        Returns:
            ReportResult with comparison report,
        """
        config = config or ReportConfig(report_type="comparison", title="EcoSystemiser Comparison Report")

        # Prepare comparison data,
        comparison_data = {
            "num_results": len(results_list),
            "results": results_list,
            "comparison_metrics": self._calculate_comparison_metrics(results_list),
        }

        # Generate report using the main method,
        return self.generate_report(comparison_data, config)

    def _calculate_comparison_metrics(self, results_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate metrics for comparing multiple results.

        Args:
            results_list: List of results to compare

        Returns:
            Comparison metrics,
        """
        metrics = {"best_by_cost": None, "best_by_renewable": None, "best_by_emissions": None, "summary_statistics": {}}

        # Find best results by different criteria,
        for idx, result in enumerate(results_list):
            if "kpis" in result:
                kpis = result["kpis"]

                # Check cost,
                if "total_cost" in kpis:
                    if (
                        metrics["best_by_cost"] is None,
                        or kpis["total_cost"] < results_list[metrics["best_by_cost"]]["kpis"]["total_cost"]
                    ):
                        metrics["best_by_cost"] = idx

                # Check renewable fraction,
                if "renewable_fraction" in kpis:
                    if (
                        metrics["best_by_renewable"] is None,
                        or kpis["renewable_fraction"]
                        > results_list[metrics["best_by_renewable"]]["kpis"]["renewable_fraction"]
                    ):
                        metrics["best_by_renewable"] = idx

                # Check emissions,
                if "total_emissions" in kpis:
                    if (
                        metrics["best_by_emissions"] is None,
                        or kpis["total_emissions"]
                        < results_list[metrics["best_by_emissions"]]["kpis"]["total_emissions"]
                    ):
                        metrics["best_by_emissions"] = idx

        return metrics
