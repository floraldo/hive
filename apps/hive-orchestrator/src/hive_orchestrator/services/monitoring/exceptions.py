"""
Monitoring Service Exceptions

Service-specific exceptions for monitoring operations.
"""

from __future__ import annotations


class MonitoringServiceError(Exception):
    """Base exception for monitoring service errors"""


class MonitoringConfigurationError(MonitoringServiceError):
    """Raised when monitoring service is misconfigured"""


class MonitoringDataError(MonitoringServiceError):
    """Raised when monitoring data is invalid or unavailable"""


class AnalysisError(MonitoringServiceError):
    """Raised when predictive analysis fails"""
