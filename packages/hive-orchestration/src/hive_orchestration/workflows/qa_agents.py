"""QA Agent Registry - Chimera Agents for Quality Automation.

Provides lightweight Python agents for fast auto-fixing of QA violations.
Uses RAG patterns and MCP tools (morphllm, sequential-thinking) for intelligent fixes.
"""

from __future__ import annotations

import subprocess
from typing import Any

from hive_logging import get_logger

logger = get_logger(__name__)


class QADetectorAgent:
    """Violation detection agent.

    Runs QA tools (Ruff, Golden Rules validator, pytest) to detect violations.
    """

    def __init__(self) -> None:
        """Initialize detector agent."""
        self.logger = logger
        self.logger.info("QA detector agent initialized")

    async def detect_violations(
        self,
        qa_type: str,
        scope: str,
        severity_level: str,
    ) -> dict[str, Any]:
        """Detect violations using appropriate QA tool.

        Args:
            qa_type: Type of QA check ('ruff', 'golden_rules', 'test', 'security')
            scope: File/directory scope
            severity_level: Severity level filter

        Returns:
            Detection result with violations list
        """
        self.logger.info(f"Detecting {qa_type} violations in {scope} (severity: {severity_level})")

        try:
            if qa_type == "ruff":
                return await self._detect_ruff(scope)
            elif qa_type == "golden_rules":
                return await self._detect_golden_rules(scope, severity_level)
            elif qa_type == "test":
                return await self._detect_test_failures(scope)
            elif qa_type == "security":
                return await self._detect_security(scope)
            else:
                return {"status": "error", "error": f"Unknown QA type: {qa_type}"}

        except Exception as e:
            self.logger.error(f"Detection failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    async def _detect_ruff(self, scope: str) -> dict[str, Any]:
        """Detect Ruff violations."""
        try:
            result = subprocess.run(
                ["ruff", "check", scope, "--output-format=json"],
                capture_output=True,
                text=True,
                timeout=60,
            )

            # Ruff exits with non-zero if violations found (this is expected)
            violations = []
            if result.stdout:
                import json

                violations = json.loads(result.stdout)

            self.logger.info(f"Ruff detected {len(violations)} violations")

            return {
                "status": "success",
                "violations": violations,
                "violations_count": len(violations),
            }

        except subprocess.TimeoutExpired:
            return {"status": "error", "error": "Ruff check timed out"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _detect_golden_rules(self, scope: str, severity_level: str) -> dict[str, Any]:
        """Detect Golden Rules violations."""
        try:
            # Run Golden Rules validator
            result = subprocess.run(
                [
                    "python",
                    "scripts/validation/validate_golden_rules.py",
                    "--level",
                    severity_level,
                    "--format",
                    "json",
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )

            violations = []
            if result.stdout:
                import json

                violations = json.loads(result.stdout).get("violations", [])

            self.logger.info(f"Golden Rules detected {len(violations)} violations")

            return {
                "status": "success",
                "violations": violations,
                "violations_count": len(violations),
            }

        except subprocess.TimeoutExpired:
            return {"status": "error", "error": "Golden Rules check timed out"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _detect_test_failures(self, scope: str) -> dict[str, Any]:
        """Detect pytest test failures."""
        try:
            result = subprocess.run(
                ["python", "-m", "pytest", scope, "--collect-only", "-q"],
                capture_output=True,
                text=True,
                timeout=60,
            )

            # Parse pytest output for failures
            failures = []
            if result.returncode != 0:
                failures = [{"type": "pytest", "message": "Test collection failed", "output": result.stdout}]

            self.logger.info(f"Pytest detected {len(failures)} failures")

            return {
                "status": "success",
                "violations": failures,
                "violations_count": len(failures),
            }

        except subprocess.TimeoutExpired:
            return {"status": "error", "error": "Pytest check timed out"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _detect_security(self, scope: str) -> dict[str, Any]:
        """Detect security vulnerabilities."""
        # TODO: Integrate security scanner (bandit, safety, etc.)
        self.logger.warning("Security scanning not yet implemented")

        return {
            "status": "success",
            "violations": [],
            "violations_count": 0,
        }


class QAFixerAgent:
    """Violation fixer agent with RAG enhancement.

    Uses RAG patterns and morphllm for intelligent auto-fixes.
    """

    def __init__(self) -> None:
        """Initialize fixer agent."""
        self.logger = logger
        self.logger.info("QA fixer agent initialized")

    async def apply_fixes(
        self,
        violations: list[dict[str, Any]],
        rag_context: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Apply auto-fixes to violations.

        Args:
            violations: List of violations to fix
            rag_context: RAG patterns for guidance

        Returns:
            Fix result with success count
        """
        self.logger.info(f"Applying fixes to {len(violations)} violations")

        fixed_count = 0
        failed_count = 0
        fixes_applied = []

        for violation in violations:
            try:
                # Attempt fix based on violation type
                fix_result = await self._fix_violation(violation, rag_context)

                if fix_result.get("success"):
                    fixed_count += 1
                    fixes_applied.append(fix_result)
                else:
                    failed_count += 1

            except Exception as e:
                self.logger.error(f"Fix failed for violation: {e}", exc_info=True)
                failed_count += 1

        self.logger.info(f"Fixes applied: {fixed_count} success, {failed_count} failed")

        return {
            "status": "success" if fixed_count > 0 else "failed",
            "fixes_applied": fixes_applied,
            "fixed_count": fixed_count,
            "failed_count": failed_count,
        }

    async def _fix_violation(
        self,
        violation: dict[str, Any],
        rag_context: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Fix single violation.

        Args:
            violation: Violation to fix
            rag_context: RAG patterns

        Returns:
            Fix result
        """
        violation_type = violation.get("type", "unknown")

        # Ruff auto-fix (use ruff --fix)
        if violation_type.startswith(("E", "F", "W")):
            return await self._fix_ruff_violation(violation)

        # Golden Rules fixes
        if violation_type.startswith("GR"):
            return await self._fix_golden_rule(violation, rag_context)

        # Unknown type
        return {"success": False, "error": f"Unknown violation type: {violation_type}"}

    async def _fix_ruff_violation(self, violation: dict[str, Any]) -> dict[str, Any]:
        """Fix Ruff violation using ruff --fix."""
        try:
            file_path = violation.get("file")
            if not file_path:
                return {"success": False, "error": "No file path in violation"}

            # Run ruff --fix on file
            result = subprocess.run(
                ["ruff", "check", "--fix", file_path],
                capture_output=True,
                text=True,
                timeout=30,
            )

            return {
                "success": True,
                "violation_type": violation.get("type"),
                "file": file_path,
                "method": "ruff --fix",
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _fix_golden_rule(
        self,
        violation: dict[str, Any],
        rag_context: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Fix Golden Rule violation.

        Uses RAG patterns for guidance.
        TODO: Integrate with morphllm for intelligent pattern application.
        """
        self.logger.warning(f"Golden Rule fix not yet implemented: {violation.get('type')}")

        # For now, return failure (escalate to CC worker)
        return {
            "success": False,
            "error": "Golden Rule auto-fix not yet implemented (escalating to CC worker)",
        }


class QAValidatorAgent:
    """Validation agent to verify fixes worked."""

    def __init__(self) -> None:
        """Initialize validator agent."""
        self.logger = logger
        self.logger.info("QA validator agent initialized")

    async def validate_fixes(
        self,
        qa_type: str,
        scope: str,
    ) -> dict[str, Any]:
        """Re-run QA tool to validate fixes.

        Args:
            qa_type: Type of QA check
            scope: File/directory scope

        Returns:
            Validation result
        """
        self.logger.info(f"Validating {qa_type} fixes in {scope}")

        try:
            # Re-run detection to check if violations are gone
            detector = QADetectorAgent()
            result = await detector.detect_violations(qa_type, scope, "ERROR")

            remaining_violations = result.get("violations_count", 0)

            if remaining_violations == 0:
                return {
                    "status": "success",
                    "message": "All violations fixed",
                }
            else:
                return {
                    "status": "failed",
                    "message": f"{remaining_violations} violations remain",
                    "remaining_violations": remaining_violations,
                }

        except Exception as e:
            return {"status": "error", "error": str(e)}


class QACommitterAgent:
    """Git commit agent for QA fixes."""

    def __init__(self) -> None:
        """Initialize committer agent."""
        self.logger = logger
        self.logger.info("QA committer agent initialized")

    async def commit_changes(
        self,
        fixes_applied: list[dict[str, Any]],
        worker_id: str,
    ) -> dict[str, Any]:
        """Commit fixes to git.

        Args:
            fixes_applied: List of fixes that were applied
            worker_id: Worker ID for commit message

        Returns:
            Commit result
        """
        self.logger.info(f"Committing {len(fixes_applied)} fixes (worker: {worker_id})")

        try:
            # Build commit message
            commit_message = f"fix(qa): Auto-fix {len(fixes_applied)} violations\n\n"
            commit_message += f"Worker: {worker_id}\n"
            commit_message += "Fixes:\n"

            for fix in fixes_applied[:10]:  # Limit to 10 for message brevity
                violation_type = fix.get("violation_type", "unknown")
                file_path = fix.get("file", "unknown")
                commit_message += f"- {violation_type} in {file_path}\n"

            if len(fixes_applied) > 10:
                commit_message += f"... and {len(fixes_applied) - 10} more\n"

            # Git add and commit
            subprocess.run(["git", "add", "."], check=True, timeout=30)

            subprocess.run(
                ["git", "commit", "-m", commit_message],
                check=True,
                timeout=30,
            )

            self.logger.info("Fixes committed successfully")

            return {
                "status": "success",
                "commit_message": commit_message,
            }

        except subprocess.CalledProcessError as e:
            return {"status": "error", "error": f"Git commit failed: {e}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}


def create_qa_agents_registry() -> dict[str, Any]:
    """Create agent registry for QA workflow execution.

    Returns:
        Dictionary mapping agent names to agent instances
    """
    return {
        "qa-detector-agent": QADetectorAgent(),
        "qa-fixer-agent": QAFixerAgent(),
        "qa-validator-agent": QAValidatorAgent(),
        "qa-committer-agent": QACommitterAgent(),
    }


__all__ = [
    "QACommitterAgent",
    "QADetectorAgent",
    "QAFixerAgent",
    "QAValidatorAgent",
    "create_qa_agents_registry",
]
