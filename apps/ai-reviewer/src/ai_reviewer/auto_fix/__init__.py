"""Auto-Fix Module for Guardian Agent

Provides autonomous error detection, fix generation, and retry management.

Components:
    - ErrorAnalyzer: Parse validation tool output (pytest, ruff, mypy)
    - FixGenerator: Generate targeted fixes using LLM
    - RetryManager: Apply fixes and manage retry attempts
    - EscalationLogic: Determine when to escalate to human review

Example:
    from ai_reviewer.auto_fix import ErrorAnalyzer, FixGenerator, RetryManager

    # Analyze errors
    analyzer = ErrorAnalyzer()
    errors = analyzer.parse_ruff_output(ruff_output)

    # Generate fixes
    generator = FixGenerator()
    fix = generator.generate_fix(errors[0], code_content)

    # Apply and retry
    manager = RetryManager(max_attempts=3)
    success = manager.apply_fix(file_path, fix)

"""

from .error_analyzer import ErrorAnalyzer, ErrorSeverity, ParsedError, ValidationTool
from .escalation import EscalationDecision, EscalationLogic, EscalationReason
from .fix_generator import FixGenerator, GeneratedFix
from .retry_manager import FixAttempt, FixSession, RetryManager

__all__ = [
    "ErrorAnalyzer",
    "ErrorSeverity",
    "EscalationDecision",
    "EscalationLogic",
    "EscalationReason",
    "FixAttempt",
    "FixGenerator",
    "FixSession",
    "GeneratedFix",
    "ParsedError",
    "RetryManager",
    "ValidationTool",
]
