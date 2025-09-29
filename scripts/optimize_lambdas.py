#!/usr/bin/env python3
"""
Optimize Lambda Function Usage for Hive Platform V4.4

Identifies lambda functions that could be optimized with:
- operator.itemgetter for simple attribute access
- operator.attrgetter for complex attribute access
- functools.partial for partial function application
- Named functions for complex logic
"""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from hive_logging import get_logger

logger = get_logger(__name__)


@dataclass
class LambdaOptimization:
    """Represents a potential lambda optimization"""

    file_path: Path
    line_number: int
    original: str
    suggested: str
    optimization_type: str
    complexity: str  # simple, moderate, complex


class LambdaOptimizer:
    """Analyzes and suggests lambda function optimizations"""

    def __init__(self, hive_root: Path = None):
        self.hive_root = hive_root or Path.cwd()
        self.optimizations = []

    def find_python_files(self) -> List[Path]:
        """Find all Python files in packages and apps"""
        python_files = []

        for pattern in ["packages/**/*.py", "apps/**/*.py"]:
            python_files.extend(self.hive_root.glob(pattern))

        # Exclude test files and legacy directories
        filtered_files = []
        for file_path in python_files:
            path_str = str(file_path).lower()
            if not any(exclude in path_str for exclude in ["__pycache__", "archive", "legacy", ".backup"]):
                filtered_files.append(file_path)

        return filtered_files

    def analyze_file(self, file_path: Path) -> List[LambdaOptimization]:
        """Analyze a single file for lambda optimization opportunities"""
        optimizations = []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                lines = content.split("\n")

            # Pattern 1: sorted with simple key lambda
            sorted_pattern = re.compile(
                r'sorted\([^,]+,\s*key=lambda\s+(\w+):\s*(\w+)\.get\(["\'](\w+)["\']\)(?:,\s*["\'][^"\']*["\']\))?\)'
            )
            for i, line in enumerate(lines, 1):
                match = sorted_pattern.search(line)
                if match:
                    var_name = match.group(1)
                    obj_name = match.group(2)
                    key_name = match.group(3)

                    if var_name == obj_name:
                        # Can use operator.itemgetter
                        opt = LambdaOptimization(
                            file_path=file_path,
                            line_number=i,
                            original=f"key=lambda {var_name}: {var_name}.get('{key_name}')",
                            suggested=f"key=operator.itemgetter('{key_name}')",
                            optimization_type="operator.itemgetter",
                            complexity="simple",
                        )
                        optimizations.append(opt)

            # Pattern 2: filter/map with simple lambda
            filter_map_pattern = re.compile(r"(filter|map)\(lambda\s+(\w+):\s*([^,\)]+),")
            for i, line in enumerate(lines, 1):
                match = filter_map_pattern.search(line)
                if match:
                    func_type = match.group(1)
                    var_name = match.group(2)
                    expression = match.group(3).strip()

                    # Check if it's a simple attribute access
                    if re.match(rf"^{var_name}\.(\w+)$", expression):
                        attr_name = re.match(rf"^{var_name}\.(\w+)$", expression).group(1)
                        opt = LambdaOptimization(
                            file_path=file_path,
                            line_number=i,
                            original=f"{func_type}(lambda {var_name}: {expression}",
                            suggested=f"{func_type}(operator.attrgetter('{attr_name}')",
                            optimization_type="operator.attrgetter",
                            complexity="simple",
                        )
                        optimizations.append(opt)

            # Pattern 3: Complex lambda in sorting (should be named function)
            complex_sorted = re.compile(r"sorted\([^,]+,\s*key=lambda\s+\w+:\s*[^\)]{50,}")
            for i, line in enumerate(lines, 1):
                match = complex_sorted.search(line)
                if match:
                    opt = LambdaOptimization(
                        file_path=file_path,
                        line_number=i,
                        original="Complex lambda in sorted",
                        suggested="Extract to named function for clarity",
                        optimization_type="named_function",
                        complexity="complex",
                    )
                    optimizations.append(opt)

            # Pattern 4: Lambda with multiple statements (anti-pattern)
            multi_statement = re.compile(r"lambda\s+\w+:\s*\([^;]+;[^)]+\)")
            for i, line in enumerate(lines, 1):
                if multi_statement.search(line):
                    opt = LambdaOptimization(
                        file_path=file_path,
                        line_number=i,
                        original="Multi-statement lambda",
                        suggested="Convert to named function",
                        optimization_type="named_function",
                        complexity="complex",
                    )
                    optimizations.append(opt)

        except Exception as e:
            logger.error(f"Error analyzing {file_path}: {e}")

        return optimizations

    def analyze_all(self) -> Tuple[int, Dict[str, int]]:
        """Analyze all Python files for lambda optimizations"""
        python_files = self.find_python_files()
        logger.info(f"Analyzing {len(python_files)} Python files")

        stats = {"itemgetter": 0, "attrgetter": 0, "named_function": 0, "total": 0}

        for file_path in python_files:
            file_opts = self.analyze_file(file_path)
            self.optimizations.extend(file_opts)

            for opt in file_opts:
                stats[opt.optimization_type] = stats.get(opt.optimization_type, 0) + 1
                stats["total"] += 1

        return len(python_files), stats

    def generate_report(self) -> str:
        """Generate optimization report"""
        files_analyzed, stats = self.analyze_all()

        report = f"""
# Lambda Optimization Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Summary
- Files analyzed: {files_analyzed}
- Total optimizations found: {stats['total']}
- Simple optimizations (itemgetter/attrgetter): {stats.get('itemgetter', 0) + stats.get('attrgetter', 0)}
- Complex refactoring needed: {stats.get('named_function', 0)}

## Optimization Breakdown
- operator.itemgetter opportunities: {stats.get('itemgetter', 0)}
- operator.attrgetter opportunities: {stats.get('attrgetter', 0)}
- Named function extractions needed: {stats.get('named_function', 0)}

## Top Files for Optimization
"""
        # Group by file
        by_file = {}
        for opt in self.optimizations:
            if opt.file_path not in by_file:
                by_file[opt.file_path] = []
            by_file[opt.file_path].append(opt)

        # Sort by number of optimizations
        sorted_files = sorted(by_file.items(), key=lambda x: len(x[1]), reverse=True)

        for file_path, opts in sorted_files[:10]:
            rel_path = file_path.relative_to(self.hive_root)
            report += f"\n### {rel_path} ({len(opts)} optimizations)\n"
            for opt in opts[:3]:  # Show first 3 optimizations
                report += f"- Line {opt.line_number}: {opt.optimization_type}\n"
                if opt.complexity == "simple":
                    report += f"  - Current: `{opt.original}`\n"
                    report += f"  - Suggested: `{opt.suggested}`\n"

        return report

    def apply_simple_optimizations(self, dry_run: bool = True) -> Dict[str, int]:
        """Apply simple optimizations automatically"""
        operations = {"files_updated": 0, "optimizations_applied": 0, "skipped": 0}

        # Group optimizations by file
        by_file = {}
        for opt in self.optimizations:
            if opt.complexity == "simple":
                if opt.file_path not in by_file:
                    by_file[opt.file_path] = []
                by_file[opt.file_path].append(opt)

        for file_path, opts in by_file.items():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                modified = False
                needs_operator_import = False

                # Apply optimizations (in reverse order to maintain line numbers)
                for opt in sorted(opts, key=lambda x: x.line_number, reverse=True):
                    line_idx = opt.line_number - 1
                    if line_idx < len(lines):
                        original_line = lines[line_idx]

                        # Apply the optimization
                        if opt.optimization_type == "operator.itemgetter":
                            new_line = re.sub(
                                r'key=lambda\s+\w+:\s*\w+\.get\(["\'][^"\']+["\']\)', opt.suggested, original_line
                            )
                            if new_line != original_line:
                                lines[line_idx] = new_line
                                modified = True
                                needs_operator_import = True
                                operations["optimizations_applied"] += 1

                if modified and not dry_run:
                    # Add operator import if needed
                    if needs_operator_import and "import operator" not in "".join(lines):
                        # Find the right place to add import
                        import_added = False
                        for i, line in enumerate(lines):
                            if line.startswith("from") or line.startswith("import"):
                                # Add after last import
                                continue
                            elif not line.strip() or line.strip().startswith("#"):
                                continue
                            else:
                                # Found first non-import line, add before it
                                lines.insert(i, "import operator\n")
                                import_added = True
                                break

                        if not import_added:
                            lines.insert(0, "import operator\n")

                    # Write back
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.writelines(lines)

                    operations["files_updated"] += 1
                    logger.info(f"Updated {file_path}: {len(opts)} optimizations")

            except Exception as e:
                logger.error(f"Error updating {file_path}: {e}")
                operations["skipped"] += 1

        return operations


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Optimize lambda function usage")
    parser.add_argument("--report", action="store_true", help="Generate optimization report")
    parser.add_argument("--apply", action="store_true", help="Apply simple optimizations")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be changed")

    args = parser.parse_args()

    optimizer = LambdaOptimizer()

    if args.report:
        print(optimizer.generate_report())
    elif args.apply:
        results = optimizer.apply_simple_optimizations(dry_run=args.dry_run)
        print(f"Optimization results: {results}")
    else:
        print("Use --report to see optimization opportunities or --apply to apply them")


if __name__ == "__main__":
    main()
