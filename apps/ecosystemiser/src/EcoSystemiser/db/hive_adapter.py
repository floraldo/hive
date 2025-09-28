"""
EcoSystemiser Database Adapter

This module provides database functionality by importing from ecosystemiser's
core database service, following the inherit→extend pattern.
"""

# Import from ecosystemiser core database service
from ecosystemiser.core.db import (
    get_ecosystemiser_db_path,
    get_ecosystemiser_connection,
    ecosystemiser_transaction,
    get_db_connection,
    validate_ecosystemiser_database
)

# Legacy alias for compatibility
validate_hive_integration = validate_ecosystemiser_database