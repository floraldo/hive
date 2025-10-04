#!/usr/bin/env python3
# Security: subprocess calls in this module use system tools (git) with hardcoded,
# trusted arguments only. No user input is passed to subprocess.

"""ReviewerCore - Queen's Internal Code Review Module
Provides quality assessment and iterative refinement capabilities
"""

import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hive_logging import get_logger

logger = get_logger(__name__)


class ReviewerCore:
    """Internal reviewer for the Queen to assess task completion quality"""

    def __init__(self, hive_root: Path):
        self.root = hive_root
        self.hive_dir = self.root / "hive"
        self.tasks_dir = self.hive_dir / "tasks"
        self.results_dir = self.hive_dir / "results"

    def review_task_output(self, task: dict[str, Any], worktree_path: Path) -> dict[str, Any]:
        """Review the output of a completed task

        Returns:
            {
                "passed": bool,
                "score": int (0-100),
                "feedback": str,
                "improvements": [list of specific improvements needed],
                "strengths": [list of things done well]
            }

        """
        task["id"]
        acceptance_criteria = task.get("acceptance", [])
        task.get("instruction", "")

        # Initialize review result
        review = {
            "passed": False,
            "score": 0,
            "feedback": "",
            "improvements": [],
            "strengths": [],
            "timestamp": datetime.now(UTC).isoformat(),
        }

        # Check if worktree exists
        if not worktree_path.exists():
            review["feedback"] = "Worktree does not exist - cannot review"
            return review

        # Get list of changed files
        changed_files = self._get_changed_files(worktree_path)

        # Basic checks
        checks_passed = 0
        total_checks = 0

        # Check 1: Were any files created/modified?
        total_checks += 1
        if changed_files:
            checks_passed += 1
            review["strengths"].append(f"Created/modified {len(changed_files)} files")
        else:
            review["improvements"].append("No files were created or modified")

        # Check 2: Review each acceptance criterion
        for criterion in acceptance_criteria:
            total_checks += 1
            if self._check_criterion(criterion, worktree_path, changed_files):
                checks_passed += 1
                review["strengths"].append(f"Met: {criterion[:50]}...")
            else:
                review["improvements"].append(f"Not met: {criterion[:50]}...")

        # Check 3: Look for tests (if applicable)
        if any(tag in task.get("tags", []) for tag in ["testing", "backend", "frontend"]):
            total_checks += 1
            test_files = [f for f in changed_files if "test" in f.lower()]
            if test_files:
                checks_passed += 1
                review["strengths"].append(f"Created {len(test_files)} test file(s)")
            else:
                review["improvements"].append("No test files created")

        # Check 4: Code quality basics
        python_files = [f for f in changed_files if f.endswith(".py")]
        if python_files:
            total_checks += 1
            quality_issues = self._check_code_quality(worktree_path, python_files)
            if not quality_issues:
                checks_passed += 1
                review["strengths"].append("Code follows basic quality standards")
            else:
                review["improvements"].extend(quality_issues)

        # Calculate score
        if total_checks > 0:
            review["score"] = int((checks_passed / total_checks) * 100)

        # Determine if passed (threshold: 70%)
        review["passed"] = review["score"] >= 70

        # Generate overall feedback
        if review["passed"]:
            review["feedback"] = f"Task completed successfully with score {review['score']}%. "
            if review["improvements"]:
                review["feedback"] += "Minor improvements suggested but not required."
        else:
            review["feedback"] = f"Task needs refinement (score: {review['score']}%). "
            review["feedback"] += f"Address {len(review['improvements'])} issues before completion."

        return review

    def _get_changed_files(self, worktree_path: Path) -> list[str]:
        """Get list of files changed in the worktree"""
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD"],
                check=False, cwd=str(worktree_path),
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                files = result.stdout.strip().split("\n")
                return [f for f in files if f]

            # Also check for untracked files
            result = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard"],
                check=False, cwd=str(worktree_path),
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                files = result.stdout.strip().split("\n")
                return [f for f in files if f]

        except Exception as e:
            logger.error(f"Error getting changed files: {e}")

        return []

    def _check_criterion(self, criterion: str, worktree_path: Path, changed_files: list[str]) -> bool:
        """Check if a specific acceptance criterion is met"""
        criterion_lower = criterion.lower()

        # Check for file creation criteria
        if "create" in criterion_lower or "file:" in criterion_lower:
            # Extract filename if mentioned
            for file in changed_files:
                if file.lower() in criterion_lower:
                    return True

        # Check for specific patterns
        if "test" in criterion_lower and any("test" in f.lower() for f in changed_files):
            return True

        if "dockerfile" in criterion_lower and any("dockerfile" in f.lower() for f in changed_files):
            return True

        # Default: assume met if we have changes (basic heuristic)
        return len(changed_files) > 0

    def _check_code_quality(self, worktree_path: Path, python_files: list[str]) -> list[str]:
        """Basic code quality checks for Python files"""
        issues = []

        for file in python_files:
            file_path = worktree_path / file
            if not file_path.exists():
                continue

            try:
                with open(file_path) as f:
                    content = f.read()

                # Check for basic issues
                if "TODO" in content or "FIXME" in content:
                    issues.append(f"{file}: Contains TODO/FIXME comments")

                if "pass  # Implement" in content:
                    issues.append(f"{file}: Contains unimplemented placeholders")

                # Check if main files have proper structure
                if not file.startswith("test_") and "__main__" not in content and "def " not in content:
                    issues.append(f"{file}: No functions defined")

            except Exception as e:
                issues.append(f"{file}: Could not read for quality check ({e})")

        return issues

    def generate_refinement_task(self, original_task: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
        """Generate a refinement task based on review feedback"""
        task_id = original_task["id"]
        iteration = original_task.get("iteration", 0) + 1

        refinement_task = {
            "id": f"{task_id}-r{iteration}",
            "title": f"Refinement: {original_task.get('title', task_id)}",
            "description": f"Refinement iteration {iteration} based on review feedback",
            "instruction": self._generate_refinement_instructions(original_task, review),
            "acceptance": review["improvements"],  # The improvements become the new acceptance criteria
            "priority": "P0",  # High priority for refinements
            "risk": "low",
            "status": "queued",
            "tags": original_task.get("tags", []),
            "parent_task": task_id,
            "iteration": iteration,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }

        return refinement_task

    def _generate_refinement_instructions(self, original_task: dict[str, Any], review: dict[str, Any]) -> str:
        """Generate specific instructions for refinement"""
        instructions = f"""Continue work on task '{original_task["id"]}' from the existing branch.

ORIGINAL TASK:
{original_task.get("description", "")}

REVIEW FEEDBACK (Score: {review["score"]}%):
{review["feedback"]}

SPECIFIC IMPROVEMENTS NEEDED:
"""
        for i, improvement in enumerate(review["improvements"], 1):
            instructions += f"\n{i}. {improvement}"

        instructions += """

WHAT WAS DONE WELL (preserve these):
"""
        for strength in review["strengths"]:
            instructions += f"\n- {strength}"

        instructions += """

IMPORTANT: Build upon the existing work in the branch. Do not start from scratch.
Focus on addressing the specific improvements while maintaining what was done well.
"""

        return instructions
