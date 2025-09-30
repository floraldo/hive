from hive_logging import get_logger

logger = get_logger(__name__)

"""
EcoSystemiser Database Adapter,

This module provides database functionality by importing from ecosystemiser's
core database service, following the inherit→extend pattern.
"""

# Import from ecosystemiser core database service
from ecosystemiser.core.db import validate_ecosystemiser_database

# Legacy alias for compatibility
validate_hive_integration = validate_ecosystemiser_database
