from hive_logging import get_logger

logger = get_logger(__name__)

"""EcoSystemiser database module."""

# Primary imports - use Hive adapter for improved connection management
# Legacy imports for backward compatibility
from .connection import get_db_connection
from .hive_adapter import (
    ecosystemiser_transaction,
    get_ecosystemiser_connection,
    get_ecosystemiser_db_path,
    validate_hive_integration,
)

# Schema management
from .schema import ensure_database_schema

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
