"""
Automated Golden Rules Violation Fixer

This module provides automated fixes for mechanical violations detected by the
Enhanced Golden Rules Framework. It focuses on high-confidence, low-risk fixes
that can be applied automatically to accelerate the Platinum Burndown process.

Key Features:
- AST-based transformations for accuracy
- Backup creation before modifications
- Dry-run mode for safety
- Detailed reporting of changes made
- Integration with Enhanced Golden Rules Framework
"""

from __future__ import annotations

import ast
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set


@dataclass
class AutofixResult:
    """Result of an automated fix operation"""

    file_path: Path
    rule_id: str
    rule_name: str
    fixes_applied: int
    changes_made: List[str]
    backup_created: bool
    success: bool
    error_message: str | None = None


class GoldenRulesAutoFixer:
    """
    Automated fixer for mechanical Golden Rules violations.

    Focuses on high-confidence fixes that can be applied safely:
    - Async function naming (Rule 14)
    - Print statement replacement (Rule 9)
    - Exception inheritance (Rule 8)
    - Import organization (Rule 6)
    """

    def __init__(self, project_root: Path, dry_run: bool = True, create_backups: bool = True) -> None:
        self.project_root = project_root
        self.dry_run = dry_run
        self.create_backups = create_backups
        self.results: List[AutofixResult] = []

    def fix_all_violations(self, target_rules: Optional[Set[str]] = None) -> List[AutofixResult]:
        """
        Fix all mechanical violations across the project.

        Args:
            target_rules: Specific rules to fix (e.g., {'rule-14', 'rule-9'})
                         If None, fixes all supported rules

        Returns:
            List of autofix results
        """
        self.results = []

        # Default to all supported rules
        if target_rules is None:
            target_rules = {"rule-14", "rule-9", "rule-8"}

        # Get all Python files
        python_files = self._get_python_files()

        for py_file in python_files:
            backup_path = None
            try:
                # Create backup if requested
                if self.create_backups and not self.dry_run:
                    backup_path = self._create_backup(py_file)

                # Apply fixes based on target rules
                if "rule-14" in target_rules:
                    self._fix_async_naming(py_file)

                if "rule-9" in target_rules:
                    self._fix_print_statements(py_file)

                if "rule-8" in target_rules:
                    self._fix_exception_inheritance(py_file)

            except Exception as e:
                self.results.append(
                    AutofixResult(
                        file_path=py_file,
                        rule_id="autofix-error",
                        rule_name="Autofix Error",
                        fixes_applied=0,
                        changes_made=[],
                        backup_created=backup_path is not None,
                        success=False,
                        error_message=str(e),
                    )
                )

        return self.results

    def _get_python_files(self) -> List[Path]:
        """Get all Python files to process"""
        files = []
        for base_dir in [self.project_root / "apps", self.project_root / "packages"]:
            if base_dir.exists():
                files.extend(base_dir.rglob("*.py"))

        # Filter out unwanted files
        filtered_files = []
        for file_path in files:
            if any(skip in str(file_path) for skip in [".venv", "__pycache__", ".pytest_cache"]):
                continue
            filtered_files.append(file_path)

        return filtered_files

    def _create_backup(self, file_path: Path) -> Path:
        """Create backup of file before modification"""
        backup_path = file_path.with_suffix(f"{file_path.suffix}.backup")
        shutil.copy2(file_path, backup_path)
        return backup_path

    def _fix_async_naming(self, file_path: Path) -> None:
        """
        Fix async function naming violations (Rule 14).

        Renames async functions to end with '_async' suffix.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Parse AST
            tree = ast.parse(content)

            changes_made = []
            modified_content = content

            # Find async functions that need renaming
            for node in ast.walk(tree):
                if isinstance(node, ast.AsyncFunctionDef):
                    old_name = node.name

                    # Skip if already has _async suffix or starts with 'a'
                    if old_name.endswith("_async") or old_name.startswith("a"):
                        continue

                    # Skip special methods and private functions
                    if old_name.startswith("__") or old_name in ["run", "main", "start", "stop"]:
                        continue

                    new_name = f"{old_name}_async"

                    # Replace function definition and all calls
                    # Use word boundaries to avoid partial matches
                    pattern = rf"\b{re.escape(old_name)}\b"

                    # Count matches to verify changes
                    matches = len(re.findall(pattern, modified_content))
                    if matches > 0:
                        modified_content = re.sub(pattern, new_name, modified_content)
                        changes_made.append(
                            f"Renamed async function '{old_name}' to '{new_name}' ({matches} occurrences)"
                        )

            # Apply changes
            if changes_made and not self.dry_run:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(modified_content)

            if changes_made:
                self.results.append(
                    AutofixResult(
                        file_path=file_path,
                        rule_id="rule-14",
                        rule_name="Async Pattern Consistency",
                        fixes_applied=len(changes_made),
                        changes_made=changes_made,
                        backup_created=self.create_backups and not self.dry_run,
                        success=True,
                    )
                )

        except Exception as e:
            self.results.append(
                AutofixResult(
                    file_path=file_path,
                    rule_id="rule-14",
                    rule_name="Async Pattern Consistency",
                    fixes_applied=0,
                    changes_made=[],
                    backup_created=False,
                    success=False,
                    error_message=f"Error fixing async naming: {e}",
                )
            )

    def _fix_print_statements(self, file_path: Path) -> None:
        """
        Fix print statement violations (Rule 9).

        Replaces print() calls with logger.info() calls.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Skip test files and CLI files
            if any(indicator in str(file_path).lower() for indicator in ["test", "cli", "main", "script"]):
                return

            # Skip if already has logger import
            if "from hive_logging import" not in content:
                # Add logger import at the top
                lines = content.split("\n")

                # Find the best place to insert the import
                insert_index = 0
                for i, line in enumerate(lines):
                    if line.strip().startswith('"""') or line.strip().startswith("'''"):
                        # Skip docstrings
                        continue
                    if line.strip().startswith("import ") or line.strip().startswith("from "):
                        insert_index = i + 1
                    elif line.strip() and not line.strip().startswith("#"):
                        break

                # Insert logger import
                logger_import = "from hive_logging import get_logger"
                logger_init = "logger = get_logger(__name__)"

                lines.insert(insert_index, logger_import)
                lines.insert(insert_index + 1, logger_init)
                lines.insert(insert_index + 2, "")

                content = "\n".join(lines)

            changes_made = []
            modified_content = content

            # Replace print statements with logger calls
            # Pattern to match print() calls but not method calls like console.print()
            print_pattern = r"(?<!\.)\bprint\s*\("

            # Find all print statements
            for match in re.finditer(print_pattern, content):
                # Extract the full print statement
                start_pos = match.start()
                paren_count = 0
                end_pos = start_pos

                for i, char in enumerate(content[start_pos:], start_pos):
                    if char == "(":
                        paren_count += 1
                    elif char == ")":
                        paren_count -= 1
                        if paren_count == 0:
                            end_pos = i + 1
                            break

                old_statement = content[start_pos:end_pos]

                # Extract the arguments from print()
                args_start = old_statement.find("(") + 1
                args_end = old_statement.rfind(")")
                args = old_statement[args_start:args_end].strip()

                # Create logger replacement
                if args:
                    new_statement = f"logger.info({args})"
                else:
                    new_statement = "logger.info('')"

                modified_content = modified_content.replace(old_statement, new_statement)
                changes_made.append(f"Replaced print() with logger.info(): {old_statement}")

            # Apply changes
            if changes_made and not self.dry_run:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(modified_content)

            if changes_made:
                self.results.append(
                    AutofixResult(
                        file_path=file_path,
                        rule_id="rule-9",
                        rule_name="Logging Standards",
                        fixes_applied=len(changes_made),
                        changes_made=changes_made,
                        backup_created=self.create_backups and not self.dry_run,
                        success=True,
                    )
                )

        except Exception as e:
            self.results.append(
                AutofixResult(
                    file_path=file_path,
                    rule_id="rule-9",
                    rule_name="Logging Standards",
                    fixes_applied=0,
                    changes_made=[],
                    backup_created=False,
                    success=False,
                    error_message=f"Error fixing print statements: {e}",
                )
            )

    def _fix_exception_inheritance(self, file_path: Path) -> None:
        """
        Fix exception inheritance violations (Rule 8).

        Updates custom exception classes to inherit from BaseError.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Parse AST to find exception classes
            tree = ast.parse(content)

            changes_made = []
            modified_content = content

            # Add BaseError import if needed
            needs_base_error_import = False

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Check if this is an exception class
                    class_name = node.name
                    if not class_name.endswith("Error"):
                        continue

                    # Check current inheritance
                    base_names = []
                    for base in node.bases:
                        if isinstance(base, ast.Name):
                            base_names.append(base.id)

                    # Skip if already inherits from BaseError or standard exceptions
                    valid_bases = {"BaseError", "Exception", "ValueError", "TypeError", "RuntimeError"}
                    if any(base in valid_bases for base in base_names):
                        continue

                    # Update to inherit from BaseError
                    if not base_names:
                        # No current inheritance - add BaseError
                        old_class_def = f"class {class_name}:"
                        new_class_def = f"class {class_name}(BaseError):"
                        modified_content = modified_content.replace(old_class_def, new_class_def)
                        changes_made.append(f"Added BaseError inheritance to {class_name}")
                        needs_base_error_import = True
                    else:
                        # Has inheritance but not from valid bases - replace first base
                        old_base = base_names[0]
                        modified_content = modified_content.replace(
                            f"class {class_name}({old_base}", f"class {class_name}(BaseError"
                        )
                        changes_made.append(f"Changed {class_name} to inherit from BaseError instead of {old_base}")
                        needs_base_error_import = True

            # Add BaseError import if needed
            if needs_base_error_import and "from hive_errors import BaseError" not in modified_content:
                lines = modified_content.split("\n")

                # Find import section
                insert_index = 0
                for i, line in enumerate(lines):
                    if line.strip().startswith("import ") or line.strip().startswith("from "):
                        insert_index = i + 1
                    elif line.strip() and not line.strip().startswith("#"):
                        break

                lines.insert(insert_index, "from hive_errors import BaseError")
                lines.insert(insert_index + 1, "")
                modified_content = "\n".join(lines)
                changes_made.append("Added BaseError import")

            # Apply changes
            if changes_made and not self.dry_run:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(modified_content)

            if changes_made:
                self.results.append(
                    AutofixResult(
                        file_path=file_path,
                        rule_id="rule-8",
                        rule_name="Error Handling Standards",
                        fixes_applied=len(changes_made),
                        changes_made=changes_made,
                        backup_created=self.create_backups and not self.dry_run,
                        success=True,
                    )
                )

        except Exception as e:
            self.results.append(
                AutofixResult(
                    file_path=file_path,
                    rule_id="rule-8",
                    rule_name="Error Handling Standards",
                    fixes_applied=0,
                    changes_made=[],
                    backup_created=False,
                    success=False,
                    error_message=f"Error fixing exception inheritance: {e}",
                )
            )

    def generate_report(self) -> str:
        """Generate a comprehensive autofix report"""
        if not self.results:
            return "No autofix operations performed."

        report = []
        report.append("🔧 Golden Rules Autofix Report")
        report.append("=" * 40)
        report.append("")

        # Summary
        total_fixes = sum(r.fixes_applied for r in self.results if r.success)
        successful_files = len([r for r in self.results if r.success and r.fixes_applied > 0])
        failed_operations = len([r for r in self.results if not r.success])

        report.append("📊 Summary:")
        report.append(f"  • Total fixes applied: {total_fixes}")
        report.append(f"  • Files successfully modified: {successful_files}")
        report.append(f"  • Failed operations: {failed_operations}")
        report.append(f"  • Mode: {'DRY RUN' if self.dry_run else 'LIVE EXECUTION'}")
        report.append("")

        # Group by rule
        by_rule = {}
        for result in self.results:
            if result.rule_id not in by_rule:
                by_rule[result.rule_id] = []
            by_rule[result.rule_id].append(result)

        for rule_id, rule_results in by_rule.items():
            successful = [r for r in rule_results if r.success and r.fixes_applied > 0]
            if not successful:
                continue

            rule_name = successful[0].rule_name
            total_rule_fixes = sum(r.fixes_applied for r in successful)

            report.append(f"📋 {rule_name} ({rule_id}):")
            report.append(f"  • Files processed: {len(successful)}")
            report.append(f"  • Total fixes: {total_rule_fixes}")

            # Show sample changes
            for result in successful[:3]:  # Show first 3 files
                report.append(f"  • {result.file_path.relative_to(self.project_root)}")
                for change in result.changes_made[:2]:  # Show first 2 changes
                    report.append(f"    - {change}")
                if len(result.changes_made) > 2:
                    report.append(f"    - ... and {len(result.changes_made) - 2} more changes")

            if len(successful) > 3:
                report.append(f"  • ... and {len(successful) - 3} more files")
            report.append("")

        # Errors
        errors = [r for r in self.results if not r.success]
        if errors:
            report.append("❌ Errors:")
            for error in errors[:5]:
                report.append(f"  • {error.file_path.relative_to(self.project_root)}: {error.error_message}")
            if len(errors) > 5:
                report.append(f"  • ... and {len(errors) - 5} more errors")
            report.append("")

        # Next steps
        report.append("🚀 Next Steps:")
        if self.dry_run:
            report.append("  1. Review the proposed changes above")
            report.append("  2. Run with dry_run=False to apply fixes")
            report.append("  3. Test the modified code")
            report.append("  4. Commit the improvements")
        else:
            report.append("  1. Test the modified code")
            report.append("  2. Run Golden Rules validation to verify fixes")
            report.append("  3. Commit the improvements")
            report.append("  4. Continue with remaining manual fixes")

        return "\n".join(report)


def main() -> None:
    """CLI interface for the autofix tool"""
    import argparse

    parser = argparse.ArgumentParser(description="Automated Golden Rules violation fixer")
    parser.add_argument(
        "--dry-run", action="store_true", default=True, help="Show what would be fixed without making changes"
    )
    parser.add_argument("--execute", action="store_true", help="Actually apply the fixes (overrides --dry-run)")
    parser.add_argument("--rules", nargs="+", help="Specific rules to fix (e.g., rule-14 rule-9)")
    parser.add_argument("--no-backup", action="store_true", help="Don't create backup files")

    args = parser.parse_args()

    # Determine execution mode
    dry_run = not args.execute
    create_backups = not args.no_backup
    target_rules = set(args.rules) if args.rules else None

    # Setup logger for CLI
    from hive_logging import get_logger

    logger = get_logger(__name__)

    logger.info("Golden Rules Autofix Tool")
    logger.info("=" * 40)
    logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE EXECUTION'}")
    logger.info(f"Backups: {'Enabled' if create_backups and not dry_run else 'Disabled'}")
    logger.info(f"Target rules: {target_rules or 'All supported rules'}")
    logger.info("")

    # Run autofix
    fixer = GoldenRulesAutoFixer(project_root=Path("."), dry_run=dry_run, create_backups=create_backups)

    results = fixer.fix_all_violations(target_rules)

    # Generate and print report
    report = fixer.generate_report()
    logger.info(report)


if __name__ == "__main__":
    main()
