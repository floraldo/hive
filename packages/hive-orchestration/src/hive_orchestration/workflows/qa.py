"""QA Workflow - Chimera Pattern for Quality Automation.

Defines the QA workflow state machine for autonomous quality enforcement via Chimera agents.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class QAPhase(str, Enum):
    """QA workflow phases."""

    DETECT = "detect_violations"
    FIX = "apply_fixes"
    VALIDATE = "validate_fixes"
    COMMIT = "commit_changes"
    COMPLETE = "complete"
    FAILED = "failed"


class QAWorkflow(BaseModel):
    """QA workflow definition for Chimera execution.

    State machine for autonomous quality enforcement:
    1. DETECT: Detect violations (Ruff, Golden Rules, tests)
    2. FIX: Apply auto-fixes using RAG patterns
    3. VALIDATE: Run validation to ensure fixes work
    4. COMMIT: Commit fixes with worker ID reference
    5. COMPLETE: Workflow success
    6. FAILED: Workflow failure (escalate to HITL)

    Example:
        workflow = QAWorkflow(
            violations=[{"type": "E501", "file": "auth.py"}],
            rag_context=[{"fix_pattern": "use black --line-length 120"}]
        )
    """

    # Workflow metadata
    workflow_type: str = Field(default="qa_workflow", description="Workflow type identifier")
    current_phase: QAPhase = Field(default=QAPhase.DETECT, description="Current phase")

    # Input data
    violations: list[dict[str, Any]] = Field(default_factory=list, description="Violations to fix")
    rag_context: list[dict[str, Any]] = Field(default_factory=list, description="RAG patterns for fixes")

    # Execution parameters
    qa_type: str = Field(default="ruff", description="Type of QA check (ruff, golden_rules, test, security)")
    scope: str = Field(default=".", description="File/directory scope for QA")
    severity_level: str = Field(default="ERROR", description="Severity level (CRITICAL, ERROR, WARNING, INFO)")

    # Phase results
    detection_result: dict[str, Any] | None = Field(default=None, description="Violation detection result")
    fix_result: dict[str, Any] | None = Field(default=None, description="Auto-fix result")
    validation_result: dict[str, Any] | None = Field(default=None, description="Fix validation result")
    commit_result: dict[str, Any] | None = Field(default=None, description="Git commit result")

    # Error handling
    error_message: str | None = Field(default=None, description="Error message if workflow fails")
    escalated: bool = Field(default=False, description="Whether workflow was escalated to HITL")

    def is_terminal(self) -> bool:
        """Check if workflow is in terminal state."""
        return self.current_phase in (QAPhase.COMPLETE, QAPhase.FAILED)

    def transition_to(self, next_phase: QAPhase, result: dict[str, Any]) -> None:
        """Transition to next phase with result.

        Args:
            next_phase: Next phase to transition to
            result: Result from current phase execution
        """
        # Store phase result
        if self.current_phase == QAPhase.DETECT:
            self.detection_result = result
        elif self.current_phase == QAPhase.FIX:
            self.fix_result = result
        elif self.current_phase == QAPhase.VALIDATE:
            self.validation_result = result
        elif self.current_phase == QAPhase.COMMIT:
            self.commit_result = result

        # Transition to next phase
        self.current_phase = next_phase

        # Handle failure
        if next_phase == QAPhase.FAILED:
            self.error_message = result.get("error", "Unknown error")

    def get_state_machine(self) -> dict[str, Any]:
        """Get workflow state machine definition.

        Returns:
            State machine dictionary for Chimera executor
        """
        return {
            "states": {
                QAPhase.DETECT: {
                    "agent": "qa-detector-agent",
                    "action": "detect_violations",
                    "params": {
                        "qa_type": self.qa_type,
                        "scope": self.scope,
                        "severity_level": self.severity_level,
                    },
                    "timeout": 60,
                    "on_success": QAPhase.FIX.value,
                    "on_failure": QAPhase.FAILED.value,
                },
                QAPhase.FIX: {
                    "agent": "qa-fixer-agent",
                    "action": "apply_fixes",
                    "params": {
                        "violations": self.violations,
                        "rag_context": self.rag_context,
                    },
                    "timeout": 120,
                    "on_success": QAPhase.VALIDATE.value,
                    "on_failure": QAPhase.FAILED.value,
                },
                QAPhase.VALIDATE: {
                    "agent": "qa-validator-agent",
                    "action": "validate_fixes",
                    "params": {
                        "qa_type": self.qa_type,
                        "scope": self.scope,
                    },
                    "timeout": 60,
                    "on_success": QAPhase.COMMIT.value,
                    "on_failure": QAPhase.FAILED.value,
                },
                QAPhase.COMMIT: {
                    "agent": "qa-committer-agent",
                    "action": "commit_changes",
                    "params": {
                        "fixes_applied": self.fix_result.get("fixes_applied", []) if self.fix_result else [],
                        "worker_id": "qa-agent-chimera",
                    },
                    "timeout": 30,
                    "on_success": QAPhase.COMPLETE.value,
                    "on_failure": QAPhase.FAILED.value,
                },
                QAPhase.COMPLETE: {
                    "terminal": True,
                },
                QAPhase.FAILED: {
                    "terminal": True,
                },
            },
            "initial_state": QAPhase.DETECT.value,
        }

    def get_next_action(self) -> dict[str, Any]:
        """Get next action to execute based on current phase.

        Returns:
            Action dictionary with agent, method, params, timeout
        """
        state_machine = self.get_state_machine()
        current_state = state_machine["states"][self.current_phase]

        return current_state


def create_qa_task(
    violations: list[dict[str, Any]],
    qa_type: str = "ruff",
    scope: str = ".",
    severity_level: str = "ERROR",
    rag_context: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create QA workflow task for hive-orchestrator.

    Args:
        violations: List of violations to fix
        qa_type: Type of QA check
        scope: File/directory scope
        severity_level: Severity level
        rag_context: Optional RAG patterns for fixes

    Returns:
        Task dictionary for orchestrator
    """
    workflow = QAWorkflow(
        violations=violations,
        qa_type=qa_type,
        scope=scope,
        severity_level=severity_level,
        rag_context=rag_context or [],
    )

    return {
        "title": f"QA Workflow: {qa_type} ({len(violations)} violations)",
        "description": f"Auto-fix {len(violations)} {qa_type} violations in {scope}",
        "task_type": "qa_workflow",
        "priority": 2,
        "workflow": workflow.model_dump(),
        "payload": {
            "violations": violations,
            "qa_type": qa_type,
            "scope": scope,
        },
    }


__all__ = ["QAPhase", "QAWorkflow", "create_qa_task"]
