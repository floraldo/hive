"""
EcoSystemiser database connection management.

This module provides database connection utilities by importing from
EcoSystemiser's core database service, maintaining proper architectural layering.
"""

# Import from ecosystemiser core database service
from ecosystemiser.core.db import (
    ecosystemiser_transaction,
    get_db_connection,
    get_ecosystemiser_connection,
    get_ecosystemiser_db_path,
)

# DEPRECATED: Custom ConnectionPool class removed
# EcoSystemiser uses its own dedicated database connection management.
# This provides proper resource management, connection validation, and thread safety.
#
# For new code, use:
# - get_ecosystemiser_connection() from ecosystemiser.db.hive_adapter
# - ecosystemiser_transaction() for transactional operations
#
# These functions provide context-managed connections for EcoSystemiser's
# dedicated database with proper cleanup and error handling.
