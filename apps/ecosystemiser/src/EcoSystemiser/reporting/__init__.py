"""Reporting Module - Flask web application for dynamic report generation.

This module provides a web-based interface for generating and viewing
analysis reports from EcoSystemiser simulation results. It integrates
with the Analyser and DataVis modules to provide comprehensive reporting.
"""

from .app import create_app, run_server

__all__ = [
    'create_app',
    'run_server'
]