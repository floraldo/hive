#!/usr/bin/env python3
"""
AST-Based Safe Comma Fixer - EXAMPLE TEMPLATE

This demonstrates the CORRECT approach to fixing Python syntax issues:
- Uses AST for context-aware understanding
- Validates structure preservation
- Fails fast on unexpected changes
- Creates backups automatically

DO NOT use broad regex patterns for code modification!
"""

import ast
import shutil
import sys
from pathlib import Path
from typing import Optional


class ASTSafeCommaFixer:
    """Safe, AST-based comma fixing with validation."""

    def __init__(self, backup_dir: Path | None = None):
        self.backup_dir = backup_dir or Path("backups")
        self.fixes_applied = 0
        self.files_processed = 0
        self.files_fixed = 0
        self.files_failed = 0

    def create_backup(self, filepath: Path) -> Path:
        """Create backup before fixing."""
        self.backup_dir.mkdir(exist_ok=True)
        backup_path = self.backup_dir / f"{filepath.name}.backup"
        shutil.copy2(filepath, backup_path)
        return backup_path

    def restore_backup(self, filepath: Path, backup_path: Path) -> None:
        """Restore from backup if fix fails."""
        shutil.copy2(backup_path, filepath)

    def validate_structure_preservation(
        self, original_ast: Optional[ast.Module], new_ast: ast.Module
    ) -> bool:
        """Verify AST structure hasn't changed unexpectedly."""
        if original_ast is None:
            # Original was broken, can't compare
            return True

        # Check basic structure preservation
        # (In production, use more sophisticated comparison)
        original_nodes = sum(1 for _ in ast.walk(original_ast))
        new_nodes = sum(1 for _ in ast.walk(new_ast))

        # Allow small changes (added commas don't create new nodes)
        # but detect major structural changes
        node_diff = abs(new_nodes - original_nodes)
        if node_diff > 10:  # Arbitrary threshold
            print(f"  ⚠️  Structure changed: {node_diff} node difference")
            return False

        return True

    def fix_specific_patterns(self, tree: ast.Module) -> tuple[ast.Module, int]:
        """
        Fix ONLY specific, known-safe patterns using AST.

        This is a TEMPLATE - implement actual fixes here.
        Example fixes you could implement:
        - Dict unpacking without trailing comma
        - SQL string trailing commas
        - Specific function call patterns

        DO NOT use broad regex patterns!
        """
        fixes = 0

        # Example: Visit all function calls
        # Use ast.NodeVisitor or ast.NodeTransformer for safe modifications
        # See: https://docs.python.org/3/library/ast.html

        # For now, this is a NO-OP example
        # In production, implement specific pattern fixes using AST visitors

        return tree, fixes

    def fix_file(self, filepath: Path) -> bool:
        """Fix a single file with full validation."""
        try:
            # Create backup
            backup_path = self.create_backup(filepath)

            # Read original content
            with open(filepath, encoding="utf-8", errors="ignore") as f:
                original_content = f.read()

            # Try to parse original (may fail if already broken)
            original_ast = None
            try:
                original_ast = ast.parse(original_content, filename=str(filepath))
                # If already valid, no fixes needed
                self.files_processed += 1
                return True
            except SyntaxError:
                # File is broken - we'll try to fix it
                pass

            # For now, just validate the file compiles
            # In production, implement actual AST-based fixes here
            try:
                if original_ast:
                    # Apply fixes
                    fixed_tree, fixes = self.fix_specific_patterns(original_ast)

                    # Convert back to code
                    fixed_content = ast.unparse(fixed_tree)

                    # Validate result
                    new_ast = ast.parse(fixed_content, filename=str(filepath))

                    # Check structure preservation
                    if not self.validate_structure_preservation(original_ast, new_ast):
                        self.restore_backup(filepath, backup_path)
                        self.files_failed += 1
                        print(f"✗ ABORTED: {filepath} - structure changed unexpectedly")
                        return False

                    # Write fixed content
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(fixed_content)

                    self.files_fixed += 1
                    self.fixes_applied += fixes
                    print(f"✓ FIXED: {filepath} ({fixes} fixes)")
                    return True
                else:
                    # File was already broken - can't fix with AST
                    print(f"✗ SKIP: {filepath} - syntax errors prevent AST parsing")
                    return False

            except SyntaxError as e:
                # Fix introduced errors - ABORT
                self.restore_backup(filepath, backup_path)
                self.files_failed += 1
                print(f"✗ ABORTED: {filepath} - introduced syntax error: {e}")
                return False

        except Exception as e:
            self.files_failed += 1
            print(f"✗ ERROR: {filepath} - {e}")
            return False
        finally:
            self.files_processed += 1

    def fix_directory(self, directory: Path, pattern: str = "**/*.py") -> None:
        """Fix all Python files in directory."""
        files = list(directory.glob(pattern))
        print(f"Processing {len(files)} Python files in {directory}")

        for filepath in files:
            self.fix_file(filepath)

        # Print summary
        print(f"\n{'=' * 60}")
        print("AST-Based Safe Comma Fixer - Results")
        print(f"{'=' * 60}")
        print(f"Files processed: {self.files_processed}")
        print(f"Files fixed: {self.files_fixed}")
        print(f"Files failed: {self.files_failed}")
        print(f"Total fixes applied: {self.fixes_applied}")

        if self.files_fixed > 0:
            print(f"\n✓ SUCCESS: Fixed {self.files_fixed} files safely")
        if self.files_failed > 0:
            print(f"\n✗ WARNING: {self.files_failed} files could not be fixed")

        print(f"\nBackups created in: {self.backup_dir}")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python ast_safe_comma_fixer.py <directory_or_file>")
        print("\nExample: python ast_safe_comma_fixer.py apps/ecosystemiser")
        print("\nThis is a TEMPLATE script demonstrating safe AST-based fixing.")
        print("Implement actual fixes in fix_specific_patterns() method.")
        sys.exit(1)

    target = Path(sys.argv[1])

    if not target.exists():
        print(f"ERROR: {target} not found")
        sys.exit(1)

    print("=" * 60)
    print("AST-Based Safe Comma Fixer (TEMPLATE)")
    print("=" * 60)
    print("\n⚠️  This is a TEMPLATE demonstrating safe AST-based fixing.")
    print("Implement actual pattern fixes before using in production.\n")

    fixer = ASTSafeCommaFixer()

    if target.is_file():
        success = fixer.fix_file(target)
        sys.exit(0 if success else 1)
    elif target.is_dir():
        fixer.fix_directory(target)
        sys.exit(0 if fixer.files_failed == 0 else 1)
    else:
        print(f"ERROR: {target} is not a valid file or directory")
        sys.exit(1)


if __name__ == "__main__":
    main()
