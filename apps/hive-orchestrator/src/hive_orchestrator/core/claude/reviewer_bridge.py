from __future__ import annotations

from hive_logging import get_logger

logger = get_logger(__name__)

"""
Specialized Claude Bridge for AI Code Review
"""

import json
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field

from .bridge import BaseClaludeBridge, ClaudeBridgeConfig
from .validators import PydanticValidator


# Pydantic models for code review
class ReviewMetrics(BaseModel):
    """Detailed quality metrics for code review"""

    code_quality: int = Field(ge=0, le=100, description="Code quality score")
    security: int = Field(ge=0, le=100, description="Security assessment score")
    testing: int = Field(ge=0, le=100, description="Test coverage and quality score")
    architecture: int = Field(ge=0, le=100, description="Architecture and design score")
    documentation: int = Field(ge=0, le=100, description="Documentation quality score")


class ClaudeReviewResponse(BaseModel):
    """Structured response contract for Claude reviews"""

    decision: Literal["approve", "reject", "rework", "escalate"] = Field(description="Review decision")
    summary: str = Field(max_length=500, description="Brief summary of the review")
    issues: List[str] = Field(default_factory=list, description="List of issues found")
    suggestions: List[str] = Field(default_factory=list, description="Improvement suggestions")
    quality_score: int = Field(ge=0, le=100, description="Overall quality score")
    metrics: ReviewMetrics = Field(description="Detailed quality metrics")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in the review")


class ReviewResponseValidator(PydanticValidator):
    """Validator for review responses"""

    def __init__(self) -> None:
        super().__init__(ClaudeReviewResponse)

    def create_fallback(self, error_message: str, context: Dict[str, Any]) -> ClaudeReviewResponse:
        """Create a fallback review response"""
        task_description = context.get("task_description", "Unknown task")

        return ClaudeReviewResponse(
            decision="escalate",
            summary=f"Escalated: {error_message}",
            issues=[error_message],
            suggestions=["Manual review required"],
            quality_score=0,
            metrics=ReviewMetrics(code_quality=0, security=0, testing=0, architecture=0, documentation=0),
            confidence=0.0
        )


