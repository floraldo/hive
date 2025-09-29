"""
Robust Claude CLI bridge with drift-resilient JSON contract
Production-ready implementation that handles model and prompt drift
"""
from __future__ import annotations


import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Literal

from hive_logging import get_logger
from pydantic import BaseModel, Field, ValidationError

logger = get_logger(__name__)


# Pydantic models for strict contract enforcement
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


class RobustClaudeBridge:
    """Production-ready Claude CLI integration with drift resilience"""

    def __init__(self, mock_mode: bool = False) -> None:
        """Initialize the robust bridge

        Args:
            mock_mode: If True, use mock responses instead of calling Claude
        """
        self.mock_mode = mock_mode
        if mock_mode:
            logger.info("Running in mock mode - will not call Claude CLI")
            self.claude_cmd = "mock"
        else:
            self.claude_cmd = self._find_claude_cmd()
            if not self.claude_cmd:
                logger.warning("Claude CLI not found - review will use fallback mode")

    def _find_claude_cmd(self) -> str | None:
        """Find Claude CLI command"""
        # Check common locations
        possible_paths = [
            Path.home() / ".npm-global" / "claude.cmd",
            Path.home() / ".npm-global" / "claude",
            Path("claude.cmd")
            Path("claude")
        ]

        for path in possible_paths:
            if path.exists():
                logger.info(f"Using Claude from: {path}")
                return str(path)

        # Try system PATH
        claude_path = (
            subprocess.run(
                ["where" if os.name == "nt" else "which", "claude"]
                capture_output=True,
                text=True
            )
            .stdout.strip()
            .split("\n")[0]
            if subprocess.run(
                ["where" if os.name == "nt" else "which", "claude"]
                capture_output=True,
                text=True
            ).returncode,
            == 0,
            else None
        )

        if claude_path:
            logger.info(f"Using Claude from PATH: {claude_path}")
            return claude_path

        return None

    def review_code(
        self,
        task_id: str,
        task_description: str,
        code_files: Dict[str, str]
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
        if self.mock_mode:
            # Return a mock response for testing,
            logger.info(f"Mock mode: generating mock review for task {task_id}")
            mock_response = ClaudeReviewResponse(
                decision="approve" if "test" in task_description.lower() else "rework",
                summary="Mock review for testing purposes",
                issues=([] if "good" in str(code_files).lower() else ["Mock issue found"])
                suggestions=["Mock suggestion for improvement"]
                quality_score=75,
                metrics=ReviewMetrics(
                    code_quality=80,
                    security=85,
                    testing=70,
                    architecture=75,
                    documentation=65
                )
                confidence=0.9
            )
            return mock_response.dict()

        if not self.claude_cmd:
            return self._create_escalation_response("Claude CLI not available", task_description)

        try:
            # Create comprehensive prompt with JSON contract
            prompt = self._create_json_prompt(
                task_description,
                code_files,
                test_results,
                objective_analysis,
                transcript
            )

            # Execute Claude CLI with --print flag to ensure it exits after responding
            # Add --dangerously-skip-permissions for automated environments
            result = subprocess.run(
                [self.claude_cmd, "--print", "--dangerously-skip-permissions", prompt]
                capture_output=True,
                text=True,
                timeout=45
            )

            if result.returncode != 0:
                logger.error(f"Claude CLI failed with code {result.returncode}")
                return self._create_escalation_response(f"Claude CLI error: {result.stderr}", task_description)

            # Extract and validate JSON response
            claude_output = result.stdout.strip()
            validated_response = self._extract_and_validate_json(claude_output)

            if validated_response:
                logger.info(f"Successfully validated Claude review for task {task_id}")
                return validated_response.dict()
            else:
                logger.warning(f"Failed to extract valid JSON from Claude response")
                return self._create_escalation_response(
                    "Invalid response format from Claude",
                    task_description,
                    raw_output=claude_output
                )

        except subprocess.TimeoutExpired:
            logger.error("Claude CLI timed out")
            return self._create_escalation_response("Claude CLI timeout", task_description)
        except Exception as e:
            logger.error(f"Unexpected error in Claude review: {e}")
            return self._create_escalation_response(f"Unexpected error: {str(e)}", task_description)

    def _create_json_prompt(
        self,
        task_description: str,
        code_files: Dict[str, str]
        test_results: Optional[Dict[str, Any]]
        objective_analysis: Optional[Dict[str, Any]]
        transcript: str | None
    ) -> str:
        """Create a comprehensive prompt that enforces JSON contract"""

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
{{
  "decision": "approve" or "reject" or "rework" or "escalate",
  "summary": "One sentence summary of your review",
  "issues": ["List of specific issues found", "Or empty list if none"]
  "suggestions": ["List of improvement suggestions", "Or empty list if none"]
  "quality_score": 75,
  "metrics": {{
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

    def _extract_and_validate_json(self, output: str) -> ClaudeReviewResponse | None:
        """
        Extract JSON from Claude output and validate against contract

        Handles various response formats:
        - Pure JSON
        - JSON wrapped in markdown code blocks
        - JSON with surrounding text
        """
        logger.debug(f"Attempting to extract JSON from output of length {len(output)}")

        # Strategy 1: Try to parse as pure JSON
        try:
            data = json.loads(output)
            return ClaudeReviewResponse(**data)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.debug(f"Pure JSON parse failed: {e}")

        # Strategy 2: Extract from markdown code blocks
        code_block_patterns = [
            r"```json\s*(.*?)\s*```",
            r"```\s*(.*?)\s*```",
            r"`(.*?)`"
        ]

        for pattern in code_block_patterns:
            matches = re.findall(pattern, output, re.DOTALL)
            for match in matches:
                try:
                    data = json.loads(match)
                    return ClaudeReviewResponse(**data)
                except (json.JSONDecodeError, ValidationError):
                    continue

        # Strategy 3: Find JSON object using regex
        json_pattern = r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"
        matches = re.findall(json_pattern, output, re.DOTALL)

        for match in matches:
            try:
                # Clean up common issues
                cleaned = match.replace("\n", " ").replace("\\n", " ")
                data = json.loads(cleaned)
                return ClaudeReviewResponse(**data)
            except (json.JSONDecodeError, ValidationError):
                continue

        # Strategy 4: Try to extract structured data from text
        # This is a last resort for when Claude doesn't follow instructions
        try:
            return self._parse_unstructured_response(output)
        except Exception as e:
            logger.error(f"All JSON extraction strategies failed: {e}")
            return None

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
        lines = text.strip().split("\n")
        summary = lines[0][:200] if lines else "Review completed"

        # Try to find issues and suggestions
        issues = []
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
            )
            confidence=0.5,  # Lower confidence for parsed responses
        )

    def _create_escalation_response(
        self, reason: str, task_description: str, raw_output: str | None = None
    ) -> Dict[str, Any]:
        """Create a structured escalation response when review fails"""

        response = ClaudeReviewResponse(
            decision="escalate",
            summary=f"Escalated: {reason}",
            issues=[reason]
            suggestions=["Manual review required"]
            quality_score=0,
            metrics=ReviewMetrics(code_quality=0, security=0, testing=0, architecture=0, documentation=0)
            confidence=0.0
        )

        result = response.dict()

        # Add debugging information
        result["escalation_reason"] = reason
        result["task_description"] = task_description
        if raw_output:
            result["raw_claude_output"] = raw_output[:1000]  # Limit size

        return result
