#!/usr/bin/env python3
"""Performance audit script to identify optimization opportunities."""

import ast
import re
from pathlib import Path


def check_n_plus_one_queries(file_path: Path) -> list[str]:
    """Check for potential N+1 query patterns."""
    issues = []

    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    # Look for loops with database queries
    patterns = [
        r"for.*in.*:\s*\n.*(?:SELECT|INSERT|UPDATE|DELETE)",
        r"while.*:\s*\n.*(?:SELECT|INSERT|UPDATE|DELETE)",
        r'\.execute\(["\']SELECT.*["\'].*\).*\n.*for',
    ]

    for pattern in patterns:
        if re.search(pattern, content, re.MULTILINE | re.IGNORECASE):
            issues.append(f"Potential N+1 query pattern in {file_path}")

    return issues


def check_memory_leaks(file_path: Path) -> list[str]:
    """Check for potential memory leaks."""
    issues = []

    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    # Check for growing lists without cleanup
    if ".append(" in content:
        # Check if there's corresponding cleanup
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if ".append(" in line and not any(cleanup in content for cleanup in [".clear()", ".pop()", "del ", "= []"]):
                # Check if it's in a class that might accumulate
                if i > 0 and "self." in line:
                    issues.append(f"Potential memory leak (growing list) in {file_path}:{i + 1}")

    # Check for unclosed resources
    patterns = [
        (r"open\(", "close()"),
        (r"connect\(", "close()"),
        (r"Session\(", "close()"),
    ]

    for open_pattern, close_pattern in patterns:
        if re.search(open_pattern, content) and close_pattern not in content and "with " not in content:
            issues.append(f"Potential unclosed resource in {file_path}")

    return issues


def check_inefficient_operations(file_path: Path) -> list[str]:
    """Check for inefficient operations."""
    issues = []

    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content)

        class InefficiencyVisitor(ast.NodeVisitor):
            def __init__(self):
                self.issues = []

            def visit_For(self, node):
                # Check for inefficient string concatenation in loops
                for child in ast.walk(node):
                    if isinstance(child, ast.AugAssign) and isinstance(child.op, ast.Add):
                        if isinstance(child.target, ast.Name):
                            self.issues.append(f"String concatenation in loop at line {child.lineno}")

                # Check for repeated function calls in loop condition
                if isinstance(node.iter, ast.Call):
                    if isinstance(node.iter.func, ast.Name) and node.iter.func.id in ["range", "len"]:
                        # This is fine
                        pass
                    else:
                        self.issues.append(f"Function call in loop condition at line {node.lineno}")

                self.generic_visit(node)

            def visit_ListComp(self, node):
                # Check for nested list comprehensions
                for child in ast.walk(node):
                    if isinstance(child, ast.ListComp) and child != node:
                        self.issues.append(f"Nested list comprehension at line {node.lineno}")

                self.generic_visit(node)

        visitor = InefficiencyVisitor()
        visitor.visit(tree)

        for issue in visitor.issues:
            issues.append(f"{file_path}: {issue}")

    except Exception:
        # Parsing errors, skip file
        pass

    return issues


def check_missing_indexes(file_path: Path) -> list[str]:
    """Check for queries that might benefit from indexes."""
    issues = []

    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    # Look for WHERE clauses without corresponding indexes
    where_patterns = re.findall(r"WHERE\s+(\w+)\s*=", content, re.IGNORECASE)

    # Check if these columns have indexes
    for column in where_patterns:
        if column not in ["id", "task_id", "status", "priority"]:  # Known indexed columns
            if f"idx_{column}" not in content and f"INDEX.*{column}" not in content:
                issues.append(f"Column '{column}' used in WHERE clause might need index in {file_path}")

    return issues


def check_caching_opportunities(file_path: Path) -> list[str]:
    """Identify opportunities for caching."""
    issues = []

    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    # Look for repeated expensive operations
    patterns = [
        (r"json\.loads\(.*\)", "JSON parsing"),
        (r"\.split\(.*\).*\.split\(", "Multiple string splits"),
        (r"for.*in.*:\s*\n.*re\.(search|match|compile)", "Regex in loop"),
    ]

    for pattern, operation in patterns:
        if re.search(pattern, content, re.MULTILINE):
            issues.append(f"Consider caching {operation} in {file_path}")

    return issues


def audit_performance(root_dir: Path) -> dict[str, list[str]]:
    """Run performance audit on Python files."""
    results = {"n_plus_one": [], "memory_leaks": [], "inefficient_ops": [], "missing_indexes": [], "caching": []}

    for py_file in root_dir.rglob("*.py"):
        # Skip test files and vendored code
        if "test" in py_file.parts or "__pycache__" in str(py_file):
            continue

        results["n_plus_one"].extend(check_n_plus_one_queries(py_file))
        results["memory_leaks"].extend(check_memory_leaks(py_file))
        results["inefficient_ops"].extend(check_inefficient_operations(py_file))

        # Only check database files for indexes
        if "db" in str(py_file) or "database" in str(py_file):
            results["missing_indexes"].extend(check_missing_indexes(py_file))

        results["caching"].extend(check_caching_opportunities(py_file))

    return results


def main() -> None:
    """Main performance audit function."""
    print("=" * 80)
    print("PERFORMANCE AUDIT REPORT")
    print("=" * 80)

    root_dir = Path.cwd()
    results = audit_performance(root_dir)

    total_issues = 0

    for category, issues in results.items():
        if issues:
            print(f"\n{category.replace('_', ' ').title()}:")
            print("-" * 40)
            for issue in issues[:10]:  # Limit to first 10 per category
                print(f"  - {issue}")
            if len(issues) > 10:
                print(f"  ... and {len(issues) - 10} more")
            total_issues += len(issues)

    print("\n" + "=" * 80)
    print(f"Total Performance Issues Found: {total_issues}")

    if total_issues == 0:
        print("✅ No major performance issues detected!")
    else:
        print("\nRecommendations:")
        if results["n_plus_one"]:
            print("  1. Use batch queries or joins to avoid N+1 patterns")
        if results["memory_leaks"]:
            print("  2. Ensure proper resource cleanup and list management")
        if results["inefficient_ops"]:
            print("  3. Optimize loop operations and avoid repeated calculations")
        if results["missing_indexes"]:
            print("  4. Add database indexes for frequently queried columns")
        if results["caching"]:
            print("  5. Implement caching for expensive repeated operations")

    print("=" * 80)


if __name__ == "__main__":
    main()
