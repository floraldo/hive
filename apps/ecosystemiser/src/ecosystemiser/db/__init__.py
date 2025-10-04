"""EcoSystemiser database module."""

# Import from core.db module
from ecosystemiser.core.db import (
    ecosystemiser_transaction,
    get_db_connection,
    get_ecosystemiser_connection,
    get_ecosystemiser_db_path,
    validate_ecosystemiser_database,
)
from hive_logging import get_logger

# Import from schema module
from .schema import ensure_database_schema

logger = get_logger(__name__)

# Alias for consistency
validate_hive_integration = validate_ecosystemiser_database

__all__ = [
    # Recommended - use these for new code
    "get_ecosystemiser_connection",
    "ecosystemiser_transaction",
    "get_ecosystemiser_db_path",
    "validate_hive_integration",
    # Legacy - for backward compatibility
    "get_db_connection",
    # Schema management
    "ensure_database_schema",
]
