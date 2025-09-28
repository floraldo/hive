"""EcoSystemiser database module."""

# Primary imports - use Hive adapter for improved connection management
from .hive_adapter import (
    get_ecosystemiser_connection,
    ecosystemiser_transaction,
    get_ecosystemiser_db_path,
    validate_hive_integration
)

# Legacy imports for backward compatibility
from .connection import get_db_connection

# Schema management
from .schema import ensure_database_schema

__all__ = [
    # Recommended - use these for new code
    'get_ecosystemiser_connection',
    'ecosystemiser_transaction',
    'get_ecosystemiser_db_path',
    'validate_hive_integration',

    # Legacy - for backward compatibility
    'get_db_connection',

    # Schema management
    'ensure_database_schema'
]