from __future__ import annotations

from hive_logging import get_logger

logger = get_logger(__name__)

"""Output formatting utilities for CLI commands."""

import json
from typing import Any, Dict, List

import click
import yaml
from rich.console import Console
from rich.table import Table


class HiveOutput:
    """Unified output formatter for Hive CLI commands."""

    def __init__(self, format_type: str = "table") -> None:
        self.format_type = format_type
        self.console = Console()

    def output(self, data: Any, title: str | None = None) -> None:
        """Output data in the specified format."""
        if self.format_type == "json":
            self.output_json(data)
        elif self.format_type == "yaml":
            self.output_yaml(data)
        elif self.format_type == "table":
            self.output_table(data, title)
        else:
            self.output_text(data)

    def output_json(self, data: Any) -> None:
        """Output data as JSON."""
        click.echo(json.dumps(data, indent=2, default=str))

    def output_yaml(self, data: Any) -> None:
        """Output data as YAML."""
        click.echo(yaml.dump(data, default_flow_style=False))

    def output_table(self, data: Any, title: str | None = None) -> None:
        """Output data as a formatted table."""
        if isinstance(data, list) and data and isinstance(data[0], dict):
            table = self._create_table_from_dicts(data, title)
            self.console.logger.info(table)
        elif isinstance(data, dict):
            table = self._create_table_from_dict(data, title)
            self.console.logger.info(table)
        else:
            # Fallback to pretty print
            plogger.info(data, console=self.console)

    def output_text(self, data: Any) -> None:
        """Output data as formatted text."""
        if isinstance(data, (dict, list)):
            plogger.info(data, console=self.console)
        else:
            click.echo(str(data))

    def _create_table_from_dicts(self, data: List[Dict], title: str | None = None) -> Table:
        """Create a Rich table from a list of dictionaries."""
        table = Table(title=title)

        # Add columns based on first item keys
        for key in data[0].keys():
            table.add_column(str(key).replace("_", " ").title())

        # Add rows
        for item in data:
            table.add_row(*[str(item.get(key, "")) for key in data[0].keys()])

        return table

    def _create_table_from_dict(self, data: Dict, title: str | None = None) -> Table:
        """Create a Rich table from a dictionary."""
        table = Table(title=title)
        table.add_column("Key")
        table.add_column("Value")

        for key, value in data.items():
            table.add_row(str(key), str(value))

        return table


def format_table(data: Any, title: str | None = None) -> str:
    """Format data as a table (legacy function)."""
    output = HiveOutput("table")
    output.output_table(data, title)
    return ""  # Rich handles printing directly


def format_json(data: Any) -> str:
    """Format data as JSON."""
    return json.dumps(data, indent=2, default=str)


def format_yaml(data: Any) -> str:
    """Format data as YAML."""
    return yaml.dump(data, default_flow_style=False)
