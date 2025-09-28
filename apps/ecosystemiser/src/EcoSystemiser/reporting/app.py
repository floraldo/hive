"""Flask application for dynamic report generation."""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from ecosystemiser.analyser import AnalyserService
from ecosystemiser.datavis.plot_factory import PlotFactory
from ecosystemiser.reporting.generator import HTMLReportGenerator
from flask import Flask, jsonify, render_template, request, send_file
from hive_logging import get_logger

logger = get_logger(__name__)


def create_app(config: Optional[Dict[str, Any]] = None) -> Flask:
    """Create and configure the Flask application.

    Args:
        config: Optional configuration dictionary

    Returns:
        Configured Flask application
    """
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # Apply configuration
    if config:
        app.config.update(config)
    else:
        app.config["SECRET_KEY"] = "ecosystemiser-reporting-key"
        app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max file size

    # Initialize services
    app.analyser = AnalyserService()
    app.plot_factory = PlotFactory()

    @app.route("/")
    def index():
        """Landing page with overview of available reports."""
        return render_template("index.html")

    @app.route("/upload", methods=["GET", "POST"])
    def upload():
        """Handle results file upload and processing."""
        if request.method == "POST":
            # Check if file was uploaded
            if "results_file" not in request.files:
                return jsonify({"error": "No file uploaded"}), 400

            file = request.files["results_file"]
            if file.filename == "":
                return jsonify({"error": "No file selected"}), 400

            # Save uploaded file temporarily
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as tmp:
                content = file.read().decode("utf-8")
                json_data = json.loads(content)  # Validate JSON
                json.dump(json_data, tmp)
                tmp_path = tmp.name

            try:
                # Run analysis
                analysis_results = app.analyser.analyse(tmp_path)

                # Store results in session for report generation
                session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
                app.config[f"results_{session_id}"] = {
                    "raw": json_data,
                    "analysis": analysis_results,
                }

                return jsonify(
                    {
                        "success": True,
                        "session_id": session_id,
                        "summary": analysis_results.get("summary", {}),
                    }
                )

            except Exception as e:
                logger.error(f"Error processing file: {e}")
                return jsonify({"error": str(e)}), 500

            finally:
                # Clean up temporary file
                Path(tmp_path).unlink(missing_ok=True)

        return render_template("upload.html")

    @app.route("/report/<session_id>")
    def report(session_id):
        """Generate and display comprehensive report."""
        # Retrieve stored results
        session_key = f"results_{session_id}"
        if session_key not in app.config:
            return (
                render_template(
                    "error.html",
                    error="Session not found. Please upload results again.",
                ),
                404,
            )

        data = app.config[session_key]
        raw_results = data["raw"]
        analysis_results = data["analysis"]

        # Generate plots
        plots = generate_plots(app.plot_factory, raw_results, analysis_results)

        # Prepare report data
        report_data = {
            "session_id": session_id,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "metadata": analysis_results.get("metadata", {}),
            "summary": analysis_results.get("summary", {}),
            "analyses": analysis_results.get("analyses", {}),
            "plots": plots,
        }

        return render_template("report.html", **report_data)

    @app.route("/report/ga/<study_id>")
    def report_ga(study_id):
        """Generate GA optimization report from study results."""
        # Look for study results file
        results_dir = Path(app.config.get("RESULTS_DIR", "results"))
        study_file = results_dir / f"ga_optimization_{study_id}.json"

        if not study_file.exists():
            # Try alternative naming patterns
            study_file = results_dir / f"{study_id}.json"
            if not study_file.exists():
                return (
                    render_template(
                        "error.html", error=f"Study results not found: {study_id}"
                    ),
                    404,
                )

        # Load study results
        with open(study_file, "r") as f:
            study_data = json.load(f)

        # Extract GA-specific results
        ga_result = study_data.get("best_result", {})

        # Generate GA-specific plots
        plots = {}
        if ga_result:
            plots["pareto_front"] = app.plot_factory.create_ga_pareto_front_plot(
                ga_result
            )
            plots["convergence"] = app.plot_factory.create_ga_convergence_plot(
                ga_result
            )

        # Prepare report data
        report_data = {
            "study_id": study_id,
            "study_type": "genetic_algorithm",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "summary": study_data.get("summary_statistics", {}),
            "best_result": ga_result,
            "num_simulations": study_data.get("num_simulations", 0),
            "execution_time": study_data.get("execution_time", 0),
            "plots": plots,
            "objectives": study_data.get("configuration", {}).get("objectives", []),
        }

        return render_template("report_ga.html", **report_data)

    @app.route("/report/mc/<study_id>")
    def report_mc(study_id):
        """Generate MC uncertainty analysis report from study results."""
        # Look for study results file
        results_dir = Path(app.config.get("RESULTS_DIR", "results"))
        study_file = results_dir / f"mc_uncertainty_{study_id}.json"

        if not study_file.exists():
            # Try alternative naming patterns
            study_file = results_dir / f"{study_id}.json"
            if not study_file.exists():
                return (
                    render_template(
                        "error.html", error=f"Study results not found: {study_id}"
                    ),
                    404,
                )

        # Load study results
        with open(study_file, "r") as f:
            study_data = json.load(f)

        # Extract MC-specific results
        mc_result = study_data.get("best_result", {})

        # Generate MC-specific plots
        plots = {}
        if mc_result:
            plots["uncertainty"] = (
                app.plot_factory.create_uncertainty_distribution_plot(mc_result)
            )
            plots["risk"] = app.plot_factory.create_risk_analysis_plot(mc_result)
            if "sensitivity" in mc_result:
                plots["sensitivity"] = app.plot_factory.create_sensitivity_tornado_plot(
                    mc_result
                )
            if "scenarios" in mc_result:
                plots["scenarios"] = app.plot_factory.create_scenario_comparison_plot(
                    mc_result
                )

        # Prepare report data
        report_data = {
            "study_id": study_id,
            "study_type": "monte_carlo",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "summary": study_data.get("summary_statistics", {}),
            "uncertainty_analysis": mc_result.get("uncertainty_analysis", {}),
            "num_samples": study_data.get("num_simulations", 0),
            "execution_time": study_data.get("execution_time", 0),
            "plots": plots,
            "sampling_method": study_data.get("configuration", {}).get(
                "sampling_method", "lhs"
            ),
        }

        return render_template("report_mc.html", **report_data)

    @app.route("/api/study/<study_id>")
    def api_study(study_id):
        """API endpoint to retrieve study results."""
        results_dir = Path(app.config.get("RESULTS_DIR", "results"))

        # Try different file patterns
        patterns = [
            f"ga_optimization_{study_id}.json",
            f"mc_uncertainty_{study_id}.json",
            f"{study_id}.json",
        ]

        for pattern in patterns:
            study_file = results_dir / pattern
            if study_file.exists():
                with open(study_file, "r") as f:
                    return jsonify(json.load(f))

        return jsonify({"error": f"Study not found: {study_id}"}), 404

    @app.route("/api/analyze", methods=["POST"])
    def api_analyze():
        """API endpoint for programmatic analysis."""
        if not request.json:
            return jsonify({"error": "No JSON data provided"}), 400

        try:
            # Save JSON to temporary file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as tmp:
                json.dump(request.json, tmp)
                tmp_path = tmp.name

            # Run analysis
            strategies = request.args.getlist("strategies")
            if not strategies:
                strategies = None  # Use all strategies

            analysis_results = app.analyser.analyse(tmp_path, strategies)

            return jsonify(analysis_results)

        except Exception as e:
            logger.error(f"API analysis error: {e}")
            return jsonify({"error": str(e)}), 500

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    @app.route("/api/plot/<plot_type>", methods=["POST"])
    def api_plot(plot_type):
        """API endpoint for generating specific plots."""
        if not request.json:
            return jsonify({"error": "No JSON data provided"}), 400

        try:
            data = request.json
            plot_func = getattr(app.plot_factory, f"create_{plot_type}_plot", None)

            if not plot_func:
                return jsonify({"error": f"Unknown plot type: {plot_type}"}), 400

            plot_data = plot_func(data)
            return jsonify(plot_data)

        except Exception as e:
            logger.error(f"Plot generation error: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/download/<session_id>")
    def download_report(session_id):
        """Download report as HTML file."""
        # Generate report HTML
        session_key = f"results_{session_id}"
        if session_key not in app.config:
            return jsonify({"error": "Session not found"}), 404

        data = app.config[session_key]
        raw_results = data["raw"]
        analysis_results = data["analysis"]

        # Generate plots
        plots = generate_plots(app.plot_factory, raw_results, analysis_results)

        # Use centralized generator for standalone reports
        generator = HTMLReportGenerator()
        html = generator.generate_standalone_report(
            analysis_results, plots, f"EcoSystemiser Analysis Report - {session_id}"
        )

        # Save to temporary file and send
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as tmp:
            tmp.write(html)
            tmp_path = tmp.name

        return send_file(
            tmp_path,
            as_attachment=True,
            download_name=f"ecosystemiser_report_{session_id}.html",
            mimetype="text/html",
        )

    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 errors."""
        return render_template("error.html", error="Page not found"), 404

    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 errors."""
        logger.error(f"Internal server error: {error}")
        return render_template("error.html", error="Internal server error"), 500

    return app


