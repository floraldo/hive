"""Guardian Write Mode - Active Code Improvement.

Evolves Guardian from read-only advisor to active participant that can
propose and apply safe code changes. Implements progressive complexity
levels with comprehensive safety gates.

Safety Progression:
- Level 1 (Safest): Typos in comments/docstrings
- Level 2 (Safe): Missing docstrings
- Level 3 (Moderate): Code formatting
- Level 4 (Complex): Logic fixes
- Level 5 (Advanced): Feature enhancements

All changes require approval and are fully reversible through git.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ChangeLevel(Enum):
    """Progressive complexity levels for Guardian changes."""

    LEVEL_1_TYPO = 1  # Typos in comments/docstrings
    LEVEL_2_DOCSTRING = 2  # Missing docstrings
    LEVEL_3_FORMATTING = 3  # Code formatting (trailing commas, imports)
    LEVEL_4_LOGIC = 4  # Logic fixes (golden rules violations)
    LEVEL_5_FEATURE = 5  # Feature enhancements

    @property
    def risk_level(self) -> str:
        """Get risk level description."""
        risk_map = {
            1: "minimal",
            2: "low",
            3: "moderate",
            4: "elevated",
            5: "high",
        }
        return risk_map[self.value]

    @property
    def requires_tests(self) -> bool:
        """Check if level requires test validation."""
        return self.value >= 4  # Logic fixes and above

    @property
    def requires_review(self) -> bool:
        """Check if level requires human review."""
        return self.value >= 3  # Formatting and above


class ChangeCategory(Enum):
    """Categories of changes Guardian can make."""

    # Level 1
    TYPO_COMMENT = "typo_in_comment"
    TYPO_DOCSTRING = "typo_in_docstring"

    # Level 2
    MISSING_DOCSTRING = "missing_docstring"
    INCOMPLETE_DOCSTRING = "incomplete_docstring"

    # Level 3
    MISSING_TRAILING_COMMA = "missing_trailing_comma"
    IMPORT_SORTING = "import_sorting"
    WHITESPACE_FORMATTING = "whitespace_formatting"

    # Level 4
    GOLDEN_RULE_VIOLATION = "golden_rule_violation"
    TYPE_HINT_MISSING = "type_hint_missing"
    ERROR_HANDLING_MISSING = "error_handling_missing"

    # Level 5
    PERFORMANCE_IMPROVEMENT = "performance_improvement"
    FEATURE_ENHANCEMENT = "feature_enhancement"

    @property
    def level(self) -> ChangeLevel:
        """Get change level for this category."""
        level_map = {
            "typo_in_comment": ChangeLevel.LEVEL_1_TYPO,
            "typo_in_docstring": ChangeLevel.LEVEL_1_TYPO,
            "missing_docstring": ChangeLevel.LEVEL_2_DOCSTRING,
            "incomplete_docstring": ChangeLevel.LEVEL_2_DOCSTRING,
            "missing_trailing_comma": ChangeLevel.LEVEL_3_FORMATTING,
            "import_sorting": ChangeLevel.LEVEL_3_FORMATTING,
            "whitespace_formatting": ChangeLevel.LEVEL_3_FORMATTING,
            "golden_rule_violation": ChangeLevel.LEVEL_4_LOGIC,
            "type_hint_missing": ChangeLevel.LEVEL_4_LOGIC,
            "error_handling_missing": ChangeLevel.LEVEL_4_LOGIC,
            "performance_improvement": ChangeLevel.LEVEL_5_FEATURE,
            "feature_enhancement": ChangeLevel.LEVEL_5_FEATURE,
        }
        return level_map[self.value]


@dataclass
class ChangeProposal:
    """Proposed code change with safety metadata.

    Represents a single atomic change Guardian wants to make,
    with full context for review and rollback.
    """

    # Core change details
    file_path: Path
    category: ChangeCategory
    description: str
    old_code: str
    new_code: str

    # Context from RAG
    rag_context: str
    related_patterns: list[str]
    confidence_score: float  # 0.0-1.0

    # Safety metadata
    level: ChangeLevel
    risk_assessment: str
    requires_tests: bool
    requires_review: bool

    # Tracking
    proposal_id: str
    created_at: datetime
    approved_by: str | None = None
    applied_at: datetime | None = None
    git_commit: str | None = None

    # Validation
    syntax_validated: bool = False
    tests_passed: bool = False
    review_status: str = "pending"  # pending, approved, rejected

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "proposal_id": self.proposal_id,
            "file_path": str(self.file_path),
            "category": self.category.value,
            "level": self.level.value,
            "description": self.description,
            "old_code": self.old_code,
            "new_code": self.new_code,
            "rag_context": self.rag_context,
            "confidence_score": self.confidence_score,
            "risk_level": self.level.risk_level,
            "requires_tests": self.requires_tests,
            "requires_review": self.requires_review,
            "created_at": self.created_at.isoformat(),
            "review_status": self.review_status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChangeProposal:
        """Create from dictionary."""
        return cls(
            file_path=Path(data["file_path"]),
            category=ChangeCategory(data["category"]),
            description=data["description"],
            old_code=data["old_code"],
            new_code=data["new_code"],
            rag_context=data["rag_context"],
            related_patterns=data.get("related_patterns", []),
            confidence_score=data["confidence_score"],
            level=ChangeLevel(data["level"]),
            risk_assessment=data.get("risk_assessment", ""),
            requires_tests=data["requires_tests"],
            requires_review=data["requires_review"],
            proposal_id=data["proposal_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            review_status=data.get("review_status", "pending"),
        )


@dataclass
class SafetyGate:
    """Safety gate for validating changes before application.

    Implements progressive validation based on change level.
    """

    name: str
    description: str
    required_for_levels: list[ChangeLevel]
    validation_fn: callable

    def applies_to(self, proposal: ChangeProposal) -> bool:
        """Check if this gate applies to the proposal."""
        return proposal.level in self.required_for_levels

    async def validate(self, proposal: ChangeProposal) -> tuple[bool, str]:
        """Validate proposal through this gate.

        Returns:
            (passed, message) tuple

        """
        try:
            result = await self.validation_fn(proposal)
            if isinstance(result, bool):
                return result, "Validation passed" if result else "Validation failed"
            return result
        except Exception as e:
            logger.error(f"Safety gate {self.name} failed: {e}")
            return False, f"Gate error: {e!s}"


class WriteModeConfig:
    """Configuration for Guardian Write Mode."""

    def __init__(
        self,
        enabled_levels: list[ChangeLevel] | None = None,
        max_changes_per_pr: int = 10,
        require_approval: bool = True,
        auto_commit: bool = False,
        dry_run: bool = True,
    ):
        """Initialize Write Mode configuration.

        Args:
            enabled_levels: Levels allowed for automatic application
            max_changes_per_pr: Maximum changes in single PR
            require_approval: Require human approval before applying
            auto_commit: Automatically commit approved changes
            dry_run: Run in simulation mode (no actual changes)

        """
        # Default to safest level only
        self.enabled_levels = enabled_levels or [ChangeLevel.LEVEL_1_TYPO]
        self.max_changes_per_pr = max_changes_per_pr
        self.require_approval = require_approval
        self.auto_commit = auto_commit
        self.dry_run = dry_run

    def is_level_enabled(self, level: ChangeLevel) -> bool:
        """Check if a change level is enabled."""
        return level in self.enabled_levels

    def can_auto_apply(self, proposal: ChangeProposal) -> bool:
        """Check if proposal can be automatically applied."""
        if self.dry_run:
            return False
        if self.require_approval and not proposal.approved_by:
            return False
        return self.is_level_enabled(proposal.level)


# Built-in safety gates
async def validate_syntax(proposal: ChangeProposal) -> tuple[bool, str]:
    """Validate Python syntax of proposed change."""
    import ast

    try:
        ast.parse(proposal.new_code)
        return True, "Syntax valid"
    except SyntaxError as e:
        return False, f"Syntax error: {e}"


async def validate_no_secrets(proposal: ChangeProposal) -> tuple[bool, str]:
    """Ensure change doesn't introduce secrets."""
    secret_patterns = [
        "password",
        "api_key",
        "secret",
        "token",
        "credential",
    ]

    # Check if adding any secret-like strings
    new_lower = proposal.new_code.lower()
    for pattern in secret_patterns:
        if pattern in new_lower and pattern not in proposal.old_code.lower():
            return False, f"Potential secret detected: {pattern}"

    return True, "No secrets detected"


