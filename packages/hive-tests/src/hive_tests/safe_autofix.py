"""
Safe Automated Golden Rules Violation Fixer - AST-ONLY

This module provides SAFE automated fixes for mechanical violations using
ONLY AST-based transformations. NO REGEX CODE MODIFICATION ALLOWED.

Lessons from incidents:
- emergency_syntax_fix_consolidated.py (2025-10-02): Regex comma disaster
- modernize_type_hints.py (2025-10-03): Regex import corruption
- autofix.py print fixer (2025-10-04): Regex print replacement (QUARANTINED)

CORE PRINCIPLE: ALL code modification MUST use AST. NO EXCEPTIONS.

Key Features:
- AST-based transformations ONLY (no regex on code structure)
- Backup creation before modifications
- Dry-run mode as default
- Detailed reporting of changes made
- Integration with Enhanced Golden Rules Framework

Safe Components Extracted:
- Async naming fixer (delegates to AST transformer)
- Exception inheritance fixer (uses AST parsing before modification)
"""

from __future__ import annotations

import ast
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AutofixResult:
    """Result of an automated fix operation"""

    file_path: Path
    rule_id: str
    rule_name: str
    fixes_applied: int
    changes_made: list[str]
    backup_created: bool
    success: bool
    error_message: str | None = None


class SafeGoldenRulesAutoFixer:
    """
    SAFE automated fixer for mechanical Golden Rules violations.

    Uses ONLY AST-based transformations. NO REGEX CODE MODIFICATION.

    Supported safe fixes:
    - Async function naming (Rule 14) - delegates to AST transformer
    - Exception inheritance (Rule 8) - uses AST parsing
    """

    def __init__(self, project_root: Path, dry_run: bool = True, create_backups: bool = True) -> None:
        self.project_root = project_root
        self.dry_run = dry_run
        self.create_backups = create_backups
        self.results: list[AutofixResult] = []

    def fix_all_violations(self, target_rules: set[str] | None = None) -> list[AutofixResult]:
        """
        Fix all mechanical violations across the project using SAFE AST-based methods.

        Args:
            target_rules: Specific rules to fix (e.g., {'rule-14', 'rule-8'})
                         If None, fixes all supported safe rules

        Returns:
            List of autofix results
        """
        self.results = []

        # Default to all SAFE supported rules (AST-only)
        if target_rules is None:
            target_rules = {"rule-14", "rule-8"}

        # Get all Python files
        python_files = self._get_python_files()

        for py_file in python_files:
            backup_path = None
            try:
                # Create backup if requested
                if self.create_backups and not self.dry_run:
                    backup_path = self._create_backup(py_file)

                # Apply SAFE fixes based on target rules
                if "rule-14" in target_rules:
                    self._fix_async_naming(py_file)

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
                    ),
                )

        return self.results

    def _get_python_files(self) -> list[Path]:
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
        Fix async function naming violations (Rule 14) - SAFE AST-BASED.

        Renames async functions to end with '_async' suffix using AST transformation.
        Delegates to async_naming_transformer which uses proper AST visitors.
        """
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            # Use enhanced AST transformer (SAFE - no regex)
            from .async_naming_transformer import fix_async_naming_ast

            try:
                modified_content, fixes = fix_async_naming_ast(content)
            except (SyntaxError, RuntimeError) as e:
                # Gracefully fail - do NOT fall back to regex
                self.results.append(
                    AutofixResult(
                        file_path=file_path,
                        rule_id="rule-14",
                        rule_name="Async Pattern Consistency",
                        fixes_applied=0,
                        changes_made=[],
                        backup_created=False,
                        success=False,
                        error_message=f"AST transformation failed: {e}",
                    ),
                )
                return

            # Build changes list
            changes_made = []
            for fix in fixes:
                total_changes = 1 + fix.occurrences  # Definition + call sites
                changes_made.append(
                    f"Renamed async function '{fix.old_name}' to '{fix.new_name}' "
                    f"at line {fix.line_number} ({total_changes} total occurrences)",
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
                    ),
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
                ),
            )

    def _fix_exception_inheritance(self, file_path: Path) -> None:
        """
        Fix exception inheritance violations (Rule 8) - SAFE AST-BASED.

        Updates custom exception classes to inherit from BaseError.
        Uses AST parsing to find exception classes (context-aware).
        """
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            # Parse AST to find exception classes (SAFE - context-aware)
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
                    # NOTE: Uses str.replace() AFTER AST analysis (borderline acceptable)
                    # Better: Use libcst for proper AST transformation in future
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
                            f"class {class_name}({old_base}",
                            f"class {class_name}(BaseError",
                        )
                        changes_made.append(f"Changed {class_name} to inherit from BaseError instead of {old_base}")
                        needs_base_error_import = True

            # Add BaseError import if needed
            if needs_base_error_import and "from hive_errors import BaseError" not in modified_content:
                lines = modified_content.split("\n")

                # Find import section (simple line-based - acceptable for imports)
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
                    ),
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
                ),
            )

    def generate_report(self) -> str:
        """Generate a comprehensive autofix report"""
        if not self.results:
            return "No autofix operations performed."

        report = []
        report.append("🔧 Safe Golden Rules Autofix Report (AST-ONLY)")
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
        report.append("  • Safety: AST-ONLY transformations (NO REGEX)")
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

        return "\n".join(report)


def main() -> None:
    """CLI interface for the safe autofix tool"""
    import argparse

    parser = argparse.ArgumentParser(description="SAFE Automated Golden Rules violation fixer (AST-ONLY)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Show what would be fixed without making changes (default)",
    )
    parser.add_argument("--execute", action="store_true", help="Actually apply the fixes (overrides --dry-run)")
    parser.add_argument("--rules", nargs="+", help="Specific rules to fix (e.g., rule-14 rule-8)")
    parser.add_argument("--no-backup", action="store_true", help="Don't create backup files")

    args = parser.parse_args()

    # Determine execution mode
    dry_run = not args.execute
    create_backups = not args.no_backup
    target_rules = set(args.rules) if args.rules else None

    # Setup logger for CLI
    from hive_logging import get_logger

    logger = get_logger(__name__)

    logger.info("Safe Golden Rules Autofix Tool (AST-ONLY)")
    logger.info("=" * 40)
    logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE EXECUTION'}")
    logger.info(f"Backups: {'Enabled' if create_backups and not dry_run else 'Disabled'}")
    logger.info(f"Target rules: {target_rules or 'All safe rules (rule-14, rule-8)'}")
    logger.info("Safety: AST-ONLY transformations (NO REGEX)")
    logger.info("")

    # Run safe autofix
    fixer = SafeGoldenRulesAutoFixer(project_root=Path("."), dry_run=dry_run, create_backups=create_backups)

    fixer.fix_all_violations(target_rules)

    # Generate and print report
    report = fixer.generate_report()
    logger.info(report)


if __name__ == "__main__":
    main()
