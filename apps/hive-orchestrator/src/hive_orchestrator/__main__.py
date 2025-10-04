# ruff: noqa: E402
from hive_logging import get_logger

logger = get_logger(__name__)

"""
Main entry point for the hive_orchestrator package.
Allows the package to be run with: python -m hive_orchestrator
"""

from .cli import cli

if __name__ == "__main__":
    cli()
