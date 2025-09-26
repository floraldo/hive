"""
Bridge to integrate inspect_run.py with the AI reviewer
"""

import sys
import subprocess
import json
from pathlib import Path
from typing import Dict, Any, Optional

from hive_logging import get_logger

logger = get_logger(__name__)


class InspectorBridge:
    """Bridge to run inspect_run.py and integrate results with AI review"""

    def __init__(self):
        """Initialize inspector bridge"""
        # Find the inspect_run.py script
        # Use resolve() to get absolute path on Windows
        self.inspect_script = (Path(__file__).parent.parent.parent.parent.parent / "scripts" / "inspect_run.py").resolve()

        if not self.inspect_script.exists():
            logger.warning(f"inspect_run.py not found at {self.inspect_script}")

    def inspect_task_run(self, task_id: str, run_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Run objective analysis on a task using inspect_run.py

        Args:
            task_id: Task identifier
            run_id: Optional run identifier

        Returns:
            Dictionary containing objective analysis results
        """
        if not self.inspect_script.exists():
            return {
                "error": "inspect_run.py script not found",
                "task_id": task_id,
                "metrics": {},
                "files": {},
                "checks": {}
            }

        try:
            # Build command to run inspect_run.py
            cmd = [sys.executable, str(self.inspect_script)]

            if run_id:
                cmd.extend(["--run-id", run_id])
            else:
                # Use task_id as run_id for now - this should be improved
                # In a real system, we'd need to map task_id to run_id
                cmd.extend(["--run-id", task_id])

            # Add output format
            cmd.extend(["--output", "json"])

            # Run the script
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60  # 1 minute timeout
            )

            if result.returncode == 0:
                try:
                    # Parse JSON output
                    analysis = json.loads(result.stdout)
                    logger.info(f"Successfully ran objective analysis for task {task_id}")
                    return analysis
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse inspect_run.py output: {e}")
                    return self._create_error_response(task_id, f"JSON decode error: {e}")
            else:
                logger.error(f"inspect_run.py failed with code {result.returncode}: {result.stderr}")
                return self._create_error_response(task_id, f"Script error: {result.stderr}")

        except subprocess.TimeoutExpired:
            logger.error(f"inspect_run.py timed out for task {task_id}")
            return self._create_error_response(task_id, "Analysis timed out")
        except Exception as e:
            logger.error(f"Error running inspect_run.py for task {task_id}: {e}")
            return self._create_error_response(task_id, str(e))

    def _create_error_response(self, task_id: str, error_msg: str) -> Dict[str, Any]:
        """Create standardized error response"""
        return {
            "error": error_msg,
            "task_id": task_id,
            "timestamp": None,
            "files": {},
            "metrics": {
                "code_quality": 0,
                "test_coverage": 0,
                "documentation": 0,
                "complexity": 0
            },
            "checks": {
                "syntax_valid": False,
                "tests_exist": False,
                "documentation_exists": False
            },
            "issues": [{"type": "analysis_error", "message": error_msg}],
            "summary": {
                "total_files": 0,
                "total_lines": 0,
                "total_issues": 1
            }
        }

    def extract_code_quality_metrics(self, analysis: Dict[str, Any]) -> Dict[str, float]:
        """
        Extract standardized quality metrics from analysis

        Args:
            analysis: Raw analysis from inspect_run.py

        Returns:
            Dictionary of normalized quality scores (0-100)
        """
        metrics = {
            "code_quality": 0.0,
            "test_coverage": 0.0,
            "documentation": 0.0,
            "security": 0.0,
            "architecture": 0.0
        }

        if "error" in analysis:
            return metrics

        try:
            # Extract metrics from analysis
            analysis_metrics = analysis.get("metrics", {})
            analysis_checks = analysis.get("checks", {})
            analysis_issues = analysis.get("issues", [])

            # Code quality based on issues and checks
            total_files = analysis.get("summary", {}).get("total_files", 1)
            total_issues = len(analysis_issues)

            if total_files > 0:
                # Base score reduced by issues per file
                issues_per_file = total_issues / total_files
                metrics["code_quality"] = max(0, 100 - (issues_per_file * 10))

            # Test coverage
            if "test_coverage" in analysis_metrics:
                metrics["test_coverage"] = float(analysis_metrics["test_coverage"])
            elif analysis_checks.get("tests_exist", False):
                metrics["test_coverage"] = 75.0  # Assume reasonable coverage if tests exist
            else:
                metrics["test_coverage"] = 0.0

            # Documentation
            if analysis_checks.get("documentation_exists", False):
                metrics["documentation"] = 80.0
            else:
                metrics["documentation"] = 20.0

            # Security - check for common issues
            security_issues = [i for i in analysis_issues if "security" in i.get("type", "").lower()]
            metrics["security"] = max(0, 100 - (len(security_issues) * 20))

            # Architecture - based on complexity and structure
            complexity = analysis_metrics.get("complexity", 0)
            if complexity > 0:
                # Lower complexity is better
                metrics["architecture"] = max(0, 100 - (complexity * 2))
            else:
                metrics["architecture"] = 70.0  # Default for simple code

            logger.debug(f"Extracted metrics: {metrics}")
            return metrics

        except Exception as e:
            logger.error(f"Error extracting metrics: {e}")
            return metrics

    def get_review_summary(self, analysis: Dict[str, Any]) -> str:
        """
        Generate a human-readable summary of the objective analysis

        Args:
            analysis: Analysis results from inspect_run.py

        Returns:
            String summary for review report
        """
        if "error" in analysis:
            return f"Analysis failed: {analysis['error']}"

        try:
            summary_parts = []

            # File summary
            file_count = analysis.get("summary", {}).get("total_files", 0)
            line_count = analysis.get("summary", {}).get("total_lines", 0)
            summary_parts.append(f"Analyzed {file_count} files with {line_count} total lines.")

            # Issues summary
            issues = analysis.get("issues", [])
            if issues:
                issue_types = {}
                for issue in issues:
                    issue_type = issue.get("type", "unknown")
                    issue_types[issue_type] = issue_types.get(issue_type, 0) + 1

                issue_summary = ", ".join([f"{count} {type}" for type, count in issue_types.items()])
                summary_parts.append(f"Found issues: {issue_summary}.")
            else:
                summary_parts.append("No issues detected.")

            # Checks summary
            checks = analysis.get("checks", {})
            passed_checks = [check for check, passed in checks.items() if passed]
            if passed_checks:
                summary_parts.append(f"Passed checks: {', '.join(passed_checks)}.")

            return " ".join(summary_parts)

        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return "Could not generate analysis summary."