def generate_plots(
    plot_factory: PlotFactory,
    raw_results: Dict[str, Any],
    analysis_results: Dict[str, Any],
) -> Dict[str, Any]:
    """Generate all relevant plots for the report.

    Args:
        plot_factory: PlotFactory instance
        raw_results: Raw simulation results
        analysis_results: Analysis results

    Returns:
        Dictionary of plot data
    """
    plots = {}

    # Technical KPI gauges
    if "technical_kpi" in analysis_results.get("analyses", {}):
        kpi_data = analysis_results["analyses"]["technical_kpi"]
        plots["kpi_gauges"] = plot_factory.create_technical_kpi_gauges(kpi_data)

    # Economic summary
    if "economic" in analysis_results.get("analyses", {}):
        economic_data = analysis_results["analyses"]["economic"]
        plots["economic_summary"] = plot_factory.create_economic_summary_plot(
            economic_data
        )

    # Sensitivity analysis
    if "sensitivity" in analysis_results.get("analyses", {}):
        sensitivity_data = analysis_results["analyses"]["sensitivity"]
        plots["sensitivity_heatmap"] = plot_factory.create_sensitivity_heatmap(
            sensitivity_data
        )
        plots["pareto_frontier"] = plot_factory.create_pareto_frontier_plot(
            sensitivity_data
        )

    # Original visualizations from raw results
    if "system" in raw_results:
        system = raw_results["system"]
        # These would need the actual system object, not just the dictionary
        # For now, we'll skip these as they require the full system instance

    # KPI dashboard from raw KPIs
    if "kpis" in raw_results:
        plots["kpi_dashboard"] = plot_factory.create_kpi_dashboard(raw_results["kpis"])

    # Solver metrics
    if "solver_metrics" in raw_results:
        plots["optimization_status"] = (
            plot_factory.create_optimization_convergence_plot(
                raw_results["solver_metrics"]
            )
        )

    return plots


def run_server(host: str = "127.0.0.1", port: int = 5000, debug: bool = False):
    """Run the Flask development server.

    Args:
        host: Host to bind to
        port: Port to bind to
        debug: Enable debug mode
    """
    app = create_app()
    logger.info(f"Starting EcoSystemiser Reporting Server on {host}:{port}")
    app.run(host=host, port=port, debug=debug)
