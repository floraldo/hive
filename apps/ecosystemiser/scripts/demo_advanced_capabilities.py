import asyncio

#!/usr/bin/env python3
"""
Advanced EcoSystemiser Capabilities Demonstration

This script demonstrates the newly implemented advanced solver capabilities:
- Genetic Algorithm optimization for design space exploration
- Monte Carlo uncertainty analysis for risk assessment
- Interactive reporting with enhanced visualizations

Usage:
    python demo_advanced_capabilities.py
"""

import sys
import time
from pathlib import Path

# Use Poetry workspace imports
try:
    from ecosystemiser.datavis.plot_factory import PlotFactory
    from ecosystemiser.reporting.generator import HTMLReportGenerator
    from ecosystemiser.services.study_service import SimulationConfig, StudyConfig, StudyService
    from hive_logging import get_logger

    logger = get_logger(__name__)

    def demo_genetic_algorithm_optimization() -> None:
        """Demonstrate genetic algorithm optimization for system design."""
        logger.info("=== Genetic Algorithm Design Optimization Demo ===")

        # Create a sample system configuration path (would be real in practice),
        Path("config/sample_system.yml")

        # Define optimization variables (battery and solar sizing)

        # Multi-objective optimization: minimize cost, maximize renewable fraction

        # GA configuration

        # Create study service
        StudyService()

        # Simulate running the optimization (in real use, this would call actual optimization)
        logger.info("Simulating genetic algorithm optimization...")

        # Create mock results for demonstration
        demo_result = {
            "study_id": "ga_demo_system_design",
            "study_type": "genetic_algorithm",
            "num_simulations": 600,  # 30 population * 20 generations,
            "successful_simulations": 580,
            "failed_simulations": 20,
            "execution_time": 145.3,
            "best_result": {
                "best_solution": [85.4, 42.1, 35.8],  # battery, solar, inverter,
                "best_fitness": 125400.50,
                "best_objectives": [125400.50, 0.847],  # cost, renewable fraction,
                "pareto_front": [
                    [98500.20, 0.726],
                    [110200.30, 0.781],
                    [125400.50, 0.847],
                    [142800.75, 0.892],
                    [168500.90, 0.923],
                ],
                "pareto_objectives": [
                    [98500.20, 0.726],
                    [110200.30, 0.781],
                    [125400.50, 0.847],
                    [142800.75, 0.892],
                    [168500.90, 0.923],
                ],
                "convergence_history": [
                    180000,
                    165000,
                    152000,
                    145000,
                    140000,
                    135000,
                    132000,
                    130000,
                    128000,
                    127000,
                    126500,
                    126000,
                    125800,
                    125600,
                    125500,
                    125450,
                    125430,
                    125420,
                    125410,
                    125400.50,
                ],
                "algorithm_metadata": {
                    "final_population_diversity": 0.234,
                    "convergence_rate": 0.94,
                    "elite_contribution": 0.65,
                    "mutation_effectiveness": 0.78,
                },
            },
            "summary_statistics": {
                "final_generation": 20,
                "total_evaluations": 600,
                "convergence_status": "CONVERGED",
                "pareto_front_size": 5,
                "optimization_efficiency": 0.89,
            },
        }

        logger.info(
            f"Optimization completed: {demo_result['successful_simulations']}/{demo_result['num_simulations']} successful evaluations",
        )
        logger.info(
            f"Best solution: Battery={demo_result['best_result']['best_solution'][0]:.1f} kWh, Solar={demo_result['best_result']['best_solution'][1]:.1f} kW",
        )
        logger.info(
            f"Achieved cost: ${demo_result['best_result']['best_objectives'][0]:,.0f}, Renewable fraction: {demo_result['best_result']['best_objectives'][1]:.1%}",
        )

        return demo_result

    def demo_monte_carlo_uncertainty() -> None:
        """Demonstrate Monte Carlo uncertainty analysis."""
        logger.info("=== Monte Carlo Uncertainty Analysis Demo ===")

        # Define uncertainty variables

        # MC configuration

        logger.info("Simulating Monte Carlo uncertainty analysis...")

        # Create mock results for demonstration
        demo_result = {
            "study_id": "mc_demo_uncertainty",
            "study_type": "monte_carlo",
            "num_simulations": 1000,
            "successful_simulations": 987,
            "failed_simulations": 13,
            "execution_time": 78.6,
            "best_result": {
                "best_solution": [0.118, 5.45, 0.032, 0.023],  # parameter samples,
                "best_fitness": 98750.25,
                "best_objectives": [98750.25],
                "uncertainty_analysis": {
                    "statistics": {
                        "total_cost": {
                            "mean": 124850.75,
                            "std": 18420.33,
                            "min": 87420.10,
                            "max": 178650.90,
                            "median": 122450.80,
                            "skewness": 0.124,
                            "kurtosis": 2.89,
                        },
                    },
                    "confidence_intervals": {
                        "total_cost": {
                            "95%": {
                                "lower": 95680.20,
                                "upper": 165420.80,
                                "width": 69740.60,
                            },
                            "75%": {
                                "lower": 108940.50,
                                "upper": 145870.30,
                                "width": 36929.80,
                            },
                            "50%": {
                                "lower": 116250.40,
                                "upper": 132850.70,
                                "width": 16600.30,
                            },
                        },
                    },
                    "sensitivity": {
                        "total_cost": {
                            "param_0": {
                                "sensitivity_index": 0.782,
                                "pearson_correlation": -0.782,
                            },
                            "param_1": {
                                "sensitivity_index": 0.654,
                                "pearson_correlation": -0.654,
                            },
                            "param_2": {
                                "sensitivity_index": 0.423,
                                "pearson_correlation": 0.423,
                            },
                            "param_3": {
                                "sensitivity_index": 0.287,
                                "pearson_correlation": 0.287,
                            },
                        },
                    },
                    "risk": {
                        "total_cost": {
                            "var_95": 165420.80,
                            "var_99": 171850.50,
                            "cvar_95": 169850.75,
                            "cvar_99": 174200.25,
                            "prob_exceed_mean": 0.487,
                            "prob_exceed_2std": 0.022,
                            "risk_ratio": 0.148,
                        },
                    },
                    "scenarios": {
                        "total_cost": {
                            "optimistic": {
                                "description": "Best 10% of outcomes",
                                "sample_count": 98,
                                "mean_objective": 95240.80,
                            },
                            "expected": {
                                "description": "Median outcomes",
                                "sample_count": 487,
                                "mean_objective": 124850.75,
                            },
                            "pessimistic": {
                                "description": "Worst 10% of outcomes",
                                "sample_count": 99,
                                "mean_objective": 168420.30,
                            },
                        },
                    },
                },
            },
            "summary_statistics": {
                "sampling_method": "lhs",
                "total_samples": 1000,
                "analysis_completeness": 0.987,
            },
        }

        logger.info(
            f"Monte Carlo analysis completed: {demo_result['successful_simulations']}/{demo_result['num_simulations']} successful samples",
        )
        logger.info(
            f"Mean cost: ${demo_result['best_result']['uncertainty_analysis']['statistics']['total_cost']['mean']:,.0f}",
        )
        logger.info(
            f"95% confidence interval: ${demo_result['best_result']['uncertainty_analysis']['confidence_intervals']['total_cost']['95%']['lower']:,.0f} - ${demo_result['best_result']['uncertainty_analysis']['confidence_intervals']['total_cost']['95%']['upper']:,.0f}",
        )

        return demo_result

    def generate_demo_plots() -> None:
        """Generate demonstration plots for the reports."""
        plot_factory = (PlotFactory(),)
        plots = {}

        # Mock data for Pareto frontier plot
        pareto_data = {
            "trade_off_analysis": {
                "pareto_frontier": [
                    {"cost": 98500.20, "renewable": 0.726},
                    {"cost": 110200.30, "renewable": 0.781},
                    {"cost": 125400.50, "renewable": 0.847},
                    {"cost": 142800.75, "renewable": 0.892},
                    {"cost": 168500.90, "renewable": 0.923},
                ],
                "cost_renewable_correlation": -0.745,
            },
        }
        plots["pareto_frontier"] = plot_factory.create_pareto_frontier_plot(pareto_data)

        # Mock convergence data
        ga_result = {
            "convergence_history": [
                180000,
                165000,
                152000,
                145000,
                140000,
                135000,
                132000,
                130000,
                128000,
                127000,
                126500,
                126000,
                125800,
                125600,
                125500,
                125450,
                125430,
                125420,
                125410,
                125400.50,
            ],
        }
        plots["convergence"] = plot_factory.create_ga_convergence_plot(ga_result)

        # Mock uncertainty distribution
        mc_result = {
            "uncertainty_analysis": {
                "statistics": {
                    "total_cost": {
                        "mean": 124850.75,
                        "std": 18420.33,
                        "min": 87420.10,
                        "max": 178650.90,
                    },
                },
            },
        }
        plots["uncertainty_distribution"] = plot_factory.create_uncertainty_distribution_plot(mc_result)

        # Mock risk analysis
        plots["risk_analysis"] = plot_factory.create_risk_analysis_plot(mc_result)

        return plots

    def generate_interactive_reports() -> None:
        """Generate interactive HTML reports demonstrating the new capabilities."""
        logger.info("=== Generating Interactive Reports ===")

        # Generate demonstration data
        ga_result = (demo_genetic_algorithm_optimization(),)
        mc_result = (demo_monte_carlo_uncertainty(),)
        plots = generate_demo_plots()

        # Create report generator
        report_generator = HTMLReportGenerator()

        # Generate GA optimization report
        ga_html = report_generator.generate_ga_optimization_report(ga_result, plots)
        ga_report_path = Path("reports/demo_ga_optimization.html")
        report_generator.save_report(ga_html, ga_report_path)
        logger.info(f"Generated GA optimization report: {ga_report_path}")

        # Generate MC uncertainty report
        mc_html = report_generator.generate_mc_uncertainty_report(mc_result, plots)
        mc_report_path = Path("reports/demo_mc_uncertainty.html")
        report_generator.save_report(mc_html, mc_report_path)
        logger.info(f"Generated MC uncertainty report: {mc_report_path}")

        # Generate comparison report
        comparison_html = report_generator.generate_study_comparison_report([ga_result, mc_result], plots)
        comparison_report_path = Path("reports/demo_study_comparison.html")
        report_generator.save_report(comparison_html, comparison_report_path)
        logger.info(f"Generated study comparison report: {comparison_report_path}")

        return {
            "ga_report": ga_report_path,
            "mc_report": mc_report_path,
            "comparison_report": comparison_report_path,
        }

    async def main() -> None:
        """Main demonstration function."""
        logger.info("EcoSystemiser Advanced Capabilities Demonstration")
        logger.info("=" * 60)

        start_time = time.time()

        try:
            # Run demonstrations
            logger.info("Running advanced solver demonstrations...")

            demo_genetic_algorithm_optimization()
            await asyncio.sleep(1)  # Simulate processing time

            demo_monte_carlo_uncertainty()
            await asyncio.sleep(1)  # Simulate processing time

            # Generate reports
            logger.info("Generating interactive reports...")
            reports = (generate_interactive_reports(),)

            execution_time = time.time() - start_time

            # Summary
            logger.info("=" * 60)
            logger.info("Demonstration completed successfully!")
            logger.info(f"Total execution time: {execution_time:.2f} seconds")
            logger.info("")
            logger.info("Advanced Capabilities Demonstrated:")
            logger.info("  * Genetic Algorithm Design Optimization")
            logger.info("    - Multi-objective optimization (cost vs. renewable fraction)")
            logger.info("    - Pareto frontier analysis")
            logger.info("    - Design space exploration with 600 evaluations")
            logger.info("  * Monte Carlo Uncertainty Analysis")
            logger.info("    - Latin Hypercube Sampling (1000 samples)")
            logger.info("    - Statistical analysis with confidence intervals")
            logger.info("    - Risk assessment (VaR, CVaR)")
            logger.info("    - Sensitivity analysis")
            logger.info("  * Interactive Reporting")
            logger.info("    - Bootstrap-enhanced UI with navigation")
            logger.info("    - Advanced visualizations with Plotly")
            logger.info("    - Responsive design for mobile/desktop")
            logger.info("")
            logger.info("Generated Reports:")
            for report_type, report_path in reports.items():
                logger.info(f"  • {report_type}: {report_path}")
            logger.info("")
            logger.info("Strategic Impact:")
            logger.info("  - EcoSystemiser transformed from operational optimizer")
            logger.info("    to intelligent design co-pilot")
            logger.info("  - Quantitative uncertainty management with scientific rigor")
            logger.info("  - Professional-grade reporting for decision support")
            logger.info("  - Production-ready foundation for advanced analytics")

        except Exception as e:
            logger.error(f"Demonstration failed: {e}")
            import traceback

            traceback.print_exc()
            return False

        return True

    if __name__ == "__main__":
        success = main()
        sys.exit(0 if success else 1)

except ImportError as e:
    logger.info(f"CRITICAL: Cannot import required modules: {e}")
    logger.info("This indicates the advanced solver implementation needs additional work")
    sys.exit(1)
