"""Centralized HTML report generation for EcoSystemiser.

This module provides a unified approach to generating HTML reports,
eliminating code duplication between CLI and web interfaces.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class HTMLReportGenerator:
    """Generate HTML reports from analysis results with consistent formatting."""

    def __init__(self):
        """Initialize the report generator."""
        self.plotly_cdn = "https://cdn.plot.ly/plotly-latest.min.js"
        self.bootstrap_cdn = "https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css"
        self.bootstrap_js_cdn = "https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"

    def generate_standalone_report(
        self,
        analysis_results: Dict[str, Any],
        plots: Optional[Dict[str, Any]] = None,
        title: str = "EcoSystemiser Analysis Report",
        report_type: str = "standard"
    ) -> str:
        """Generate a complete standalone HTML report.

        Args:
            analysis_results: Analysis results dictionary
            plots: Optional dictionary of Plotly plots
            title: Report title

        Returns:
            Complete HTML string
        """
        # Build HTML sections based on report type
        head_html = self._generate_head(title, include_bootstrap=(report_type in ['genetic_algorithm', 'monte_carlo', 'study']))

        if report_type == 'genetic_algorithm':
            content_html = self._generate_ga_report_content(analysis_results, plots or {})
        elif report_type == 'monte_carlo':
            content_html = self._generate_mc_report_content(analysis_results, plots or {})
        elif report_type == 'study':
            content_html = self._generate_study_report_content(analysis_results, plots or {})
        else:
            # Standard report
            summary_html = self._generate_summary_section(analysis_results)
            plots_html = self._generate_plots_section(plots or {})
            details_html = self._generate_details_section(analysis_results)
            content_html = f"{summary_html}{plots_html}{details_html}"

        scripts_html = self._generate_scripts(plots or {}, report_type)

        # Assemble complete HTML
        timestamp_html = f'<div class="timestamp">Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>'

        if report_type in ['genetic_algorithm', 'monte_carlo', 'study']:
            # Interactive report with navigation
            html = f"""
<!DOCTYPE html>
<html>
{head_html}
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-success">
        <div class="container-fluid">
            <a class="navbar-brand" href="#">{title}</a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav ms-auto">
                    <li class="nav-item"><a class="nav-link" href="#summary">Summary</a></li>
                    <li class="nav-item"><a class="nav-link" href="#results">Results</a></li>
                    <li class="nav-item"><a class="nav-link" href="#analysis">Analysis</a></li>
                    <li class="nav-item"><a class="nav-link" href="#details">Details</a></li>
                </ul>
            </div>
        </div>
    </nav>
    <div class="container-fluid mt-4">
        {timestamp_html}
        {content_html}
    </div>
    {scripts_html}
</body>
</html>
            """
        else:
            # Standard report
            html = f"""
<!DOCTYPE html>
<html>
{head_html}
<body>
    <div class="container">
        <h1>{title}</h1>
        {timestamp_html}
        {content_html}
    </div>
    {scripts_html}
