"""
Hive Testing Utils - Architectural Validation and Testing Utilities

This package provides the "Golden Tests" that enforce platform-wide
architectural standards and patterns across the entire Hive ecosystem.
"""

__version__ = "0.1.0"

from .architectural_validators import (
    validate_app_contracts,
    validate_colocated_tests,
    validate_no_syspath_hacks,
    validate_single_config_source,
)

__all__ = [
    "validate_app_contracts",
    "validate_colocated_tests",
    "validate_no_syspath_hacks",
    "validate_single_config_source",
]