"""
Chimera Workflow - E2E Test-Driven Feature Development

Orchestrates the complete autonomous development loop:
1. Generate E2E test (failing)
2. Implement code to pass test
3. Guardian review
4. Deploy to staging
5. Validate E2E test on staging
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ChimeraPhase(str, Enum):
    """Phases in the Chimera workflow."""

    E2E_TEST_GENERATION = "e2e_test_generation"
    CODE_IMPLEMENTATION = "code_implementation"
    GUARDIAN_REVIEW = "guardian_review"
    STAGING_DEPLOYMENT = "staging_deployment"
    E2E_VALIDATION = "e2e_validation"
    COMPLETE = "complete"
    FAILED = "failed"


class ChimeraWorkflow(BaseModel):
    """
    Chimera workflow state machine.

    Implements autonomous TDD loop with E2E validation.

    Example:
        workflow = ChimeraWorkflow(
            feature_description="User can login with Google OAuth",
            target_url="https://myapp.dev/login",
            staging_url="https://staging.myapp.dev/login"
        )
    """

    # Feature definition
    feature_description: str = Field(description="Natural language feature description")
    target_url: str = Field(description="Production URL for testing")
    staging_url: str | None = Field(default=None, description="Staging URL for validation")

    # Workflow state
    current_phase: ChimeraPhase = Field(
        default=ChimeraPhase.E2E_TEST_GENERATION,
        description="Current workflow phase"
    )

    # Phase artifacts
    test_path: str | None = Field(default=None, description="Path to generated E2E test")
    test_generation_result: dict[str, Any] | None = Field(
        default=None,
        description="E2E test generation result"
    )

    code_pr_id: str | None = Field(default=None, description="Pull request ID")
    code_commit_sha: str | None = Field(default=None, description="Code commit SHA")
    code_implementation_result: dict[str, Any] | None = Field(
        default=None,
        description="Code implementation result"
    )

    review_decision: str | None = Field(default=None, description="Guardian review decision")
    review_result: dict[str, Any] | None = Field(
        default=None,
        description="Guardian review result"
    )

    deployment_url: str | None = Field(default=None, description="Deployed staging URL")
    deployment_result: dict[str, Any] | None = Field(
        default=None,
        description="Deployment result"
    )

    validation_status: str | None = Field(default=None, description="E2E validation status")
    validation_result: dict[str, Any] | None = Field(
        default=None,
        description="E2E validation result"
    )

    # Workflow metadata
    retry_count: int = Field(default=0, description="Number of retry attempts")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    error_message: str | None = Field(default=None, description="Error message if failed")

    def get_state_machine(self) -> dict[str, Any]:
        """
        Get state machine definition for workflow.

        Returns:
            State machine dict with transitions and actions
        """
        return {
            "states": {
                ChimeraPhase.E2E_TEST_GENERATION: {
                    "description": "Generate failing E2E test from feature description",
                    "agent": "e2e-tester-agent",
                    "action": "generate_test",
                    "on_success": ChimeraPhase.CODE_IMPLEMENTATION,
                    "on_failure": ChimeraPhase.FAILED,
                    "timeout": 300,  # 5 minutes
                },
                ChimeraPhase.CODE_IMPLEMENTATION: {
                    "description": "Implement code to make E2E test pass",
                    "agent": "coder-agent",
                    "action": "implement_feature",
                    "on_success": ChimeraPhase.GUARDIAN_REVIEW,
                    "on_failure": ChimeraPhase.FAILED,
                    "timeout": 1800,  # 30 minutes
                },
                ChimeraPhase.GUARDIAN_REVIEW: {
                    "description": "Review code for quality and compliance",
                    "agent": "guardian-agent",
                    "action": "review_pr",
                    "on_success": ChimeraPhase.STAGING_DEPLOYMENT,
                    "on_failure": ChimeraPhase.CODE_IMPLEMENTATION,  # Retry implementation
                    "timeout": 600,  # 10 minutes
                },
                ChimeraPhase.STAGING_DEPLOYMENT: {
                    "description": "Deploy to staging environment",
                    "agent": "deployment-agent",
                    "action": "deploy_to_staging",
                    "on_success": ChimeraPhase.E2E_VALIDATION,
                    "on_failure": ChimeraPhase.FAILED,
                    "timeout": 900,  # 15 minutes
                },
                ChimeraPhase.E2E_VALIDATION: {
                    "description": "Run E2E test against staging deployment",
                    "agent": "e2e-tester-agent",
                    "action": "execute_test",
                    "on_success": ChimeraPhase.COMPLETE,
                    "on_failure": ChimeraPhase.CODE_IMPLEMENTATION,  # Retry implementation
                    "timeout": 600,  # 10 minutes
                },
                ChimeraPhase.COMPLETE: {
                    "description": "Workflow completed successfully",
                    "terminal": True,
                },
                ChimeraPhase.FAILED: {
                    "description": "Workflow failed",
                    "terminal": True,
                },
            },
            "initial_state": ChimeraPhase.E2E_TEST_GENERATION,
            "terminal_states": [ChimeraPhase.COMPLETE, ChimeraPhase.FAILED],
        }

    def transition_to(self, phase: ChimeraPhase, result: dict[str, Any] | None = None) -> None:
        """
        Transition workflow to new phase.

        Args:
            phase: Target phase
            result: Result data from previous phase
        """
        self.current_phase = phase

        # Store phase-specific results
        if phase == ChimeraPhase.CODE_IMPLEMENTATION and result:
            self.test_generation_result = result
            self.test_path = result.get("test_path")

        elif phase == ChimeraPhase.GUARDIAN_REVIEW and result:
            self.code_implementation_result = result
            self.code_pr_id = result.get("pr_id")
            self.code_commit_sha = result.get("commit_sha")

        elif phase == ChimeraPhase.STAGING_DEPLOYMENT and result:
            self.review_result = result
            self.review_decision = result.get("decision")

        elif phase == ChimeraPhase.E2E_VALIDATION and result:
            self.deployment_result = result
            self.deployment_url = result.get("staging_url")

        elif phase == ChimeraPhase.COMPLETE and result:
            self.validation_result = result
            self.validation_status = result.get("status")

        elif phase == ChimeraPhase.FAILED:
            self.error_message = result.get("error") if result else "Unknown error"

    def can_retry(self) -> bool:
        """Check if workflow can be retried."""
        return self.retry_count < self.max_retries

    def increment_retry(self) -> None:
        """Increment retry counter."""
        self.retry_count += 1

    def is_terminal(self) -> bool:
        """Check if workflow is in terminal state."""
        return self.current_phase in (ChimeraPhase.COMPLETE, ChimeraPhase.FAILED)

    def get_next_action(self) -> dict[str, Any]:
        """
        Get next action to execute based on current phase.

        Returns:
            Action dict with agent, action, and parameters
        """
        state_machine = self.get_state_machine()
        current_state = state_machine["states"][self.current_phase]

        if current_state.get("terminal"):
            return {"action": "none", "terminal": True}

        # Build action parameters based on phase
        if self.current_phase == ChimeraPhase.E2E_TEST_GENERATION:
            params = {
                "feature": self.feature_description,
                "url": self.target_url,
            }
        elif self.current_phase == ChimeraPhase.CODE_IMPLEMENTATION:
            params = {
                "test_path": self.test_path,
                "feature": self.feature_description,
            }
        elif self.current_phase == ChimeraPhase.GUARDIAN_REVIEW:
            params = {
                "pr_id": self.code_pr_id,
            }
        elif self.current_phase == ChimeraPhase.STAGING_DEPLOYMENT:
            params = {
                "commit_sha": self.code_commit_sha,
            }
        elif self.current_phase == ChimeraPhase.E2E_VALIDATION:
            params = {
                "test_path": self.test_path,
                "url": self.deployment_url or self.staging_url,
            }
        else:
            params = {}

        return {
            "agent": current_state["agent"],
            "action": current_state["action"],
            "params": params,
            "timeout": current_state["timeout"],
        }


def create_chimera_task(
    feature_description: str,
    target_url: str,
    staging_url: str | None = None,
    priority: int = 3,
) -> dict[str, Any]:
    """
    Create a Chimera workflow task.

    Args:
        feature_description: Natural language feature description
        target_url: Production URL to test
        staging_url: Staging URL for validation (optional)
        priority: Task priority (1-5, higher = more important)

    Returns:
        Task dict ready for orchestrator

    Example:
        task = create_chimera_task(
            feature_description="User can login with Google OAuth",
            target_url="https://myapp.dev/login",
            staging_url="https://staging.myapp.dev/login"
        )
    """
    workflow = ChimeraWorkflow(
        feature_description=feature_description,
        target_url=target_url,
        staging_url=staging_url,
    )

    return {
        "title": f"Chimera: {feature_description[:50]}",
        "description": feature_description,
        "task_type": "chimera_workflow",
        "priority": priority,
        "workflow": workflow.model_dump(),
        "payload": {
            "feature_description": feature_description,
            "target_url": target_url,
            "staging_url": staging_url,
        },
    }


__all__ = ["ChimeraWorkflow", "ChimeraPhase", "create_chimera_task"]
