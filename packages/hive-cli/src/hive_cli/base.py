"""Base CLI classes for Hive applications."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from hive_errors import BaseError
from hive_logging import get_logger


class HiveError(BaseError):
    """Base error for Hive CLI operations."""



class HiveCommand(click.Command):
    """Base command class with Hive-specific functionality."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.logger = get_logger(self.name or __name__)

    def invoke(self, ctx):
        """Override invoke to add standard error handling."""
        try:
            return super().invoke(ctx)
        except BaseError as e:
            self.logger.error(f"Hive error: {e}")
            ctx.exit(1)
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            if ctx.obj and ctx.obj.get("debug"):
                raise
            ctx.exit(1)


class HiveGroup(click.Group):
    """Base group class with Hive-specific functionality."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.logger = get_logger(self.name or __name__)

    def command(self, *args, **kwargs):
        """Create a command using HiveCommand by default."""
        kwargs.setdefault("cls", HiveCommand)
        return super().command(*args, **kwargs)

    def group(self, *args, **kwargs):
        """Create a subgroup using HiveGroup by default."""
        kwargs.setdefault("cls", HiveGroup)
        return super().group(*args, **kwargs)


class HiveContext:
    """Shared context for Hive CLI commands."""

    def __init__(self) -> None:
        self.config: dict[str, Any] | None = None
        self.debug: bool = False
        self.verbose: bool = False
        self.config_path: Path | None = None

    def load_config(self, config_path: Path | None = None) -> None:
        """Load configuration from file."""
        if config_path:
            self.config_path = config_path
            # Implementation would load from config file
            # This is a placeholder for the pattern


def create_cli():
    """Create a Hive CLI group with standard configuration.

    Returns:
        Callable that creates a click.Group with HiveGroup class

    """
    def decorator(f):
        return click.group(cls=HiveGroup)(f)
    return decorator
