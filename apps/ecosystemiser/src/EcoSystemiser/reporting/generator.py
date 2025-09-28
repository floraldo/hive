"""Centralized HTML report generation for EcoSystemiser.

This module provides a unified approach to generating HTML reports,
eliminating code duplication between CLI and web interfaces.
"""

import json
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime


class HTMLReportGenerator:
    """Generate HTML reports from analysis results with consistent formatting."""

    def __init__(self):
        """Initialize the report generator."""
        self.plotly_cdn = "https://cdn.plot.ly/plotly-latest.min.js"

    def generate_standalone_report(
        self,
        analysis_results: Dict[str, Any],
        plots: Optional[Dict[str, Any]] = None,
        title: str = "EcoSystemiser Analysis Report"
    ) -> str:
        """Generate a complete standalone HTML report.

        Args:
            analysis_results: Analysis results dictionary
            plots: Optional dictionary of Plotly plots
            title: Report title

        Returns:
            Complete HTML string
        """
        # Build HTML sections
        head_html = self._generate_head(title)
        summary_html = self._generate_summary_section(analysis_results)
        plots_html = self._generate_plots_section(plots or {})
        details_html = self._generate_details_section(analysis_results)
        scripts_html = self._generate_scripts(plots or {})

        # Assemble complete HTML
        html = f"""
<!DOCTYPE html>
<html>
{head_html}
<body>
    <div class="container">
        <h1>{title}</h1>
        <div class="timestamp">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>

        {summary_html}
        {plots_html}
        {details_html}
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

    def _generate_head(self, title: str) -> str:
        """Generate HTML head section with styles and dependencies."""
        return f"""
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="{self.plotly_cdn}"></script>
    {self._generate_styles()}
</head>
        """

    def _generate_styles(self) -> str:
        """Generate CSS styles for the report."""
        return """
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

    def _generate_scripts(self, plots: Dict[str, Any]) -> str:
        """Generate JavaScript for rendering plots."""
        if not plots:
            return ""

        return f"""
<script>
document.addEventListener('DOMContentLoaded', function() {{
    const plots = {json.dumps(plots)};

    Object.keys(plots).forEach(plotId => {{
        const element = document.getElementById(plotId);
        if (element && plots[plotId]) {{
            // Default layout options
            const layout = {{
                autosize: true,
                margin: {{l: 50, r: 50, t: 50, b: 50}},
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                ...plots[plotId].layout
            }};

            // Default config options
            const config = {{
                responsive: true,
                displayModeBar: true,
                displaylogo: false,
                modeBarButtonsToRemove: ['sendDataToCloud']
            }};

            Plotly.newPlot(plotId, plots[plotId].data || plots[plotId], layout, config);
        }}
    }});
}});
</script>
        """

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