#!/usr/bin/env python3
"""
Run Inspection Tool - Objective Code Analysis for Intelligent Review

This script provides objective analysis of a run's output to support
the Queen's intelligent decision-making during the review phase.
"""

import sys
import json
import subprocess
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

# Add package paths
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "hive-core-db" / "src"))
import hive_core_db


class RunInspector:
    """Performs objective analysis of run results"""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.run_data = None
        self.task_data = None
        self.report = {
            "run_id": run_id,
            "timestamp": datetime.utcnow().isoformat(),
            "files": {},
            "metrics": {},
            "checks": {},
            "issues": [],
            "summary": {}
        }

    def load_run_data(self) -> bool:
        """Load run and task data from database"""
        self.run_data = hive_core_db.get_run(self.run_id)
        if not self.run_data:
            self.report["error"] = f"Run {self.run_id} not found"
            return False

        task_id = self.run_data.get("task_id")
        self.task_data = hive_core_db.get_task(task_id)
        if not self.task_data:
            self.report["error"] = f"Task {task_id} not found"
            return False

        self.report["task_id"] = task_id
        self.report["task_title"] = self.task_data.get("title", "Unknown")
        return True

    def analyze_files(self):
        """Analyze files created or modified by the run"""
        result_data = self.run_data.get("result_data")
        if isinstance(result_data, str):
            try:
                result_data = json.loads(result_data)
            except json.JSONDecodeError:
                result_data = {}

        files_info = result_data.get("files", {})
        created_files = files_info.get("created", [])
        modified_files = files_info.get("modified", [])

        all_files = created_files + modified_files

        for file_path in all_files:
            file_analysis = self.analyze_single_file(file_path)
            if file_analysis:
                self.report["files"][file_path] = file_analysis

        # Summary metrics
        self.report["metrics"]["files_created"] = len(created_files)
        self.report["metrics"]["files_modified"] = len(modified_files)
        self.report["metrics"]["total_files"] = len(all_files)

    def analyze_single_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Analyze a single file"""
        path = Path(file_path)

        if not path.exists():
            return {"exists": False, "error": "File not found"}

        analysis = {
            "exists": True,
            "size": path.stat().st_size,
            "extension": path.suffix,
            "is_test": "test" in path.name.lower(),
        }

        # Count lines for text files
        if path.suffix in [".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs", ".cpp", ".c", ".h"]:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    analysis["lines"] = len(lines)
                    analysis["non_empty_lines"] = len([l for l in lines if l.strip()])

                    # Check for common patterns
                    content = "".join(lines)
                    analysis["has_todo"] = "TODO" in content or "FIXME" in content
                    analysis["has_imports"] = any(["import " in l or "from " in l for l in lines[:20]])

                    # Python-specific checks
                    if path.suffix == ".py":
                        analysis["has_main"] = 'if __name__ == "__main__"' in content
                        analysis["has_class"] = "class " in content
                        analysis["has_function"] = "def " in content
                        analysis["has_docstring"] = '"""' in content or "'''" in content

            except Exception as e:
                analysis["read_error"] = str(e)

        return analysis

    def run_linter(self):
        """Run linter on Python files"""
        python_files = [f for f in self.report["files"].keys() if f.endswith(".py")]

        if not python_files:
            self.report["checks"]["linter"] = {"status": "skipped", "reason": "No Python files"}
            return

        linter_results = []
        for file_path in python_files:
            if Path(file_path).exists():
                try:
                    # Try ruff first (faster)
                    result = subprocess.run(
                        ["ruff", "check", file_path, "--output-format", "json"],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )

                    if result.returncode == 0:
                        linter_results.append({
                            "file": file_path,
                            "status": "clean",
                            "issues": []
                        })
                    else:
                        try:
                            issues = json.loads(result.stdout) if result.stdout else []
                            linter_results.append({
                                "file": file_path,
                                "status": "issues",
                                "issues": issues,
                                "issue_count": len(issues)
                            })
                            self.report["issues"].extend([
                                f"Linter: {issue.get('message', 'Unknown issue')} at {file_path}:{issue.get('location', {}).get('row', '?')}"
                                for issue in issues[:5]  # Limit to first 5 issues
                            ])
                        except json.JSONDecodeError:
                            # Fallback to text output
                            linter_results.append({
                                "file": file_path,
                                "status": "error",
                                "output": result.stdout[:500]
                            })

                except (subprocess.TimeoutExpired, FileNotFoundError):
                    # Ruff not available, try basic Python syntax check
                    try:
                        result = subprocess.run(
                            ["python", "-m", "py_compile", file_path],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        if result.returncode == 0:
                            linter_results.append({
                                "file": file_path,
                                "status": "syntax_ok"
                            })
                        else:
                            linter_results.append({
                                "file": file_path,
                                "status": "syntax_error",
                                "error": result.stderr[:200]
                            })
                            self.report["issues"].append(f"Syntax error in {file_path}")
                    except Exception as e:
                        linter_results.append({
                            "file": file_path,
                            "status": "check_failed",
                            "error": str(e)
                        })

        self.report["checks"]["linter"] = {
            "status": "completed",
            "files_checked": len(linter_results),
            "clean_files": len([r for r in linter_results if r["status"] == "clean"]),
            "files_with_issues": len([r for r in linter_results if r["status"] == "issues"]),
            "results": linter_results
        }

    def check_tests(self):
        """Check for test files and test coverage"""
        test_files = [f for f in self.report["files"].keys()
                     if "test" in Path(f).name.lower() or Path(f).parent.name in ["tests", "test", "__tests__"]]

        code_files = [f for f in self.report["files"].keys()
                      if f.endswith((".py", ".js", ".ts", ".java", ".go", ".rs"))
                      and not any(t in Path(f).name.lower() for t in ["test", "spec"])]

        self.report["checks"]["tests"] = {
            "test_files_found": len(test_files),
            "test_files": test_files,
            "code_files": len(code_files),
            "test_coverage_ratio": len(test_files) / max(len(code_files), 1)
        }

        if len(test_files) == 0 and len(code_files) > 0:
            self.report["issues"].append("No test files found for code changes")

    def generate_summary(self):
        """Generate summary and recommendations"""
        # Quality score (0-100)
        score = 100

        # Deduct points for issues
        if self.report["metrics"]["total_files"] == 0:
            score -= 50  # No files created/modified
            self.report["issues"].append("No files were created or modified")

        linter_checks = self.report.get("checks", {}).get("linter", {})
        if linter_checks.get("files_with_issues", 0) > 0:
            score -= min(30, linter_checks["files_with_issues"] * 10)

        test_checks = self.report.get("checks", {}).get("tests", {})
        if test_checks.get("test_coverage_ratio", 0) < 0.5 and self.report["metrics"]["total_files"] > 0:
            score -= 20

        # Check for TODOs
        todo_count = sum(1 for f in self.report["files"].values() if f.get("has_todo"))
        if todo_count > 0:
            score -= min(10, todo_count * 5)
            self.report["issues"].append(f"Found {todo_count} file(s) with TODO/FIXME comments")

        self.report["summary"] = {
            "quality_score": max(0, score),
            "total_issues": len(self.report["issues"]),
            "recommendation": self.get_recommendation(score),
            "confidence": "high" if self.report["metrics"]["total_files"] > 0 else "low"
        }

    def get_recommendation(self, score: int) -> str:
        """Get recommendation based on quality score"""
        if score >= 80:
            return "approve"  # Good quality, ready to proceed
        elif score >= 60:
            return "conditional"  # Needs minor fixes
        else:
            return "rework"  # Needs significant improvement

    def inspect(self) -> Dict[str, Any]:
        """Run full inspection"""
        # Initialize database
        hive_core_db.init_db()

        # Load run data
        if not self.load_run_data():
            return self.report

        # Perform analyses
        self.analyze_files()
        self.run_linter()
        self.check_tests()
        self.generate_summary()

        return self.report


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Inspect a run for quality analysis")
    parser.add_argument("--run-id", required=True, help="Run ID to inspect")
    parser.add_argument("--output", choices=["json", "summary"], default="json",
                       help="Output format")

    args = parser.parse_args()

    inspector = RunInspector(args.run_id)
    report = inspector.inspect()

    if args.output == "json":
        print(json.dumps(report, indent=2))
    else:
        # Summary output
        print(f"Run Inspection Report: {args.run_id}")
        print("=" * 50)
        print(f"Task: {report.get('task_title', 'Unknown')}")
        print(f"Files Changed: {report.get('metrics', {}).get('total_files', 0)}")
        print(f"Quality Score: {report.get('summary', {}).get('quality_score', 0)}/100")
        print(f"Issues Found: {report.get('summary', {}).get('total_issues', 0)}")
        print(f"Recommendation: {report.get('summary', {}).get('recommendation', 'unknown').upper()}")

        if report.get("issues"):
            print("\nIssues:")
            for issue in report["issues"][:5]:
                print(f"  - {issue}")

    # Exit with appropriate code
    recommendation = report.get("summary", {}).get("recommendation", "unknown")
    sys.exit(0 if recommendation in ["approve", "conditional"] else 1)


if __name__ == "__main__":
    main()