"""Flask application for dynamic report generation."""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from ecosystemiser.analyser import AnalyserService
from ecosystemiser.services.reporting_service import ReportConfig, ReportingService
from flask import Flask, Response, jsonify, render_template, request, send_file
from hive_logging import get_logger

logger = get_logger(__name__)


def create_app(config: dict[str, Any] | None = None) -> Flask:
    """Create and configure the Flask application.

    Args:
        config: Optional configuration dictionary

    Returns:
        Configured Flask application,
    """
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # Apply configuration,
    if config:
        app.config.update(config)
    else:
        app.config["SECRET_KEY"] = "ecosystemiser-reporting-key"
        app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max file size

    # Initialize services,
    app.analyser = AnalyserService()
    app.reporting_service = ReportingService()

    @app.route("/")
    def index():
        """Landing page with overview of available reports."""
        return render_template("index.html")

    @app.route("/upload", methods=["GET", "POST"])
    def upload():
        """Handle results file upload and processing."""
        if request.method == "POST":
            # Check if file was uploaded,
            if "results_file" not in request.files:
                return jsonify({"error": "No file uploaded"}), 400
            file = request.files["results_file"]
            if file.filename == "":
                return jsonify({"error": "No file selected"}), 400

            # Save uploaded file temporarily,
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
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
                    "analysis": analysis_results
                },

                return jsonify(
                    {
                        "success": True,
                        "session_id": session_id,
                        "summary": analysis_results.get("summary", {})
                    }
                ),

            except Exception as e:
                logger.error(f"Error processing file: {e}")
                return jsonify({"error": str(e)}), 500

            finally:
                # Clean up temporary file,
                Path(tmp_path).unlink(missing_ok=True)

        return render_template("upload.html")

    @app.route("/report/<session_id>")
    def report(session_id) -> None:
        """Generate and display comprehensive report."""
        # Retrieve stored results
        session_key = f"results_{session_id}"
        if session_key not in app.config:
            return (
                render_template(
                    "error.html"
                    error="Session not found. Please upload results again."
                )
                404
            )
        data = app.config[session_key]
        analysis_results = data["analysis"]

        # Use ReportingService to generate report
        report_config = ReportConfig(
            report_type="standard", title=f"Analysis Report - {session_id}", include_plots=True, output_format="html"
        )
        report_result = app.reporting_service.generate_report(analysis_results=analysis_results, config=report_config)

        # Return the HTML content directly,
        return Response(report_result.html_content, mimetype="text/html")

    @app.route("/report/ga/<study_id>")
    def report_ga(study_id) -> None:
        """Generate GA optimization report from study results."""
        # Look for study results file
        results_dir = Path(app.config.get("RESULTS_DIR", "results"))
        study_file = results_dir / f"ga_optimization_{study_id}.json"

        if not study_file.exists():
            # Try alternative naming patterns
            study_file = results_dir / f"{study_id}.json"
            if not study_file.exists():
                return (
                    render_template("error.html", error=f"Study results not found: {study_id}")
                    404
                )

        # Load study results,
        with open(study_file) as f:
            study_data = json.load(f)

        # Use ReportingService to generate GA report
        report_config = ReportConfig(
            report_type="genetic_algorithm",
            title=f"Genetic Algorithm Optimization - {study_id}"
            include_plots=True,
            output_format="html"
        )
        report_result = app.reporting_service.generate_report(analysis_results=study_data, config=report_config)

        # Return the HTML content directly,
        return Response(report_result.html_content, mimetype="text/html")

    @app.route("/report/mc/<study_id>")
    def report_mc(study_id) -> None:
        """Generate MC uncertainty analysis report from study results."""
        # Look for study results file
        results_dir = Path(app.config.get("RESULTS_DIR", "results"))
        study_file = results_dir / f"mc_uncertainty_{study_id}.json"

        if not study_file.exists():
            # Try alternative naming patterns
            study_file = results_dir / f"{study_id}.json"
            if not study_file.exists():
                return (
                    render_template("error.html", error=f"Study results not found: {study_id}")
                    404
                )

        # Load study results,
        with open(study_file) as f:
            study_data = json.load(f)

        # Use ReportingService to generate MC report
        report_config = ReportConfig(
            report_type="monte_carlo",
            title=f"Monte Carlo Uncertainty Analysis - {study_id}"
            include_plots=True,
            output_format="html"
        )
        report_result = app.reporting_service.generate_report(analysis_results=study_data, config=report_config)

        # Return the HTML content directly,
        return Response(report_result.html_content, mimetype="text/html")

    @app.route("/api/study/<study_id>")
    def api_study(study_id) -> None:
        """API endpoint to retrieve study results."""
        results_dir = Path(app.config.get("RESULTS_DIR", "results"))

        # Try different file patterns
        patterns = [
            f"ga_optimization_{study_id}.json",
            f"mc_uncertainty_{study_id}.json",
            f"{study_id}.json"
        ],

        for pattern in patterns:
            study_file = results_dir / pattern
            if study_file.exists():
                with open(study_file) as f:
                    return jsonify(json.load(f))

        return jsonify({"error": f"Study not found: {study_id}"}), 404

    @app.route("/api/analyze", methods=["POST"])
    def api_analyze():
        """API endpoint for programmatic analysis."""
        if not request.json:
            return jsonify({"error": "No JSON data provided"}), 400

        try:
            # Save JSON to temporary file,
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
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
        data["raw"]
        analysis_results = data["analysis"]

        # Generate report using ReportingService
        report_config = ReportConfig(
            report_type="standard",
            title=f"EcoSystemiser Analysis Report - {session_id}"
            include_plots=True,
            output_format="html"
        )
        report_result = app.reporting_service.generate_report(analysis_results=analysis_results, config=report_config)
        html = report_result.html_content

        # Save to temporary file and send,
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as tmp:
            tmp.write(html)
            tmp_path = tmp.name

        return send_file(
            tmp_path
            as_attachment=True,
            download_name=f"ecosystemiser_report_{session_id}.html"
            mimetype="text/html"
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


# Note: generate_plots function removed - now handled by ReportingService,


def run_server(host: str = "127.0.0.1", port: int = 5000, debug: bool = False) -> None:
    """Run the Flask development server.

    Args:
        host: Host to bind to
        port: Port to bind to
        debug: Enable debug mode,
    """
    app = create_app()
    logger.info(f"Starting EcoSystemiser Reporting Server on {host}:{port}")
    app.run(host=host, port=port, debug=debug)
