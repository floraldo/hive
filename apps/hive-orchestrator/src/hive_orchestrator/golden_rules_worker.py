"""Golden Rules Worker - Autonomous Architectural Compliance Worker

Extends QAWorkerCore to provide Golden Rules validation and auto-fix:
- Simple rule auto-fixes (Rule 31: ruff config, Rule 32: Python version)
- Code pattern fixes (Rule 9: print → logger, Rule 6: import patterns)
- Architectural violation detection and escalation
- Integration with existing Golden Rules validators

Auto-Fixable Rules:
- Rule 31: Ruff Config Consistency
- Rule 32: Python Version Specification
- Rule 9: Logging Standards (print → get_logger)
- Rule 6: Import patterns (partial)

Escalation Required:
- Rule 37: Unified Config Enforcement (complex migration)
- Rule 4: Package vs App Discipline
- Rule 5: App Contracts
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

from hive_logging import get_logger
from hive_orchestration.events import QATaskEvent
from hive_orchestration.models.task import Task
from hive_orchestrator.qa_worker import QAWorkerCore
from hive_tests.architectural_validators import GOLDEN_RULES_REGISTRY, RuleSeverity, run_all_golden_rules

logger = get_logger(__name__)


class GoldenRulesWorkerCore(QAWorkerCore):
    """Autonomous Golden Rules compliance worker.

    Extends QAWorkerCore with:
    - Golden Rules validation integration
    - Rule-specific auto-fix logic
    - Architectural violation escalation
    - Migration guidance for complex rules

    Auto-Fix Capabilities:
    - Config file additions (Rule 31, 32)
    - Code pattern replacements (Rule 9)
    - Import statement fixes (Rule 6, partial)

    Performance Targets:
    - Auto-fix success: 50%+ (complex architectural rules)
    - Fix latency: <10s per file
    - False positive rate: <0.5%
    """

    def __init__(
        self,
        worker_id: str = "golden-rules-worker-1",
        workspace: Path | None = None,
        config: dict[str, Any] | None = None,
    ):
        """Initialize Golden Rules worker with auto-fix capabilities."""
        super().__init__(
            worker_id=worker_id,
            workspace=workspace,
            config=config,
        )

        # Set worker type for identification
        self.worker_type = "golden_rules"

        logger.info(f"Golden Rules Worker {worker_id} initialized")
        logger.info("  Auto-fix capabilities: Rules 31, 32, 9, 6 (partial)")

    async def detect_golden_rules_violations(
        self, file_paths: list[Path] | None = None,
    ) -> dict[str, Any]:
        """Detect Golden Rules violations in workspace using registry API.

        Args:
            file_paths: Specific files to check (None = check all)

        Returns:
            {
                "violations": [{"rule_id": "31", "file": "pyproject.toml", ...}],
                "total_count": 3,
                "auto_fixable_count": 2,
                "escalation_count": 1
            }

        """
        logger.info("Running Golden Rules validation via registry API...")

        try:
            # Run validation using registry API (no subprocess overhead)
            all_passed, results = run_all_golden_rules(
                self.workspace,
                scope_files=file_paths,
                engine="registry",
                max_severity=RuleSeverity.ERROR,  # Focus on ERROR level rules
            )

            if all_passed:
                logger.info("  No Golden Rules violations found")
                return {
                    "violations": [],
                    "total_count": 0,
                    "auto_fixable_count": 0,
                    "escalation_count": 0,
                }

            # Convert results to violation format
            violations = self._convert_results_to_violations(results)

            # Classify as auto-fixable or escalation using registry metadata
            auto_fixable = [v for v in violations if self._is_auto_fixable(v)]
            escalation = [v for v in violations if not self._is_auto_fixable(v)]

            logger.info(
                f"  Found {len(violations)} violations "
                f"({len(auto_fixable)} auto-fixable, {len(escalation)} escalation)",
            )

            return {
                "violations": violations,
                "total_count": len(violations),
                "auto_fixable_count": len(auto_fixable),
                "escalation_count": len(escalation),
            }

        except Exception as e:
            logger.error(f"Golden Rules validation failed: {e}")
            return {
                "violations": [],
                "total_count": 0,
                "auto_fixable_count": 0,
                "escalation_count": 0,
            }

    def _convert_results_to_violations(self, results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert registry results to violation format.

        Args:
            results: Registry validation results from run_all_golden_rules()

        Returns:
            List of violation dicts compatible with auto-fix logic

        """
        violations = []

        for rule_name, result in results.items():
            if result["passed"]:
                continue  # Skip passing rules

            # Find rule metadata from registry
            rule_meta = self._get_rule_metadata(rule_name)
            if not rule_meta:
                logger.warning(f"Rule metadata not found for: {rule_name}")
                continue

            # Extract violations from result
            for violation_msg in result.get("violations", []):
                # Parse file path from violation message
                # Format: "packages/hive-api/pyproject.toml: Missing [tool.ruff]"
                file_match = re.search(r"((?:packages|apps)/[^:]+)", violation_msg)
                file_path = file_match.group(1) if file_match else "unknown"

                violations.append({
                    "rule_id": str(rule_meta.get("id", "unknown")),
                    "rule_name": rule_name,
                    "file": file_path,
                    "message": violation_msg,
                    "severity": rule_meta.get("severity", "INFO"),
                    "can_autofix": rule_meta.get("can_autofix", False),
                })

        return violations

    def _get_rule_metadata(self, rule_name: str) -> dict[str, Any] | None:
        """Get metadata for a rule from the registry.

        Args:
            rule_name: Name of the rule (e.g., "No sys.path Manipulation")

        Returns:
            Rule metadata dict or None if not found

        """
        for rule in GOLDEN_RULES_REGISTRY:
            if rule.get("name") == rule_name:
                return rule
        return None

    def _is_auto_fixable(self, violation: dict[str, Any]) -> bool:
        """Check if violation can be auto-fixed using registry metadata.

        Auto-fixable rules (dynamically queried from registry):
        - Rule 31: Ruff Config Consistency (add config section)
        - Rule 32: Python Version Specification (add version)
        - Rule 9: Logging Standards (print → logger)
        - Rule 6: Import patterns (partial support)

        Args:
            violation: Violation dict with can_autofix flag

        Returns:
            True if auto-fixable, False if escalation needed

        """
        # Use registry metadata if available (new format)
        if "can_autofix" in violation:
            return violation["can_autofix"]

        # Fallback to hardcoded list for backwards compatibility
        rule_id = violation.get("rule_id", "")
        auto_fixable_rules = ["31", "32", "9", "6"]
        return rule_id in auto_fixable_rules

    async def fix_rule_31_ruff_config(self, file_path: Path) -> bool:
        """Fix Rule 31: Add [tool.ruff] to pyproject.toml.

        Args:
            file_path: Path to pyproject.toml

        Returns:
            True if fix applied successfully

        """
        try:
            content = file_path.read_text(encoding="utf-8")

            if "[tool.ruff]" in content:
                logger.info(f"  {file_path.name} already has [tool.ruff]")
                return False

            # Add ruff config section
            ruff_config = """
[tool.ruff]
line-length = 120
select = ["E", "F", "I", "W", "C90", "N", "UP", "B"]
ignore = []

[tool.ruff.isort]
known-first-party = ["hive_*"]
"""

            # Append to end of file
            new_content = content + "\n" + ruff_config

            file_path.write_text(new_content, encoding="utf-8")

            logger.info(f"  ✅ Fixed Rule 31 in {file_path.name}")
            return True

        except Exception as e:
            logger.error(f"  Failed to fix Rule 31 in {file_path}: {e}")
            return False

    async def fix_rule_32_python_version(self, file_path: Path) -> bool:
        """Fix Rule 32: Add Python version to pyproject.toml.

        Args:
            file_path: Path to pyproject.toml

        Returns:
            True if fix applied successfully

        """
        try:
            content = file_path.read_text(encoding="utf-8")

            # Check if version already specified
            if 'python = "^3.11"' in content or 'requires-python = ">=3.11"' in content:
                logger.info(f"  {file_path.name} already has Python version")
                return False

            # Try to add to [tool.poetry.dependencies] section
            if "[tool.poetry.dependencies]" in content:
                # Add after [tool.poetry.dependencies]
                new_content = content.replace(
                    "[tool.poetry.dependencies]",
                    '[tool.poetry.dependencies]\npython = "^3.11"',
                )

                file_path.write_text(new_content, encoding="utf-8")
                logger.info(f"  ✅ Fixed Rule 32 in {file_path.name}")
                return True

            # Try to add [project] section for PEP 621
            if "[project]" in content:
                new_content = content.replace(
                    "[project]",
                    '[project]\nrequires-python = ">=3.11"',
                )

                file_path.write_text(new_content, encoding="utf-8")
                logger.info(f"  ✅ Fixed Rule 32 in {file_path.name}")
                return True

            logger.warning(f"  Cannot fix Rule 32 in {file_path.name}: No suitable section")
            return False

        except Exception as e:
            logger.error(f"  Failed to fix Rule 32 in {file_path}: {e}")
            return False

    async def fix_rule_9_logging(self, file_path: Path) -> bool:
        """Fix Rule 9: Replace print() with get_logger().

        Args:
            file_path: Path to Python file

        Returns:
            True if fix applied successfully

        """
        try:
            content = file_path.read_text(encoding="utf-8")

            # Check if file has print statements
            if "print(" not in content:
                return False

            # Add logger import if not present
            needs_import = "get_logger" not in content

            if needs_import:
                # Add import after other imports
                import_line = "from hive_logging import get_logger"

                # Find last import line
                lines = content.split("\n")
                last_import_idx = 0

                for i, line in enumerate(lines):
                    if line.strip().startswith(("import ", "from ")):
                        last_import_idx = i

                # Insert logger import
                lines.insert(last_import_idx + 1, import_line)
                lines.insert(last_import_idx + 2, "")  # Blank line
                lines.insert(last_import_idx + 3, "logger = get_logger(__name__)")
                lines.insert(last_import_idx + 4, "")

                content = "\n".join(lines)

            # Replace print() with logger.info()
            # Simple pattern: print("message") → logger.info("message")
            content = re.sub(
                r'print\((["\'].*?["\'])\)',
                r"logger.info(\1)",
                content,
            )

            # Replace print(f"...") → logger.info(f"...")
            content = re.sub(
                r'print\((f["\'].*?["\'])\)',
                r"logger.info(\1)",
                content,
            )

            file_path.write_text(content, encoding="utf-8")

            logger.info(f"  ✅ Fixed Rule 9 in {file_path.name}")
            return True

        except Exception as e:
            logger.error(f"  Failed to fix Rule 9 in {file_path}: {e}")
            return False

    async def apply_golden_rules_fixes(
        self, violations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Apply auto-fixes for Golden Rules violations.

        Args:
            violations: List of violations to fix

        Returns:
            {
                "success": True,
                "violations_fixed": 5,
                "violations_remaining": 2,
                "fixed_files": ["pyproject.toml", "auth.py"],
                "escalations": [{"rule_id": "37", "reason": "..."}]
            }

        """
        violations_fixed = 0
        violations_remaining = 0
        fixed_files = set()
        escalations = []

        for violation in violations:
            rule_id = violation["rule_id"]
            file_path = self.workspace / violation["file"]

            if not file_path.exists():
                logger.warning(f"  File not found: {file_path}")
                violations_remaining += 1
                continue

            # Route to appropriate fixer
            fixed = False

            if rule_id == "31":
                fixed = await self.fix_rule_31_ruff_config(file_path)
            elif rule_id == "32":
                fixed = await self.fix_rule_32_python_version(file_path)
            elif rule_id == "9":
                fixed = await self.fix_rule_9_logging(file_path)
            elif rule_id == "6":
                # Import pattern fixes - complex, escalate for now
                escalations.append({
                    "rule_id": rule_id,
                    "file": str(file_path),
                    "reason": "Import pattern fixes require manual review",
                    "violation": violation,
                })
                violations_remaining += 1
                continue
            else:
                # Complex architectural rule - escalate
                escalations.append({
                    "rule_id": rule_id,
                    "file": str(file_path),
                    "reason": f"Rule {rule_id} requires architectural changes",
                    "violation": violation,
                })
                violations_remaining += 1
                continue

            if fixed:
                violations_fixed += 1
                fixed_files.add(file_path.name)
            else:
                violations_remaining += 1

        return {
            "success": violations_remaining == 0,
            "violations_fixed": violations_fixed,
            "violations_remaining": violations_remaining,
            "fixed_files": list(fixed_files),
            "escalations": escalations,
        }

    async def process_golden_rules_task(self, task: Task) -> dict[str, Any]:
        """Process Golden Rules task: detect violations, apply fixes, commit.

        Args:
            task: Golden Rules task

        Returns:
            Task execution result

        """
        start_time = asyncio.get_event_loop().time()
        task_id = task.id

        logger.info(f"Processing Golden Rules task: {task_id}")

        # Emit task started event
        await self.event_bus.publish(
            QATaskEvent(
                task_id=task_id,
                qa_type="golden_rules",
                event_type="started",
                payload={"worker_id": self.worker_id},
            ),
        )

        try:
            # Get file paths from task (optional - can scan all)
            file_paths_str = task.metadata.get("file_paths")
            file_paths = (
                [self.workspace / fp for fp in file_paths_str]
                if file_paths_str
                else None
            )

            # Detect violations
            detection_result = await self.detect_golden_rules_violations(file_paths)

            if detection_result["total_count"] == 0:
                logger.info("  No Golden Rules violations found")
                return {
                    "status": "success",
                    "violations_fixed": 0,
                    "violations_remaining": 0,
                    "escalations": [],
                }

            # Apply fixes
            fix_result = await self.apply_golden_rules_fixes(
                detection_result["violations"],
            )

            # Commit fixes if any were made
            if fix_result["violations_fixed"] > 0:
                fixed_paths = [
                    self.workspace / f for f in fix_result["fixed_files"]
                ]
                commit_success = await self.commit_fixes(fixed_paths, task_id)

                if not commit_success:
                    await self.escalate_issue(
                        task_id,
                        "Commit failed after Golden Rules fixes",
                        {"files": fix_result["fixed_files"]},
                    )
                    return {
                        "status": "escalated",
                        "violations_fixed": fix_result["violations_fixed"],
                        "violations_remaining": fix_result["violations_remaining"],
                        "escalations": fix_result["escalations"],
                    }

            # Handle escalations
            if fix_result["escalations"]:
                for escalation in fix_result["escalations"]:
                    await self.escalate_issue(
                        task_id,
                        escalation["reason"],
                        escalation,
                    )

            # Determine final status
            status = (
                "success"
                if fix_result["violations_remaining"] == 0
                else "escalated"
            )

            # Update metrics
            self.tasks_completed += 1
            self.violations_fixed += fix_result["violations_fixed"]

            # Emit completion event
            execution_time = (asyncio.get_event_loop().time() - start_time) * 1000

            await self.event_bus.publish(
                QATaskEvent(
                    task_id=task_id,
                    qa_type="golden_rules",
                    event_type="completed",
                    payload={
                        "worker_id": self.worker_id,
                        "status": status,
                        "violations_fixed": fix_result["violations_fixed"],
                        "violations_remaining": fix_result["violations_remaining"],
                        "escalations": len(fix_result["escalations"]),
                        "execution_time_ms": int(execution_time),
                    },
                ),
            )

            logger.info(f"Golden Rules task {task_id} completed: {status}")
            logger.info(
                f"  Fixed {fix_result['violations_fixed']} violations, "
                f"{fix_result['violations_remaining']} remaining",
            )

            return {
                "status": status,
                "violations_fixed": fix_result["violations_fixed"],
                "violations_remaining": fix_result["violations_remaining"],
                "escalations": fix_result["escalations"],
                "execution_time_ms": int(execution_time),
            }

        except Exception as e:
            logger.error(f"Golden Rules task processing failed: {e}")

            await self.event_bus.publish(
                QATaskEvent(
                    task_id=task_id,
                    qa_type="golden_rules",
                    event_type="failed",
                    payload={"worker_id": self.worker_id, "error": str(e)},
                ),
            )

            return {
                "status": "failed",
                "violations_fixed": 0,
                "violations_remaining": 0,
                "escalations": [],
                "error": str(e),
            }


async def main():
    """CLI entry point for Golden Rules worker."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Golden Rules Worker - Autonomous Architectural Compliance",
    )
    parser.add_argument(
        "--worker-id",
        default="golden-rules-worker-1",
        help="Worker ID for identification",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help="Workspace directory (default: current directory)",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Task queue poll interval in seconds",
    )

    args = parser.parse_args()

    # Create and run worker
    worker = GoldenRulesWorkerCore(
        worker_id=args.worker_id, workspace=args.workspace or Path.cwd(),
    )

    await worker.run_worker_loop(poll_interval=args.poll_interval)


if __name__ == "__main__":
    asyncio.run(main())
