"""Recovery Service Exceptions

PROJECT CHIMERA Phase 3: Self-Healing Feedback Loop
Custom exceptions for automated recovery operations.
"""

from __future__ import annotations


class RecoveryError(Exception):
    """Base exception for recovery operations."""



class PlaybookNotFoundError(RecoveryError):
    """Raised when requested playbook doesn't exist."""



class PlaybookExecutionError(RecoveryError):
    """Raised when playbook execution fails."""



class SafetyCheckFailedError(RecoveryError):
    """Raised when safety checks prevent automation."""



class InsufficientConfidenceError(SafetyCheckFailedError):
    """Raised when alert confidence is below threshold."""



class AmbiguousRootCauseError(SafetyCheckFailedError):
    """Raised when root cause is not clear from historical context."""



class RecentFailureError(SafetyCheckFailedError):
    """Raised when same issue recently failed automated recovery."""



class ManualModeError(SafetyCheckFailedError):
    """Raised when service is in manual-only mode."""



__all__ = [
    "AmbiguousRootCauseError",
    "InsufficientConfidenceError",
    "ManualModeError",
    "PlaybookExecutionError",
    "PlaybookNotFoundError",
    "RecentFailureError",
    "RecoveryError",
    "SafetyCheckFailedError",
]
