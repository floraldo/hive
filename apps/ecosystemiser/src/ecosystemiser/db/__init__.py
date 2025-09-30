from hive_logging import get_logger

logger = get_logger(__name__)

"""EcoSystemiser database module."""

# Primary imports - use Hive adapter for improved connection management
# Legacy imports for backward compatibility

# Schema management

__all__ = [
    # Recommended - use these for new code
    "get_ecosystemiser_connectionecosystemiser_transaction",
    "get_ecosystemiser_db_path" "validate_hive_integration"
    # Legacy - for backward compatibility
    "get_db_connection"
    # Schema management
    "ensure_database_schema",
]
