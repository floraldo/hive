"""CLI commands for reporting module."""

import click
import json
from pathlib import Path
from typing import Optional

from EcoSystemiser.analyser import AnalyserService
from EcoSystemiser.reporting import create_app, run_server
from EcoSystemiser.hive_logging_adapter import get_logger

logger = get_logger(__name__)


@click.group()
def report():
    """Report generation and server commands."""
    pass


@report.command()
@click.argument('results_file', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(),
              help='Output directory for report files')
@click.option('--strategies', '-s', multiple=True,
              help='Analysis strategies to run (default: all)')
@click.option('--format', 'output_format', type=click.Choice(['json', 'html']),
              default='json', help='Output format')
def analyze(results_file: str, output: Optional[str], strategies: tuple,
           output_format: str):
    """Analyze simulation results and generate report data.

    Args:
        results_file: Path to simulation results JSON file
    """
    try:
        # Initialize analyser
        analyser = AnalyserService()

        # Run analysis
        strategies_list = list(strategies) if strategies else None
        analysis_results = analyser.analyse(results_file, strategies_list)

        # Determine output path
        if output:
            output_dir = Path(output)
        else:
            output_dir = Path(results_file).parent / 'analysis_output'

        output_dir.mkdir(exist_ok=True)

        if output_format == 'json':
            # Save JSON results
            output_file = output_dir / 'analysis_results.json'
            analyser.save_analysis(analysis_results, str(output_file))
            click.echo(f"Analysis saved to: {output_file}")

        elif output_format == 'html':
            # Generate HTML report (simplified)
            from EcoSystemiser.datavis.plot_factory import PlotFactory

            plot_factory = PlotFactory()

            # Load raw results for plot generation
            with open(results_file, 'r') as f:
                raw_results = json.load(f)

            # Generate plots (simplified version)
            plots = {}
            if 'technical_kpi' in analysis_results.get('analyses', {}):
                kpi_data = analysis_results['analyses']['technical_kpi']
                plots['kpi_gauges'] = plot_factory.create_technical_kpi_gauges(kpi_data)

            # Create basic HTML report
            html_content = create_basic_html_report(analysis_results, plots)

            output_file = output_dir / 'report.html'
            with open(output_file, 'w') as f:
                f.write(html_content)

            click.echo(f"HTML report saved to: {output_file}")

        # Print summary
        summary = analysis_results.get('summary', {})
        click.echo(f"\nAnalysis Summary:")
        click.echo(f"  Successful analyses: {summary.get('successful_analyses', 0)}")
        click.echo(f"  Failed analyses: {summary.get('failed_analyses', 0)}")

        if 'key_metrics' in summary:
            key_metrics = summary['key_metrics']
            if 'grid_self_sufficiency' in key_metrics:
                click.echo(f"  Grid self-sufficiency: {key_metrics['grid_self_sufficiency']:.1%}")
            if 'renewable_fraction' in key_metrics:
                click.echo(f"  Renewable fraction: {key_metrics['renewable_fraction']:.1%}")

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@report.command()
@click.option('--host', default='127.0.0.1', help='Host to bind to')
@click.option('--port', default=5000, help='Port to bind to')
@click.option('--debug', is_flag=True, help='Enable debug mode')
def server(host: str, port: int, debug: bool):
    """Start the reporting web server.

    This starts a Flask web application for interactive report generation.
    """
    click.echo(f"Starting EcoSystemiser Reporting Server...")
    click.echo(f"Server will be available at: http://{host}:{port}")
    click.echo(f"Upload your simulation results to generate reports.")
    click.echo(f"Press Ctrl+C to stop the server.")

    try:
        run_server(host=host, port=port, debug=debug)
    except KeyboardInterrupt:
        click.echo("\nShutting down server...")
    except Exception as e:
        logger.error(f"Server error: {e}")
        click.echo(f"Server error: {e}", err=True)
        raise click.Abort()


@report.command()
@click.argument('results_file', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), default='report.html',
              help='Output HTML file path')
def generate(results_file: str, output: str):
    """Generate a standalone HTML report.

    Args:
        results_file: Path to simulation results JSON file
    """
    try:
        # Run analysis
        analyser = AnalyserService()
        analysis_results = analyser.analyse(results_file)

        # Load raw results
        with open(results_file, 'r') as f:
            raw_results = json.load(f)

        # Generate plots
        from EcoSystemiser.datavis.plot_factory import PlotFactory
        plot_factory = PlotFactory()

        plots = {}
        analyses = analysis_results.get('analyses', {})

        # Generate relevant plots
        if 'technical_kpi' in analyses:
            plots['kpi_gauges'] = plot_factory.create_technical_kpi_gauges(analyses['technical_kpi'])

        if 'economic' in analyses:
            plots['economic_summary'] = plot_factory.create_economic_summary_plot(analyses['economic'])

        if 'sensitivity' in analyses:
            plots['sensitivity_heatmap'] = plot_factory.create_sensitivity_heatmap(analyses['sensitivity'])
            plots['pareto_frontier'] = plot_factory.create_pareto_frontier_plot(analyses['sensitivity'])

        # Create HTML report
        html_content = create_standalone_html_report(analysis_results, plots)

        # Save report
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            f.write(html_content)

        click.echo(f"HTML report generated: {output_path}")

        # Print summary
        summary = analysis_results.get('summary', {})
        click.echo(f"Report includes {summary.get('successful_analyses', 0)} successful analyses")

    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