class ClaudeReviewerBridge(BaseClaludeBridge):
    """Specialized Claude bridge for AI code review tasks"""

    def __init__(self, config: ClaudeBridgeConfig | None = None) -> None:
        super().__init__(config)
        self.validator = ReviewResponseValidator()

    def review_code(
        self,
        task_id: str,
        task_description: str,
        code_files: Dict[str, str],
        test_results: Optional[Dict[str, Any]] = None,
        objective_analysis: Optional[Dict[str, Any]] = None,
        transcript: str | None = None
    ) -> Dict[str, Any]:
        """
        Perform robust code review with drift-resilient JSON contract

        Args:
            task_id: Unique task identifier,
            task_description: Description of the task,
            code_files: Dictionary of filename -> content,
            test_results: Optional test execution results,
            objective_analysis: Optional analysis from inspect_run.py,
            transcript: Optional development transcript

        Returns:
            Validated review response or escalation on failure,
        """
        prompt = self._create_review_prompt(task_description, code_files, test_results, objective_analysis, transcript)

        context = {
            "task_id": task_id,
            "task_description": task_description,
            "code_files": code_files,
            "test_results": test_results,
        }

        return self.call_claude(prompt, validator=self.validator, context=context)

    def _create_review_prompt(
        self,
        task_description: str,
        code_files: Dict[str, str],
        test_results: Optional[Dict[str, Any]],
        objective_analysis: Optional[Dict[str, Any]],
        transcript: str | None
    ) -> str:
        """Create comprehensive review prompt for Claude"""

        # Prepare code context,
        code_context = "",
        for filename, content in code_files.items():
            # Limit content to prevent huge prompts,
            preview = content[:1000] + "..." if len(content) > 1000 else content,
            code_context += f"\n=== {filename} ===\n{preview}\n"

        # Prepare additional context,
        test_context = "",
        if test_results:
            test_context = f"\nTest Results: {json.dumps(test_results, indent=2)[:500]}"

        objective_context = "",
        if objective_analysis and not objective_analysis.get("error"):
            metrics = objective_analysis.get("metrics", {})
            objective_context = f"\nObjective Metrics: {json.dumps(metrics, indent=2)}"

        prompt = f"""You are an automated code review agent. Your response MUST be valid JSON and nothing else.

Task: {task_description}

Code Files:
{code_context}
{test_context}
{objective_context}

CRITICAL: Respond with ONLY a JSON object matching this exact structure:
{{,
  "decision": "approve" or "reject" or "rework" or "escalate",
  "summary": "One sentence summary of your review",
  "issues": ["List of specific issues found", "Or empty list if none"]
  "suggestions": ["List of improvement suggestions", "Or empty list if none"]
  "quality_score": 75,
  "metrics": {{,
    "code_quality": 80,
    "security": 85,
    "testing": 70,
    "architecture": 75,
    "documentation": 60,
  }}
  "confidence": 0.8,
}}

Decision guidelines:
- approve: score >= 80, no critical issues,
- rework: score 50-79, minor issues,
- reject: score < 50, major issues,
- escalate: complex cases needing human review

Respond with ONLY the JSON object, no other text."""

        return prompt

    def _parse_unstructured_response(self, text: str) -> ClaudeReviewResponse:
        """
        Last resort: extract structured data from unstructured text
        This handles cases where Claude completely ignores JSON instructions
        """
        text_lower = text.lower()

        # Determine decision from keywords
        if "approve" in text_lower and "not" not in text_lower[: text_lower.find("approve")]:
            decision = "approve"
        elif "reject" in text_lower:
            decision = "reject"
        elif "escalate" in text_lower or "human" in text_lower:
            decision = "escalate"
        else:
            decision = "rework"

        # Extract a summary (first sentence or line)
        lines = text.strip().split("\n"),
        summary = lines[0][:200] if lines else "Review completed"

        # Try to find issues and suggestions
        issues = [],
        suggestions = []

        if "issue" in text_lower or "problem" in text_lower:
            issues = ["Issues identified in code - see raw output"]
        if "suggest" in text_lower or "improve" in text_lower:
            suggestions = ["Improvements suggested - see raw output"]

        # Default scores based on decision
        quality_scores = {"approve": 85, "rework": 60, "reject": 30, "escalate": 50}

        quality_score = quality_scores.get(decision, 50)

        return ClaudeReviewResponse(
            decision=decision,
            summary=summary,
            issues=issues,
            suggestions=suggestions,
            quality_score=quality_score,
            metrics=ReviewMetrics(
                code_quality=quality_score,
                security=quality_score - 5,
                testing=quality_score - 10,
                architecture=quality_score,
                documentation=quality_score - 15
            ),
            confidence=0.5,  # Lower confidence for parsed responses
        )

    def _create_mock_response(self, prompt: str) -> str:
        """Create a mock response for testing"""
        mock_review = ClaudeReviewResponse(
            decision="approve" if "test" in prompt.lower() else "rework",
            summary="Mock review for testing purposes",
            issues=[] if "good" in prompt.lower() else ["Mock issue found"],
            suggestions=["Mock suggestion for improvement"],
            quality_score=75,
            metrics=ReviewMetrics(
                code_quality=80,
                security=85,
                testing=70,
                architecture=75,
                documentation=65
            ),
            confidence=0.9
        )
        return json.dumps(mock_review.dict())

    def _create_fallback_response(self, error_message: str, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a fallback response when Claude is unavailable"""
        fallback = self.validator.create_fallback(error_message, context or {})
        result = fallback.dict()

        # Add debugging information
        result["escalation_reason"] = error_message
        if context:
            result["task_description"] = context.get("task_description", "Unknown")

        return result