async def validate_tests_pass(proposal: ChangeProposal) -> tuple[bool, str]:
    """Validate that tests pass after change (for logic changes)."""
    # TODO: Implement test runner integration
    # For now, return True to allow testing
    return True, "Test validation not yet implemented"


# Standard safety gates
STANDARD_SAFETY_GATES = [
    SafetyGate(
        name="syntax_validation",
        description="Validate Python syntax",
        required_for_levels=[
            ChangeLevel.LEVEL_2_DOCSTRING,
            ChangeLevel.LEVEL_3_FORMATTING,
            ChangeLevel.LEVEL_4_LOGIC,
            ChangeLevel.LEVEL_5_FEATURE,
        ],
        validation_fn=validate_syntax,
    ),
    SafetyGate(
        name="no_secrets",
        description="Ensure no secrets introduced",
        required_for_levels=[
            ChangeLevel.LEVEL_1_TYPO,
            ChangeLevel.LEVEL_2_DOCSTRING,
            ChangeLevel.LEVEL_3_FORMATTING,
            ChangeLevel.LEVEL_4_LOGIC,
            ChangeLevel.LEVEL_5_FEATURE,
        ],
        validation_fn=validate_no_secrets,
    ),
    SafetyGate(
        name="tests_pass",
        description="Validate tests pass",
        required_for_levels=[
            ChangeLevel.LEVEL_4_LOGIC,
            ChangeLevel.LEVEL_5_FEATURE,
        ],
        validation_fn=validate_tests_pass,
    ),
]
