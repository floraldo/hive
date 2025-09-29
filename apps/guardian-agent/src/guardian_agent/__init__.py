"""
Hive Guardian Agent - AI-powered code review automation.

This package provides intelligent code review capabilities leveraging
the Hive platform's AI infrastructure.
"""

from guardian_agent.core.config import GuardianConfig
from guardian_agent.core.interfaces import ReviewResult, Violation
from guardian_agent.review.engine import ReviewEngine

__version__ = "0.1.0"

__all__ = [
    "GuardianConfig",
    "ReviewEngine",
    "ReviewResult",
    "Violation",
]