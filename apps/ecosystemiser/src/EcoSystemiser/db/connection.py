"""
EcoSystemiser database connection management.

This module provides database connection utilities by importing from
EcoSystemiser's core database service, maintaining proper architectural layering.
"""

# Import from EcoSystemiser core database service
from EcoSystemiser.core.db import (
    get_ecosystemiser_db_path,
    get_db_connection,
    ecosystemiser_transaction,
    get_ecosystemiser_connection
)


# DEPRECATED: Custom ConnectionPool class removed
# EcoSystemiser uses its own dedicated database connection management.
# This provides proper resource management, connection validation, and thread safety.
#
# For new code, use:
# - get_ecosystemiser_connection() from EcoSystemiser.db.hive_adapter
# - ecosystemiser_transaction() for transactional operations
#
# These functions provide context-managed connections for EcoSystemiser's
# dedicated database with proper cleanup and error handling.