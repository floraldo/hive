from hive_logging import get_logger

logger = get_logger(__name__)

"""Reporting Module - Flask web application for dynamic report generation.,

This module provides a web-based interface for generating and viewing
analysis reports from ecosystemiser simulation results. It integrates
with the Analyser and DataVis modules to provide comprehensive reporting.
"""

from ecosystemiser.reporting.app import create_app
from ecosystemiser.reporting.generator import HTMLReportGenerator, create_standalone_html_report

__all__ = ["HTMLReportGenerator", "create_app", "create_standalone_html_report"]
