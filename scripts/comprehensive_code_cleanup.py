#!/usr/bin/env python3
"""
Comprehensive Code Cleanup Tool for Hive Platform V4.5

Identifies and reports various code quality issues:
- TODOs and technical debt comments
- Global variables and singletons
- Import issues (function-level imports, wildcard imports)
- SQL injection risks
- Async resource management issues
"""

import ast
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass
from datetime import datetime
from collections import defaultdict

from hive_logging import get_logger

logger = get_logger(__name__)


@dataclass
class CodeIssue:
    """Represents a code quality issue"""
    file_path: Path
    line_number: int
    issue_type: str
    category: str
    description: str
    severity: str  # high, medium, low
    suggested_fix: str = ""


class ComprehensiveCodeAnalyzer:
    """Analyzes code for various quality issues"""

    def __init__(self, hive_root: Path = None):
        self.hive_root = hive_root or Path.cwd()
        self.issues = []
        self.stats = defaultdict(int)

    def find_python_files(self) -> List[Path]:
        """Find all Python files in packages and apps"""
        python_files = []

        for pattern in ["packages/**/*.py", "apps/**/*.py", "scripts/**/*.py"]:
            python_files.extend(self.hive_root.glob(pattern))

        # Exclude certain patterns
        filtered_files = []
        for file_path in python_files:
            path_str = str(file_path).lower()
            if not any(exclude in path_str for exclude in ["__pycache__", "archive", "legacy", ".backup", ".venv"]):
                filtered_files.append(file_path)

        return filtered_files

    def analyze_file(self, file_path: Path) -> List[CodeIssue]:
        """Analyze a single file for various issues"""
        issues = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')

            # Check for TODOs and technical debt
            issues.extend(self._check_todos(file_path, lines))

            # Check for global variables
            issues.extend(self._check_globals(file_path, lines))

            # Check for SQL injection risks
            issues.extend(self._check_sql_injection(file_path, lines))

            # Check for import issues
            issues.extend(self._check_imports(file_path, content))

            # Check for async issues
            issues.extend(self._check_async_issues(file_path, lines))

        except Exception as e:
            logger.error(f"Error analyzing {file_path}: {e}")

        return issues

    def _check_todos(self, file_path: Path, lines: List[str]) -> List[CodeIssue]:
        """Check for TODO comments and technical debt markers"""
        issues = []
        patterns = {
            'TODO': ('todo', 'medium'),
            'FIXME': ('fixme', 'high'),
            'XXX': ('xxx', 'high'),
            'HACK': ('hack', 'high'),
            'BUG': ('bug', 'high'),
            'OPTIMIZE': ('optimize', 'medium'),
            'REFACTOR': ('refactor', 'medium'),
        }

        for i, line in enumerate(lines, 1):
            for pattern, (issue_type, severity) in patterns.items():
                if pattern in line:
                    # Extract the comment text
                    comment_match = re.search(f'{pattern}:?\\s*(.*)', line, re.IGNORECASE)
                    comment = comment_match.group(1) if comment_match else ""

                    issues.append(CodeIssue(
                        file_path=file_path,
                        line_number=i,
                        issue_type=issue_type,
                        category="technical_debt",
                        description=f"{pattern} comment: {comment.strip()}",
                        severity=severity,
                        suggested_fix="Address the technical debt or remove if obsolete"
                    ))

        return issues

    def _check_globals(self, file_path: Path, lines: List[str]) -> List[CodeIssue]:
        """Check for global variables and singleton patterns"""
        issues = []
        global_pattern = re.compile(r'^\s*global\s+(\w+)')
        singleton_patterns = [
            re.compile(r'_instance\s*=\s*None'),
            re.compile(r'__instance\s*=\s*None'),
            re.compile(r'@singleton'),
            re.compile(r'class.*\(.*Singleton.*\)'),
        ]

        for i, line in enumerate(lines, 1):
            # Check for global keyword
            match = global_pattern.match(line)
            if match:
                var_name = match.group(1)
                issues.append(CodeIssue(
                    file_path=file_path,
                    line_number=i,
                    issue_type="global_variable",
                    category="global_state",
                    description=f"Global variable: {var_name}",
                    severity="medium",
                    suggested_fix="Use dependency injection or context managers instead"
                ))

            # Check for singleton patterns
            for pattern in singleton_patterns:
                if pattern.search(line):
                    issues.append(CodeIssue(
                        file_path=file_path,
                        line_number=i,
                        issue_type="singleton_pattern",
                        category="global_state",
                        description="Singleton pattern detected",
                        severity="medium",
                        suggested_fix="Convert to dependency injection or service registry"
                    ))

        return issues

    def _check_sql_injection(self, file_path: Path, lines: List[str]) -> List[CodeIssue]:
        """Check for potential SQL injection vulnerabilities"""
        issues = []
        risky_patterns = [
            (re.compile(r'execute\(f["\']'), "f-string in SQL execute"),
            (re.compile(r'execute\([^,)]*\.format\('), "format() in SQL execute"),
            (re.compile(r'execute\([^,)]*%'), "% formatting in SQL execute"),
            (re.compile(r'executescript\(f["\']'), "f-string in executescript"),
            (re.compile(r'f["\'].*(?:SELECT|INSERT|UPDATE|DELETE|DROP|CREATE).*{'), "f-string with SQL keywords"),
        ]

        for i, line in enumerate(lines, 1):
            for pattern, description in risky_patterns:
                if pattern.search(line):
                    issues.append(CodeIssue(
                        file_path=file_path,
                        line_number=i,
                        issue_type="sql_injection_risk",
                        category="security",
                        description=description,
                        severity="high",
                        suggested_fix="Use parameterized queries with ? placeholders"
                    ))

        return issues

    def _check_imports(self, file_path: Path, content: str) -> List[CodeIssue]:
        """Check for import issues"""
        issues = []

        try:
            tree = ast.parse(content)

            # Check for wildcard imports
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        if alias.name == '*':
                            issues.append(CodeIssue(
                                file_path=file_path,
                                line_number=node.lineno,
                                issue_type="wildcard_import",
                                category="imports",
                                description=f"Wildcard import from {node.module}",
                                severity="low",
                                suggested_fix="Import specific names instead"
                            ))

                # Check for imports inside functions
                if isinstance(node, ast.FunctionDef):
                    for child in ast.walk(node):
                        if isinstance(child, (ast.Import, ast.ImportFrom)):
                            issues.append(CodeIssue(
                                file_path=file_path,
                                line_number=child.lineno,
                                issue_type="function_level_import",
                                category="imports",
                                description=f"Import inside function {node.name}",
                                severity="low",
                                suggested_fix="Move import to module level for better performance"
                            ))
                            break

        except SyntaxError:
            pass  # Skip files with syntax errors

        return issues

    def _check_async_issues(self, file_path: Path, lines: List[str]) -> List[CodeIssue]:
        """Check for async resource management issues"""
        issues = []

        # Pattern for untracked tasks
        untracked_task = re.compile(r'asyncio\.create_task\([^)]+\)(?!\s*=)')

        # Pattern for missing async context manager
        async_resource = re.compile(r'await\s+.*\.(connect|open|acquire)\(')

        for i, line in enumerate(lines, 1):
            # Check for untracked tasks
            if untracked_task.search(line):
                issues.append(CodeIssue(
                    file_path=file_path,
                    line_number=i,
                    issue_type="untracked_async_task",
                    category="async",
                    description="Async task created without storing reference",
                    severity="high",
                    suggested_fix="Store task reference: task = asyncio.create_task(...)"
                ))

            # Check for resources without context manager
            if async_resource.search(line) and 'async with' not in line:
                issues.append(CodeIssue(
                    file_path=file_path,
                    line_number=i,
                    issue_type="missing_async_context_manager",
                    category="async",
                    description="Async resource opened without context manager",
                    severity="medium",
                    suggested_fix="Use async with statement for resource management"
                ))

        return issues

    def analyze_all(self) -> Tuple[int, Dict[str, int]]:
        """Analyze all Python files"""
        python_files = self.find_python_files()
        logger.info(f"Analyzing {len(python_files)} Python files")

        for file_path in python_files:
            file_issues = self.analyze_file(file_path)
            self.issues.extend(file_issues)

            # Update statistics
            for issue in file_issues:
                self.stats[issue.category] += 1
                self.stats[f"{issue.category}_{issue.severity}"] += 1

        self.stats['total'] = len(self.issues)
        self.stats['files_analyzed'] = len(python_files)

        return len(python_files), dict(self.stats)

    def generate_report(self) -> str:
        """Generate comprehensive cleanup report"""
        files_analyzed, stats = self.analyze_all()

        # Group issues by category and severity
        by_category = defaultdict(list)
        for issue in self.issues:
            by_category[issue.category].append(issue)

        # Sort issues by severity
        severity_order = {'high': 0, 'medium': 1, 'low': 2}

        report = f"""
# Comprehensive Code Cleanup Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Executive Summary
- Files analyzed: {stats['files_analyzed']}
- Total issues found: {stats['total']}
- High severity: {sum(stats.get(f'{cat}_high', 0) for cat in by_category.keys())}
- Medium severity: {sum(stats.get(f'{cat}_medium', 0) for cat in by_category.keys())}
- Low severity: {sum(stats.get(f'{cat}_low', 0) for cat in by_category.keys())}

## Issues by Category
"""

        for category, issues in sorted(by_category.items()):
            sorted_issues = sorted(issues, key=lambda x: (severity_order.get(x.severity, 3), x.file_path, x.line_number))

            report += f"\n### {category.replace('_', ' ').title()} ({len(issues)} issues)\n"

            # Show top issues by severity
            high_issues = [i for i in sorted_issues if i.severity == 'high']
            if high_issues:
                report += f"\n#### High Severity ({len(high_issues)} issues)\n"
                for issue in high_issues[:5]:
                    rel_path = issue.file_path.relative_to(self.hive_root)
                    report += f"- **{rel_path}:{issue.line_number}**\n"
                    report += f"  - {issue.description}\n"
                    report += f"  - Fix: {issue.suggested_fix}\n"

                if len(high_issues) > 5:
                    report += f"\n... and {len(high_issues) - 5} more high severity {category} issues\n"

        # Files with most issues
        file_counts = defaultdict(int)
        for issue in self.issues:
            file_counts[issue.file_path] += 1

        report += "\n## Files with Most Issues\n"
        for file_path, count in sorted(file_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            rel_path = file_path.relative_to(self.hive_root)
            report += f"- {rel_path}: {count} issues\n"

        # Recommendations
        report += f"""
## Priority Recommendations

1. **Security (High Priority)**
   - Fix {stats.get('security_high', 0)} SQL injection risks immediately
   - Review and parameterize all SQL queries

2. **Async Resource Management**
   - Fix {stats.get('async_high', 0)} untracked async tasks
   - Add {stats.get('async_medium', 0)} missing context managers

3. **Technical Debt**
   - Address {stats.get('technical_debt_high', 0)} high-priority TODOs/FIXMEs
   - Plan refactoring for {stats.get('technical_debt_medium', 0)} medium-priority items

4. **Global State**
   - Remove {stats.get('global_state', 0)} global variables and singletons
   - Implement dependency injection patterns

5. **Code Quality**
   - Move {stats.get('imports_low', 0)} function-level imports to module level
   - Replace wildcard imports with specific imports
"""

        return report

    def export_issues_json(self, output_path: Path) -> None:
        """Export issues to JSON for further processing"""
        import json

        issues_data = []
        for issue in self.issues:
            issues_data.append({
                'file': str(issue.file_path.relative_to(self.hive_root)),
                'line': issue.line_number,
                'type': issue.issue_type,
                'category': issue.category,
                'description': issue.description,
                'severity': issue.severity,
                'fix': issue.suggested_fix
            })

        with open(output_path, 'w') as f:
            json.dump(issues_data, f, indent=2)

        logger.info(f"Exported {len(issues_data)} issues to {output_path}")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Comprehensive code cleanup analyzer")
    parser.add_argument("--report", action="store_true", help="Generate full report")
    parser.add_argument("--json", type=Path, help="Export issues to JSON file")
    parser.add_argument("--category", help="Filter by category (technical_debt, security, async, imports, global_state)")
    parser.add_argument("--severity", help="Filter by severity (high, medium, low)")

    args = parser.parse_args()

    analyzer = ComprehensiveCodeAnalyzer()

    if args.report:
        print(analyzer.generate_report())

    if args.json:
        analyzer.analyze_all()
        analyzer.export_issues_json(args.json)
        print(f"Issues exported to {args.json}")

    if not args.report and not args.json:
        # Quick summary
        files_analyzed, stats = analyzer.analyze_all()
        print(f"\nQuick Summary:")
        print(f"- Files analyzed: {stats['files_analyzed']}")
        print(f"- Total issues: {stats['total']}")
        print(f"- High severity: {sum(v for k, v in stats.items() if k.endswith('_high'))}")
        print(f"- Categories: {', '.join(k for k in stats.keys() if not k.endswith('_high') and not k.endswith('_medium') and not k.endswith('_low') and k not in ['total', 'files_analyzed'])}")
        print("\nRun with --report for detailed analysis or --json <file> to export issues")


if __name__ == "__main__":
    main()