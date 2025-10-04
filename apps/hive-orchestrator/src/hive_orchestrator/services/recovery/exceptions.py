"""
Recovery Service Exceptions

PROJECT CHIMERA Phase 3: Self-Healing Feedback Loop
Custom exceptions for automated recovery operations.
"""

from __future__ import annotations


class RecoveryError(Exception):
    """Base exception for recovery operations."""

    pass


class PlaybookNotFoundError(RecoveryError):
    """Raised when requested playbook doesn't exist."""

    pass


class PlaybookExecutionError(RecoveryError):
    """Raised when playbook execution fails."""

    pass


class SafetyCheckFailedError(RecoveryError):
    """Raised when safety checks prevent automation."""

    pass


class InsufficientConfidenceError(SafetyCheckFailedError):
    """Raised when alert confidence is below threshold."""

    pass


class AmbiguousRootCauseError(SafetyCheckFailedError):
    """Raised when root cause is not clear from historical context."""

    pass


class RecentFailureError(SafetyCheckFailedError):
    """Raised when same issue recently failed automated recovery."""

    pass


class ManualModeError(SafetyCheckFailedError):
    """Raised when service is in manual-only mode."""

    pass


__all__ = [
    "RecoveryError",
    "PlaybookNotFoundError",
    "PlaybookExecutionError",
    "SafetyCheckFailedError",
    "InsufficientConfidenceError",
    "AmbiguousRootCauseError",
    "RecentFailureError",
    "ManualModeError",
]
