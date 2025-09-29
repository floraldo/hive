from hive_logging import get_logger

logger = get_logger(__name__)

"""Common validation functions for CLI inputs."""

import json
from pathlib import Path
from typing import Any, Dict

import click
import yaml


def validate_path(ctx, param, value):
    """Validate that a path exists."""
    if value is None:
        return value

    path = Path(value)
    if not path.exists():
        raise click.BadParameter(f"Path does not exist: {path}")
    return path


def validate_config(config_path: Path) -> Dict[str, Any]:
    """Validate and load configuration file."""
    if not config_path.exists():
        raise click.BadParameter(f"Configuration file not found: {config_path}")

    try:
        if config_path.suffix.lower() in [".yaml", ".yml"]:
            with open(config_path, "r") as f:
                return yaml.safe_load(f)
        elif config_path.suffix.lower() == ".json":
            with open(config_path, "r") as f:
                return json.load(f)
        else:
            raise click.BadParameter(f"Unsupported config format: {config_path.suffix}")
    except Exception as e:
        raise click.BadParameter(f"Failed to load config: {e}")


def validate_output_dir(ctx, param, value):
    """Validate output directory and create if needed."""
    if value is None:
        return value

    path = Path(value)
    if path.exists() and not path.is_dir():
        raise click.BadParameter(f"Output path exists but is not a directory: {path}")

    # Create directory if it doesn't exist
    path.mkdir(parents=True, exist_ok=True)
    return path


def validate_positive_int(ctx, param, value):
    """Validate that value is a positive integer."""
    if value is None:
        return value

    if value <= 0:
        raise click.BadParameter(f"Value must be positive: {value}")
    return value