def create_basic_html_report(analysis_results: dict, plots: dict) -> str:
    """Create a basic HTML report without Flask templates."""
    summary = analysis_results.get('summary', {})

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>EcoSystemiser Analysis Report</title>
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            .metric {{ display: inline-block; margin: 20px; text-align: center; }}
            .metric-value {{ font-size: 2em; font-weight: bold; color: #2E7D32; }}
            .metric-label {{ color: #666; }}
            .plot {{ margin: 30px 0; }}
        </style>
    </head>
    <body>
        <h1>EcoSystemiser Analysis Report</h1>

        <h2>Summary</h2>
        <div class="metric">
            <div class="metric-value">{summary.get('successful_analyses', 0)}</div>
            <div class="metric-label">Successful Analyses</div>
        </div>
        <div class="metric">
            <div class="metric-value">{summary.get('failed_analyses', 0)}</div>
            <div class="metric-label">Failed Analyses</div>
        </div>

        <h2>Analysis Results</h2>
        <pre>{json.dumps(analysis_results, indent=2)}</pre>

        <h2>Visualizations</h2>
        <div id="plots"></div>

        <script>
        // Add plot rendering if plots are available
        const plots = {json.dumps(plots)};
        Object.keys(plots).forEach(key => {{
            if (plots[key]) {{
                const div = document.createElement('div');
                div.id = key;
                div.className = 'plot';
                document.getElementById('plots').appendChild(div);
                Plotly.newPlot(key, plots[key]);
            }}
        }});
        </script>
    </body>
    </html>
    """
    return html


def create_standalone_html_report(analysis_results: dict, plots: dict) -> str:
    """Create a comprehensive standalone HTML report."""
    summary = analysis_results.get('summary', {})
    analyses = analysis_results.get('analyses', {})

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>EcoSystemiser Analysis Report</title>
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ font-family: 'Segoe UI', sans-serif; }}
            .metric-card {{ text-align: center; padding: 1rem; background: #f8f9fa; border-radius: 8px; margin: 1rem; }}
            .metric-value {{ font-size: 2rem; font-weight: bold; color: #2E7D32; }}
            .metric-label {{ color: #666; font-size: 0.9rem; }}
            .plot-container {{ margin: 2rem 0; padding: 1rem; border: 1px solid #dee2e6; border-radius: 8px; }}
        </style>
    </head>
    <body class="container">
        <h1 class="text-center mt-4 mb-4">EcoSystemiser Analysis Report</h1>

        <div class="row">
            <div class="col-md-3">
                <div class="metric-card">
                    <div class="metric-value">{summary.get('successful_analyses', 0)}</div>
                    <div class="metric-label">Successful Analyses</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="metric-card">
                    <div class="metric-value">{summary.get('failed_analyses', 0)}</div>
                    <div class="metric-label">Failed Analyses</div>
                </div>
            </div>
    """

    # Add key metrics if available
    key_metrics = summary.get('key_metrics', {})
    if 'grid_self_sufficiency' in key_metrics:
        html += f"""
            <div class="col-md-3">
                <div class="metric-card">
                    <div class="metric-value">{key_metrics['grid_self_sufficiency']:.1%}</div>
                    <div class="metric-label">Grid Self-Sufficiency</div>
                </div>
            </div>
        """

    if 'renewable_fraction' in key_metrics:
        html += f"""
            <div class="col-md-3">
                <div class="metric-card">
                    <div class="metric-value">{key_metrics['renewable_fraction']:.1%}</div>
                    <div class="metric-label">Renewable Fraction</div>
                </div>
            </div>
        """

    html += """
        </div>

        <h2 class="mt-5">Analysis Results</h2>
    """

    # Add plot containers
    for plot_name in plots.keys():
        html += f"""
        <div class="plot-container">
            <h4>{plot_name.replace('_', ' ').title()}</h4>
            <div id="{plot_name}"></div>
        </div>
        """

    # Add detailed results tables for each analysis type
    if 'technical_kpi' in analyses:
        html += """
        <h3>Technical KPIs</h3>
        <table class="table table-striped">
        """
        for key, value in analyses['technical_kpi'].items():
            if isinstance(value, (int, float)):
                if 0 <= value <= 1:
                    formatted_value = f"{value:.1%}"
                else:
                    formatted_value = f"{value:.2f}"
            else:
                formatted_value = str(value)

            html += f"""
            <tr>
                <td>{key.replace('_', ' ').title()}</td>
                <td>{formatted_value}</td>
            </tr>
            """
        html += "</table>"

    if 'economic' in analyses:
        html += """
        <h3>Economic Analysis</h3>
        <table class="table table-striped">
        """
        economic = analyses['economic']
        economic_keys = ['lcoe', 'npv', 'payback_period_years', 'capex_total', 'opex_annual']

        for key in economic_keys:
            if key in economic:
                value = economic[key]
                if key == 'lcoe':
                    formatted_value = f"${value:.3f}/kWh"
                elif 'cost' in key or 'npv' in key or 'opex' in key or 'capex' in key:
                    formatted_value = f"${value:,.0f}"
                elif 'period' in key:
                    formatted_value = f"{value:.1f} years"
                else:
                    formatted_value = f"{value:.2f}"

                html += f"""
                <tr>
                    <td>{key.replace('_', ' ').title()}</td>
                    <td>{formatted_value}</td>
                </tr>
                """
        html += "</table>"

    # Add script to render plots
    html += f"""
        <script>
        const plots = {json.dumps(plots)};
        Object.keys(plots).forEach(key => {{
            if (plots[key] && document.getElementById(key)) {{
                Plotly.newPlot(key, plots[key], {{}}, {{responsive: true}});
            }}
        }});
        </script>
    </body>
    </html>
    """

    return html


if __name__ == '__main__':
    report()