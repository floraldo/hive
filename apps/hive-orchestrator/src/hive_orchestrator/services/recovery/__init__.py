"""Automated Recovery Service

PROJECT CHIMERA Phase 3: Self-Healing Feedback Loop
Autonomous recovery system for predictive alerts.
"""

from .audit import RecoveryAuditLogger
from .decision_engine import AutomationDecision, AutomationDecisionEngine
from .exceptions import (
    AmbiguousRootCauseError,
    InsufficientConfidenceError,
    ManualModeError,
    PlaybookExecutionError,
    PlaybookNotFoundError,
    RecentFailureError,
    RecoveryError,
    SafetyCheckFailedError,
)
from .playbook_registry import RecoveryPlaybookRegistry
from .playbooks import ClearCachePlaybook, RecoveryPlaybook, RestartServicePlaybook, ScalePoolPlaybook
from .recovery_service import AutomatedRecoveryService

__all__ = [
    "AmbiguousRootCauseError",
    "AutomatedRecoveryService",
    "AutomationDecision",
    "AutomationDecisionEngine",
    "ClearCachePlaybook",
    "InsufficientConfidenceError",
    "ManualModeError",
    "PlaybookExecutionError",
    "PlaybookNotFoundError",
    "RecentFailureError",
    "RecoveryAuditLogger",
    "RecoveryError",
    "RecoveryPlaybook",
    "RecoveryPlaybookRegistry",
    "RestartServicePlaybook",
    "SafetyCheckFailedError",
    "ScalePoolPlaybook",
]