</body>
</html>
            """
        return html

    def generate_report_body(
        self,
        analysis_results: Dict[str, Any],
        plots: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate just the body content for embedding in templates.

        Args:
            analysis_results: Analysis results dictionary
            plots: Optional dictionary of Plotly plots

        Returns:
            HTML body content string
        """
        summary_html = self._generate_summary_section(analysis_results)
        plots_html = self._generate_plots_section(plots or {})
        details_html = self._generate_details_section(analysis_results)

        return f"""
{summary_html}
{plots_html}
{details_html}
        """

    def _generate_head(self, title: str, include_bootstrap: bool = False) -> str:
        """Generate HTML head section with styles and dependencies."""
        bootstrap_css = f'<link href="{self.bootstrap_cdn}" rel="stylesheet">' if include_bootstrap else ''
        bootstrap_js = f'<script src="{self.bootstrap_js_cdn}"></script>' if include_bootstrap else ''

        return f"""
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    {bootstrap_css}
    <script src="{self.plotly_cdn}"></script>
    {bootstrap_js}
    {self._generate_styles(include_bootstrap)}
</head>
        """

    def _generate_styles(self, include_bootstrap: bool = False) -> str:
        """Generate CSS styles for the report."""
        base_styles = """
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            margin: 0;
            padding: 0;
            background: #f5f5f5;
            color: #333;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 40px 20px;
            background: white;
            box-shadow: 0 0 20px rgba(0,0,0,0.05);
        }
        """

        return f"""
    <style>
        {base_styles}
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            margin: 0;
            padding: 0;
            background: #f5f5f5;
            color: #333;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 40px 20px;
            background: white;
            box-shadow: 0 0 20px rgba(0,0,0,0.05);
        }
        h1 {
            color: #2E7D32;
            border-bottom: 3px solid #2E7D32;
            padding-bottom: 10px;
            margin-bottom: 30px;
        }
        h2 {
            color: #388E3C;
            margin-top: 40px;
            margin-bottom: 20px;
            border-bottom: 1px solid #e0e0e0;
            padding-bottom: 8px;
        }
        h3 {
            color: #43A047;
            margin-top: 25px;
            margin-bottom: 15px;
        }
        .timestamp {
            color: #666;
            font-size: 0.9em;
            margin-bottom: 30px;
        }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }
        .metric {
            background: linear-gradient(135deg, #E8F5E9 0%, #C8E6C9 100%);
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: transform 0.2s;
        }
        .metric:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        }
        .metric-value {
            font-size: 2.5em;
            font-weight: bold;
            color: #1B5E20;
            margin-bottom: 8px;
        }
        .metric-label {
            color: #558B2F;
            font-size: 0.95em;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .metric.warning .metric-value {
            color: #F57C00;
        }
        .metric.error .metric-value {
            color: #D32F2F;
        }
        .plot {
            margin: 30px 0;
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .plot-title {
            font-weight: 600;
            color: #388E3C;
            margin-bottom: 15px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        thead {
            background: linear-gradient(135deg, #4CAF50 0%, #45A049 100%);
            color: white;
        }
        th {
            padding: 12px 15px;
            text-align: left;
            font-weight: 600;
        }
        td {
            padding: 10px 15px;
            border-bottom: 1px solid #e0e0e0;
        }
        tbody tr:hover {
            background: #F1F8E9;
        }
        tbody tr:last-child td {
            border-bottom: none;
        }
        .success {
            color: #2E7D32;
            font-weight: 600;
        }
        .error {
            color: #D32F2F;
            font-weight: 600;
        }
        .warning {
            color: #F57C00;
            font-weight: 600;
        }
        .info-box {
            background: #E3F2FD;
            border-left: 4px solid #2196F3;
            padding: 15px 20px;
            margin: 20px 0;
            border-radius: 4px;
        }
        .info-box h4 {
            margin: 0 0 10px 0;
            color: #1565C0;
        }

        /* Interactive Report Styles */
        .result-card {
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            transition: transform 0.2s;
        }
        .result-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        }
        .result-card-header {
            background: linear-gradient(135deg, #4CAF50 0%, #45A049 100%);
            color: white;
            padding: 15px 20px;
            border-radius: 8px 8px 0 0;
            font-weight: 600;
        }
        .result-card-body {
            padding: 20px;
        }
        .parameter-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }
        .parameter-item {
            background: #f8f9fa;
            padding: 12px 15px;
            border-radius: 6px;
            border-left: 4px solid #4CAF50;
        }
        .parameter-name {
            font-weight: 600;
            color: #2E7D32;
            margin-bottom: 4px;
        }
        .parameter-value {
            color: #666;
            font-size: 0.95em;
        }
        .objective-badge {
            display: inline-block;
            padding: 4px 12px;
            background: #E8F5E9;
            color: #2E7D32;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 500;
            margin: 2px 4px;
        }
        .convergence-indicator {
            display: inline-flex;
            align-items: center;
            padding: 8px 12px;
            border-radius: 6px;
            font-weight: 500;
        }
        .convergence-indicator.converged {
            background: #d4edda;
            color: #155724;
        }
        .convergence-indicator.failed {
            background: #f8d7da;
            color: #721c24;
        }
        .stats-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid #e9ecef;
        }
        .stats-row:last-child {
            border-bottom: none;
        }
        .stats-label {
            font-weight: 500;
            color: #495057;
        }
        .stats-value {
            color: #2E7D32;
            font-weight: 600;
        }
        .tab-content {
            margin-top: 20px;
        }
        .risk-meter {
            display: flex;
            align-items: center;
            margin: 10px 0;
        }
        .risk-bar {
            flex: 1;
            height: 20px;
            background: linear-gradient(to right, #4CAF50, #FFC107, #F44336);
            border-radius: 10px;
            margin: 0 10px;
            position: relative;
        }
        .risk-indicator {
            position: absolute;
            top: -2px;
            width: 4px;
            height: 24px;
            background: #333;
            border-radius: 2px;
        }
    </style>
        """

    def _generate_summary_section(self, analysis_results: Dict[str, Any]) -> str:
        """Generate summary metrics section."""
        summary = analysis_results.get('summary', {})

        if not summary:
            return ""

        html = '<section class="summary">\n<h2>Summary</h2>\n<div class="metrics-grid">\n'

        # Basic metrics
        successful = summary.get('successful_analyses', 0)
        failed = summary.get('failed_analyses', 0)

        html += f'''
    <div class="metric">
        <div class="metric-value">{successful}</div>
        <div class="metric-label">Successful Analyses</div>
    </div>
        '''

        if failed > 0:
            html += f'''
    <div class="metric warning">
        <div class="metric-value">{failed}</div>
        <div class="metric-label">Failed Analyses</div>
    </div>
            '''

        # Key performance metrics
        key_metrics = summary.get('key_metrics', {})

        metric_formatters = {
            'grid_self_sufficiency': ('Grid Self-Sufficiency', lambda x: f'{x:.1%}'),
            'renewable_fraction': ('Renewable Fraction', lambda x: f'{x:.1%}'),
            'total_cost': ('Total Cost', lambda x: f'${x:,.0f}'),
            'emissions_reduction': ('Emissions Reduction', lambda x: f'{x:.1%}'),
            'peak_demand_reduction': ('Peak Demand Reduction', lambda x: f'{x:.1%}'),
            'storage_utilization': ('Storage Utilization', lambda x: f'{x:.1%}'),
        }

        for key, (label, formatter) in metric_formatters.items():
            if key in key_metrics:
                value = key_metrics[key]
                formatted_value = formatter(value) if callable(formatter) else str(value)
                html += f'''
    <div class="metric">
        <div class="metric-value">{formatted_value}</div>
        <div class="metric-label">{label}</div>
    </div>
                '''

        html += '</div>\n</section>\n'
        return html

    def _generate_plots_section(self, plots: Dict[str, Any]) -> str:
        """Generate plots section."""
        if not plots:
            return ""

        html = '<section class="visualizations">\n<h2>Visualizations</h2>\n'

        for plot_id, plot_data in plots.items():
            plot_title = plot_id.replace('_', ' ').title()
            html += f'''
<div class="plot">
    <div class="plot-title">{plot_title}</div>
    <div id="{plot_id}"></div>
</div>
            '''

        html += '</section>\n'
        return html

    def _generate_details_section(self, analysis_results: Dict[str, Any]) -> str:
        """Generate detailed results tables."""
        analyses = analysis_results.get('analyses', {})

        if not analyses:
            return ""

        html = '<section class="details">\n<h2>Detailed Results</h2>\n'

        for analysis_name, analysis_data in analyses.items():
            if isinstance(analysis_data, dict) and 'error' not in analysis_data:
                section_title = analysis_name.replace('_', ' ').title()
                html += f'<h3>{section_title}</h3>\n'
                html += self._generate_table(analysis_data)

        html += '</section>\n'
        return html

    def _generate_table(self, data: Dict[str, Any]) -> str:
        """Generate HTML table from dictionary data."""
        if not data:
            return ""

        # Filter out meta fields
        skip_fields = {'analysis_type', 'analysis_version', 'timestamp', 'id'}

        html = '<table>\n<thead>\n<tr><th>Metric</th><th>Value</th></tr>\n</thead>\n<tbody>\n'

        for key, value in data.items():
            if key in skip_fields:
                continue

            # Format key
            formatted_key = key.replace('_', ' ').title()

            # Format value
            if isinstance(value, bool):
                formatted_value = 'Yes' if value else 'No'
                css_class = 'success' if value else 'warning'
            elif isinstance(value, (int, float)):
                if 0 <= value <= 1 and 'ratio' in key.lower() or 'fraction' in key.lower():
                    formatted_value = f'{value:.1%}'
                elif value > 1000000:
                    formatted_value = f'{value:,.0f}'
                else:
                    formatted_value = f'{value:.2f}'
                css_class = ''
            elif isinstance(value, list):
                formatted_value = f'[{len(value)} items]'
                css_class = 'info'
            elif isinstance(value, dict):
                formatted_value = f'{{{len(value)} fields}}'
                css_class = 'info'
            else:
                formatted_value = str(value)[:100]  # Truncate long strings
                css_class = ''

            html += f'<tr><td>{formatted_key}</td><td class="{css_class}">{formatted_value}</td></tr>\n'

        html += '</tbody>\n</table>\n'
        return html

    def _generate_scripts(self, plots: Dict[str, Any], report_type: str = "standard") -> str:
        """Generate JavaScript for rendering plots and interactive features."""
        plot_script = ""
        if plots:
            plot_script = f"""
    // Plot rendering
    const plots = {json.dumps(plots)};
    Object.keys(plots).forEach(plotId => {{
        const element = document.getElementById(plotId);
        if (element && plots[plotId]) {{
            const layout = {{
                autosize: true,
                margin: {{l: 50, r: 50, t: 50, b: 50}},
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                ...plots[plotId].layout
            }};
            const config = {{
                responsive: true,
                displayModeBar: true,
                displaylogo: false,
                modeBarButtonsToRemove: ['sendDataToCloud']
            }};
            Plotly.newPlot(plotId, plots[plotId].data || plots[plotId], layout, config);
        }}
    }});
            """

        interactive_script = ""
        if report_type in ['genetic_algorithm', 'monte_carlo', 'study']:
            interactive_script = """
    // Interactive features
    // Smooth scrolling for navigation
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({ behavior: 'smooth' });
            }
        });
    });

    // Collapsible sections
    document.querySelectorAll('[data-bs-toggle="collapse"]').forEach(button => {
        button.addEventListener('click', function() {
            const icon = this.querySelector('.fa') || this.querySelector('[class*="arrow"]');
            if (icon) {
                icon.style.transform = icon.style.transform === 'rotate(180deg)' ? 'rotate(0deg)' : 'rotate(180deg)';
            }
        });
    });

    // Parameter filtering
    const filterInput = document.getElementById('parameterFilter');
    if (filterInput) {
        filterInput.addEventListener('input', function() {
            const filter = this.value.toLowerCase();
            document.querySelectorAll('.parameter-item').forEach(item => {
                const name = item.querySelector('.parameter-name').textContent.toLowerCase();
                item.style.display = name.includes(filter) ? 'block' : 'none';
            });
        });
    }
            """

        return f"""
<script>
document.addEventListener('DOMContentLoaded', function() {{
{plot_script}
{interactive_script}
}});
</script>
        """

    def _generate_ga_report_content(self, analysis_results: Dict[str, Any], plots: Dict[str, Any]) -> str:
        """Generate content for genetic algorithm optimization reports."""
        best_result = analysis_results.get('best_result', {})
        summary_stats = analysis_results.get('summary_statistics', {})

        html = f"""
        <div class="row" id="summary">
            <div class="col-12">
                <div class="result-card">
                    <div class="result-card-header">
                        <h2 class="mb-0">🧬 Genetic Algorithm Optimization Summary</h2>
                    </div>
                    <div class="result-card-body">
                        <div class="row">
                            <div class="col-md-6">
                                <div class="stats-row">
                                    <span class="stats-label">Algorithm Status:</span>
                                    <span class="convergence-indicator {"converged" if summary_stats.get('convergence_status') == 'CONVERGED' else 'failed'}">
                                        {summary_stats.get('convergence_status', 'Unknown')}
                                    </span>
                                </div>
                                <div class="stats-row">
                                    <span class="stats-label">Total Evaluations:</span>
                                    <span class="stats-value">{summary_stats.get('total_evaluations', 0):,}</span>
                                </div>
                                <div class="stats-row">
                                    <span class="stats-label">Final Generation:</span>
                                    <span class="stats-value">{summary_stats.get('final_generation', 0)}</span>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="stats-row">
                                    <span class="stats-label">Pareto Front Size:</span>
                                    <span class="stats-value">{summary_stats.get('pareto_front_size', 1)}</span>
                                </div>
                                <div class="stats-row">
                                    <span class="stats-label">Best Fitness:</span>
                                    <span class="stats-value">{best_result.get('best_fitness', 'N/A')}</span>
                                </div>
                                <div class="stats-row">
                                    <span class="stats-label">Execution Time:</span>
                                    <span class="stats-value">{analysis_results.get('execution_time', 0):.2f}s</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="row mt-4" id="results">
            <div class="col-12">
                <div class="result-card">
                    <div class="result-card-header">
                        <h3 class="mb-0">🎯 Optimization Results</h3>
                    </div>
                    <div class="result-card-body">
        """

        # Best solution parameters
        if best_result.get('best_solution'):
            html += """
                        <h5>Best Solution Parameters:</h5>
                        <div class="parameter-grid">
            """
            for i, param_value in enumerate(best_result['best_solution']):
                html += f"""
                            <div class="parameter-item">
                                <div class="parameter-name">Parameter {i+1}</div>
                                <div class="parameter-value">{param_value:.6f}</div>
                            </div>
                """
            html += "</div>"

        # Objectives
        if best_result.get('best_objectives'):
            html += "<h5 class='mt-4'>Objective Values:</h5><div>"
            for i, obj_value in enumerate(best_result['best_objectives']):
                html += f'<span class="objective-badge">Objective {i+1}: {obj_value:.6f}</span>'
            html += "</div>"

        html += """
                    </div>
                </div>
            </div>
        </div>
        """

        # Plots section
        if plots:
            html += self._generate_interactive_plots_section(plots, 'genetic_algorithm')

        # Algorithm metadata
        metadata = best_result.get('algorithm_metadata', {})
        if metadata:
            html += f"""
            <div class="row mt-4" id="details">
                <div class="col-12">
                    <div class="result-card">
                        <div class="result-card-header">
                            <h3 class="mb-0">🔧 Algorithm Details</h3>
                        </div>
                        <div class="result-card-body">
                            {self._generate_table(metadata)}
                        </div>
                    </div>
                </div>
            </div>
            """

        return html

    def _generate_mc_report_content(self, analysis_results: Dict[str, Any], plots: Dict[str, Any]) -> str:
        """Generate content for Monte Carlo uncertainty analysis reports."""
        best_result = analysis_results.get('best_result', {})
        summary_stats = analysis_results.get('summary_statistics', {})
        uncertainty_analysis = best_result.get('uncertainty_analysis', {})

        html = f"""
        <div class="row" id="summary">
            <div class="col-12">
                <div class="result-card">
                    <div class="result-card-header">
                        <h2 class="mb-0">🎲 Monte Carlo Uncertainty Analysis</h2>
                    </div>
                    <div class="result-card-body">
                        <div class="row">
                            <div class="col-md-6">
                                <div class="stats-row">
                                    <span class="stats-label">Sampling Method:</span>
                                    <span class="stats-value">{summary_stats.get('sampling_method', 'Unknown').upper()}</span>
                                </div>
                                <div class="stats-row">
                                    <span class="stats-label">Total Samples:</span>
                                    <span class="stats-value">{summary_stats.get('total_samples', 0):,}</span>
                                </div>
                                <div class="stats-row">
                                    <span class="stats-label">Execution Time:</span>
                                    <span class="stats-value">{analysis_results.get('execution_time', 0):.2f}s</span>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="stats-row">
                                    <span class="stats-label">Best Sample Value:</span>
                                    <span class="stats-value">{best_result.get('best_fitness', 'N/A')}</span>
                                </div>
                                <div class="stats-row">
                                    <span class="stats-label">Analysis Status:</span>
                                    <span class="convergence-indicator converged">Completed</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        """

        # Statistics section
        statistics = uncertainty_analysis.get('statistics', {})
        if statistics:
            html += """
            <div class="row mt-4" id="statistics">
                <div class="col-12">
                    <div class="result-card">
                        <div class="result-card-header">
                            <h3 class="mb-0">📊 Statistical Summary</h3>
                        </div>
                        <div class="result-card-body">
                            <div class="row">
            """

            for obj_name, obj_stats in statistics.items():
                mean = obj_stats.get('mean', 0)
                std = obj_stats.get('std', 0)
                min_val = obj_stats.get('min', 0)
                max_val = obj_stats.get('max', 0)

                html += f"""
                                <div class="col-md-6">
                                    <h5>{obj_name.replace('_', ' ').title()}</h5>
                                    <div class="stats-row">
                                        <span class="stats-label">Mean:</span>
                                        <span class="stats-value">{mean:.4f}</span>
                                    </div>
                                    <div class="stats-row">
                                        <span class="stats-label">Std Dev:</span>
                                        <span class="stats-value">{std:.4f}</span>
                                    </div>
                                    <div class="stats-row">
                                        <span class="stats-label">Range:</span>
                                        <span class="stats-value">{min_val:.4f} - {max_val:.4f}</span>
                                    </div>
                                </div>
                """

            html += """
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            """

        # Risk analysis section
        risk_metrics = uncertainty_analysis.get('risk', {})
        if risk_metrics:
            html += """
            <div class="row mt-4" id="risk">
                <div class="col-12">
                    <div class="result-card">
                        <div class="result-card-header">
                            <h3 class="mb-0">⚠️ Risk Analysis</h3>
                        </div>
                        <div class="result-card-body">
            """

            for obj_name, risk_data in risk_metrics.items():
                var_95 = risk_data.get('var_95', 0)
                cvar_95 = risk_data.get('cvar_95', 0)
                prob_exceed_mean = risk_data.get('prob_exceed_mean', 0) * 100

                html += f"""
                            <h5>{obj_name.replace('_', ' ').title()}</h5>
                            <div class="row">
                                <div class="col-md-4">
                                    <div class="stats-row">
                                        <span class="stats-label">VaR (95%):</span>
                                        <span class="stats-value">{var_95:.4f}</span>
                                    </div>
                                </div>
                                <div class="col-md-4">
                                    <div class="stats-row">
                                        <span class="stats-label">CVaR (95%):</span>
                                        <span class="stats-value">{cvar_95:.4f}</span>
                                    </div>
                                </div>
                                <div class="col-md-4">
                                    <div class="stats-row">
                                        <span class="stats-label">Prob > Mean:</span>
                                        <span class="stats-value">{prob_exceed_mean:.1f}%</span>
                                    </div>
                                </div>
                            </div>
                """

            html += """
                        </div>
                    </div>
                </div>
            </div>
            """

        # Plots section
        if plots:
            html += self._generate_interactive_plots_section(plots, 'monte_carlo')

        return html

    def _generate_study_report_content(self, analysis_results: Dict[str, Any], plots: Dict[str, Any]) -> str:
        """Generate content for general study reports."""
        return f"""
        <div class="row" id="summary">
            <div class="col-12">
                <div class="result-card">
                    <div class="result-card-header">
                        <h2 class="mb-0">📋 Study Results Summary</h2>
                    </div>
                    <div class="result-card-body">
                        {self._generate_summary_section(analysis_results)}
                    </div>
                </div>
            </div>
        </div>

        <div class="row mt-4" id="results">
            <div class="col-12">
                {self._generate_plots_section(plots)}
            </div>
        </div>

        <div class="row mt-4" id="details">
            <div class="col-12">
                <div class="result-card">
                    <div class="result-card-header">
                        <h3 class="mb-0">📈 Detailed Analysis</h3>
                    </div>
                    <div class="result-card-body">
                        {self._generate_details_section(analysis_results)}
                    </div>
                </div>
            </div>
        </div>
        """

    def _generate_interactive_plots_section(self, plots: Dict[str, Any], report_type: str) -> str:
        """Generate interactive plots section with tabs."""
        if not plots:
            return ""

        # Create tab navigation
        tab_nav = '<ul class="nav nav-tabs" id="plotTabs" role="tablist">'
        tab_content = '<div class="tab-content" id="plotTabContent">'

        for i, (plot_id, plot_data) in enumerate(plots.items()):
            plot_title = plot_id.replace('_', ' ').title()
            active_class = 'active' if i == 0 else ''
            active_attr = 'true' if i == 0 else 'false'

            tab_nav += f"""
                <li class="nav-item" role="presentation">
                    <button class="nav-link {active_class}" id="{plot_id}-tab" data-bs-toggle="tab"
                            data-bs-target="#{plot_id}-pane" type="button" role="tab"
                            aria-controls="{plot_id}-pane" aria-selected="{active_attr}">
                        {plot_title}
                    </button>
                </li>
            """

            tab_content += f"""
                <div class="tab-pane fade {'show active' if i == 0 else ''}" id="{plot_id}-pane"
                     role="tabpanel" aria-labelledby="{plot_id}-tab">
                    <div class="plot mt-3">
                        <div id="{plot_id}"></div>
                    </div>
                </div>
            """

        tab_nav += '</ul>'
        tab_content += '</div>'

        return f"""
        <div class="row mt-4" id="analysis">
            <div class="col-12">
                <div class="result-card">
                    <div class="result-card-header">
                        <h3 class="mb-0">📊 Visualization & Analysis</h3>
                    </div>
                    <div class="result-card-body">
                        {tab_nav}
                        {tab_content}
                    </div>
                </div>
            </div>
        </div>
        """

    def generate_ga_optimization_report(self, study_result: Dict[str, Any], plots: Optional[Dict[str, Any]] = None) -> str:
        """Generate a genetic algorithm optimization report.

        Args:
            study_result: StudyResult from genetic algorithm optimization
            plots: Optional dictionary of plots

        Returns:
            Complete HTML report string
        """
        title = f"Genetic Algorithm Optimization: {study_result.get('study_id', 'GA Study')}"
        return self.generate_standalone_report(study_result, plots, title, 'genetic_algorithm')

    def generate_mc_uncertainty_report(self, study_result: Dict[str, Any], plots: Optional[Dict[str, Any]] = None) -> str:
        """Generate a Monte Carlo uncertainty analysis report.

        Args:
            study_result: StudyResult from Monte Carlo analysis
            plots: Optional dictionary of plots

        Returns:
            Complete HTML report string
        """
        title = f"Monte Carlo Uncertainty Analysis: {study_result.get('study_id', 'MC Study')}"
        return self.generate_standalone_report(study_result, plots, title, 'monte_carlo')

    def generate_study_comparison_report(self, study_results: List[Dict[str, Any]],
                                       plots: Optional[Dict[str, Any]] = None) -> str:
        """Generate a comparative study report.

        Args:
            study_results: List of StudyResult dictionaries
            plots: Optional dictionary of plots

        Returns:
            Complete HTML report string
        """
        # Aggregate results for comparison
        aggregated_results = {
            'study_type': 'comparison',
            'studies': study_results,
            'summary': self._create_comparison_summary(study_results)
        }

        return self.generate_standalone_report(aggregated_results, plots, 'Study Comparison Report', 'study')

    def _create_comparison_summary(self, study_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create summary statistics for study comparison."""
        total_studies = len(study_results)
        successful_studies = sum(1 for s in study_results if s.get('successful_simulations', 0) > 0)

        # Aggregate execution times
        total_execution_time = sum(s.get('execution_time', 0) for s in study_results)
        avg_execution_time = total_execution_time / total_studies if total_studies > 0 else 0

        return {
            'total_studies': total_studies,
            'successful_studies': successful_studies,
            'total_execution_time': total_execution_time,
            'avg_execution_time': avg_execution_time,
            'study_types': list(set(s.get('study_type', 'unknown') for s in study_results))
        }

    def save_report(self, html_content: str, output_path: Path) -> None:
        """Save HTML report to file.

        Args:
            html_content: Complete HTML content
            output_path: Path to save the report
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html_content, encoding='utf-8')


# Convenience function for backward compatibility
def create_standalone_html_report(
    analysis_results: Dict[str, Any],
    plots: Optional[Dict[str, Any]] = None,
    title: str = "EcoSystemiser Analysis Report"
) -> str:
    """Create a standalone HTML report (backward compatibility wrapper).

    Args:
        analysis_results: Analysis results dictionary
        plots: Optional dictionary of Plotly plots
        title: Report title

    Returns:
        Complete HTML string
    """
    generator = HTMLReportGenerator()
    return generator.generate_standalone_report(analysis_results, plots, title)