from hive_logging import get_logger

logger = get_logger(__name__)

"""Common CLI decorators for Hive applications."""

from collections.abc import Callable
from functools import wraps
from pathlib import Path

import click


def config_option(f: Callable) -> Callable:
    """Add standard config file option."""
    return click.option("--config", "-c", type=click.Path(exists=True, path_type=Path), help="Configuration file path")(
        f,
    )


def debug_option(f: Callable) -> Callable:
    """Add standard debug option."""
    return click.option("--debug", is_flag=True, help="Enable debug mode")(f)


def verbose_option(f: Callable) -> Callable:
    """Add standard verbose option."""
    return click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")(f)


def output_format_option(f: Callable) -> Callable:
    """Add output format option."""
    return click.option(
        "--output",
        "-o",
        type=click.Choice(["json", "yaml", "table", "text"]),
        default="table",
        help="Output format",
    )(f)


def common_options(f: Callable) -> Callable:
    """Apply common CLI options to a command."""
    f = debug_option(f)
    f = verbose_option(f)
    f = config_option(f)
    f = output_format_option(f)

    @wraps(f)
    def wrapper(*args, **kwargs) -> None:
        # Set up context based on common options
        ctx = click.get_current_context()
        if not ctx.obj:
            from .base import HiveContext

            ctx.obj = HiveContext()

        # Configure context from options
        ctx.obj.debug = kwargs.get("debug", False)
        ctx.obj.verbose = kwargs.get("verbose", False)

        if kwargs.get("config"):
            ctx.obj.load_config(kwargs["config"])

        return f(*args, **kwargs)

    return wrapper


def require_config(f: Callable) -> Callable:
    """Require configuration to be loaded."""

    @wraps(f)
    def wrapper(*args, **kwargs):
        ctx = click.get_current_context()
        if not ctx.obj or not ctx.obj.config:
            raise click.ClickException("Configuration required. Use --config to specify config file.")
        return f(*args, **kwargs)

    return wrapper
