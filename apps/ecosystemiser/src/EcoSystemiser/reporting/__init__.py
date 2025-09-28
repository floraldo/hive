"""Reporting Module - Flask web application for dynamic report generation.

This module provides a web-based interface for generating and viewing
analysis reports from EcoSystemiser simulation results. It integrates
with the Analyser and DataVis modules to provide comprehensive reporting.
"""

from EcoSystemiser.reporting.app import create_app
from EcoSystemiser.reporting.generator import HTMLReportGenerator, create_standalone_html_report

__all__ = [
    'create_app',
    'HTMLReportGenerator',
    'create_standalone_html_report'
]