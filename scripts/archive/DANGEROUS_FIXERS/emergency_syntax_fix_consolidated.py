#!/usr/bin/env python3
"""
EMERGENCY SYNTAX FIX - CONSOLIDATED
===================================

This script consolidates ALL comma fixing patterns from 50+ scripts across the codebase.
Use this as the ultimate emergency backup when linters fail to fix syntax errors.

Based on comprehensive analysis of ALL comma fixing scripts:
- scripts/master_syntax_fixer.py
- scripts/emergency_syntax_fix.py
- scripts/safe_comma_fixer.py
- scripts/comprehensive_comma_fixer.py
- scripts/final_comma_fix.py
- scripts/aggressive_comma_fix.py
- scripts/direct_comma_fixer.py
- scripts/simple_comma_fixer.py
- scripts/targeted_comma_fixer.py
- scripts/pattern_comma_fixer.py
- scripts/remove_invalid_trailing_commas.py
- scripts/fix_comma_overcorrections.py
- scripts/fix_agent_targeted.py
- scripts/final_agent_fix.py
- scripts/code_red_stabilization.py
- scripts/fix_critical_files.py
- scripts/fix_async_agents.py
- scripts/master_cleanup.py
- scripts/archive/comma_fixes/fix_missing_commas.py
- scripts/archive/comma_fixes/fix_all_kwargs_commas.py
- scripts/archive/comma_fixes/cleanup_comma_artifacts.py
- scripts/archive/comma_fixes/fix_events_commas.py
- scripts/archive/comma_fixes/fix_linter_comma_damage.py
- scripts/archive/comma_fixes/fix_critical_path_commas.py
- scripts/archive/comma_fixes/fix_remaining_comma_errors.py
- scripts/archive/syntax_fixes/emergency_linter_restore.py
- scripts/archive/syntax_fixes/aggressive_syntax_fix.py
- scripts/archive/syntax_fixes/targeted_syntax_fix.py
- scripts/archive/syntax_fixes/run_all_fixes.py
- scripts/archive/syntax_fixes/fix_syntax_systematic.py
- scripts/archive/syntax_fixes/batch_syntax_fix.py
- scripts/archive/misplaced/ultimate_syntax_fix.py
- scripts/archive/misplaced/comprehensive_syntax_fix.py
- And 20+ other comma fixing scripts

SAFETY FEATURES:
- Creates backups before fixing
- Validates fixes with AST parsing
- Restores original content if fix fails
- Comprehensive error handling
- Detailed logging and reporting
- Handles all known edge cases and overcorrections
"""

import ast
import re
import shutil
import sys
from pathlib import Path


class EmergencySyntaxFixer:
    """Ultimate emergency syntax fixer consolidating ALL patterns from 50+ scripts."""

    def __init__(self, backup_dir: Path | None = None):
        self.backup_dir = backup_dir or Path("backups")
        self.fixes_applied = 0
        self.files_processed = 0
        self.files_fixed = 0
        self.files_failed = 0
        self.stats = {
            "function_calls": 0,
            "dictionaries": 0,
            "lists": 0,
            "enums": 0,
            "expressions": 0,
            "boolean_conditions": 0,
            "imports": 0,
            "classmethod_params": 0,
            "function_params": 0,
            "tuple_trailing": 0,
            "future_imports": 0,
            "typing_imports": 0,
            "incomplete_lines": 0,
            "sql_tuples": 0,
            "plot_factory": 0,
            "bus_sql": 0,
            "bad_commas_removed": 0,
            "overcorrections": 0,
        }

    def create_backup(self, filepath: Path) -> Path:
        """Create backup of file before fixing."""
        self.backup_dir.mkdir(exist_ok=True)
        backup_path = self.backup_dir / f"{filepath.name}.backup"
        shutil.copy2(filepath, backup_path)
        return backup_path

    def restore_backup(self, filepath: Path, backup_path: Path) -> None:
        """Restore file from backup."""
        shutil.copy2(backup_path, filepath)

    def fix_function_call_commas(self, content: str) -> tuple[str, int]:
        """Fix missing commas in function calls - ALL patterns from all scripts."""
        fixes = 0

        # Pattern 1: Basic function call arguments
        # arg=value\n    other_arg=value -> arg=value,\n    other_arg=value
        pattern1 = r"([a-zA-Z_][a-zA-Z0-9_]*\s*=\s*[^,\n\)]*)\n(\s+)([a-zA-Z_][a-zA-Z0-9_]*\s*=)"
        content = re.sub(pattern1, r"\1,\n\2\3", content)
        fixes += len(re.findall(pattern1, content))

        # Pattern 2: Function calls with specific parameter names
        # payload=, source=, etc.
        specific_params = ["payload", "source", "target", "value", "label"]
        for param in specific_params:
            pattern = rf"([a-zA-Z_][a-zA-Z0-9_]*=[^\n,]+)\n(\s+)({param}=)"
            content = re.sub(pattern, r"\1,\n\2\3", content)
            fixes += len(re.findall(pattern, content))

        # Pattern 3: Function calls with identifier/string/number values
        pattern3 = r'(["\'\w\d\]}\)]\s*)\n(\s+)([a-zA-Z_][a-zA-Z0-9_]*\s*[=:])'
        content = re.sub(pattern3, r"\1,\n\2\3", content)
        fixes += len(re.findall(pattern3, content))

        # Pattern 4: Multi-line function calls with complex arguments
        def fix_call_block(match):
            nonlocal fixes
            header = match.group(1)  # "function_name("
            args_block = match.group(2)  # arguments block
            footer = match.group(3)  # ")"

            lines = args_block.split("\n")
            fixed_lines = []

            for i, line in enumerate(lines):
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    fixed_lines.append(line)
                    continue

                # If this line has an argument and next line also has an argument, add comma
                if (
                    i < len(lines) - 1
                    and ("=" in stripped or stripped.isidentifier() or '"' in stripped)
                    and not stripped.endswith(",")
                    and not stripped.endswith(")")
                ):
                    next_line = lines[i + 1].strip()
                    if (
                        next_line
                        and not next_line.startswith(")")
                        and not next_line.startswith("#")
                        and ("=" in next_line or next_line.isidentifier() or '"' in next_line)
                    ):
                        line = line.rstrip() + ","
                        fixes += 1

                fixed_lines.append(line)

            return header + "\n".join(fixed_lines) + footer

        # Match function calls with multiline arguments
        pattern = r"(\w+\s*\(\s*\n)(.*?)(\n\s*\))"
        content = re.sub(pattern, fix_call_block, content, flags=re.DOTALL)

        return content, fixes

    def fix_dictionary_commas(self, content: str) -> tuple[str, int]:
        """Fix missing commas in dictionaries - ALL patterns."""
        fixes = 0

        # Pattern 1: Basic dictionary entries
        pattern1 = r'(["\'][\w_]+["\']\s*:\s*[^,}\n]+)(\s+["\'][\w_]+["\']\s*:)'
        content = re.sub(pattern1, r"\1,\n\2", content)
        fixes += len(re.findall(pattern1, content))

        # Pattern 2: Specific plot_factory patterns
        plot_patterns = [
            (r'("source": flow_info\["source"\])\n(\s*"target":)', r"\1,\n\2"),
            (r'("target": flow_info\["target"\])\n(\s*"value":)', r"\1,\n\2"),
            (r'("value": [^,\n}]*)\n(\s*"label":)', r"\1,\n\2"),
        ]

        for pattern, replacement in plot_patterns:
            new_content = re.sub(pattern, replacement, content)
            if new_content != content:
                fixes += 1
                content = new_content

        return content, fixes

    def fix_list_commas(self, content: str) -> tuple[str, int]:
        """Fix missing commas in lists - ALL patterns."""
        fixes = 0

        # Pattern 1: Basic list items
        pattern1 = r"([a-zA-Z_][a-zA-Z0-9_\[\]]*)\n(\s+[a-zA-Z_][a-zA-Z0-9_\[\]]*)"
        content = re.sub(pattern1, r"\1,\n\2", content)
        fixes += len(re.findall(pattern1, content))

        # Pattern 2: List items with complex expressions
        pattern2 = r'([^,\(\n]+)\n(\s+[a-zA-Z_"\'\.][a-zA-Z0-9_"\'\.\[\]]*(?:\([^)]*\))?)'
        content = re.sub(pattern2, r"\1,\n\2", content)
        fixes += len(re.findall(pattern2, content))

        return content, fixes

    def fix_enum_commas(self, content: str) -> tuple[str, int]:
        """Fix missing commas in enum definitions."""
        fixes = 0

        # Pattern: enum items without commas
        pattern = r"(\w+)\n(\s+)(\w+)"
        content = re.sub(pattern, r"\1,\n\2\3", content)
        fixes += len(re.findall(pattern, content))

        return content, fixes

    def fix_multiline_expressions(self, content: str) -> tuple[str, int]:
        """Fix missing commas in multiline expressions."""
        fixes = 0

        # Pattern: expressions spanning multiple lines
        pattern = r"([^,\n]+)\n(\s+[^,\n]+)"
        content = re.sub(pattern, r"\1,\n\2", content)
        fixes += len(re.findall(pattern, content))

        return content, fixes

    def fix_boolean_conditions(self, content: str) -> tuple[str, int]:
        """Fix missing commas in boolean conditions."""
        fixes = 0

        # Pattern: boolean expressions
        pattern = r"(\w+\s*=\s*[^,\n]+)\n(\s+)(\w+\s*=)"
        content = re.sub(pattern, r"\1,\n\2\3", content)
        fixes += len(re.findall(pattern, content))

        return content, fixes

    def fix_import_commas(self, content: str) -> tuple[str, int]:
        """Fix missing commas in import statements - ALL patterns."""
        fixes = 0

        # Pattern 1: Basic import statements
        pattern1 = r"([a-zA-Z_][a-zA-Z0-9_]*)\n(\s+[a-zA-Z_][a-zA-Z0-9_]*)\n\)"
        content = re.sub(pattern1, r"\1,\n\2\n)", content)
        fixes += len(re.findall(pattern1, content))

        # Pattern 2: Multiline imports with complex handling
        def fix_import_block(match):
            nonlocal fixes
            header = match.group(1)  # "from module import ("
            imports_block = match.group(2)  # import items
            footer = match.group(3)  # ")"

            lines = imports_block.split("\n")
            fixed_lines = []

            for i, line in enumerate(lines):
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    fixed_lines.append(line)
                    continue

                # If this line has an import and next line also has an import, add comma
                if i < len(lines) - 1 and stripped and not stripped.endswith(",") and not stripped.endswith(")"):
                    next_line = lines[i + 1].strip()
                    if next_line and not next_line.startswith(")") and not next_line.startswith("#"):
                        line = line.rstrip() + ","
                        fixes += 1

                fixed_lines.append(line)

            return header + "\n".join(fixed_lines) + footer

        # Match multiline imports
        pattern = r"(from\s+[\w\.]+\s+import\s+\(\s*\n)(.*?)(\n\s*\))"
        content = re.sub(pattern, fix_import_block, content, flags=re.DOTALL)

        return content, fixes

    def fix_classmethod_parameters(self, content: str) -> tuple[str, int]:
        """Fix missing commas in @classmethod parameters."""
        fixes = 0

        def fix_classmethod_block(match):
            nonlocal fixes
            decorator = match.group(1)  # @classmethod\n
            header = match.group(2)  # def method_name(
            params_block = match.group(3)  # parameter block
            footer = match.group(4)  # ):

            lines = params_block.split("\n")
            fixed_lines = []

            for i, line in enumerate(lines):
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    fixed_lines.append(line)
                    continue

                # If this line has a parameter and next line also has a parameter, add comma
                if (
                    i < len(lines) - 1
                    and (":" in stripped or "cls" in stripped)
                    and not stripped.endswith(",")
                    and not stripped.endswith(")")
                ):
                    next_line = lines[i + 1].strip()
                    if (
                        next_line
                        and not next_line.startswith(")")
                        and not next_line.startswith("#")
                        and (":" in next_line or "**" in next_line)
                    ):
                        line = line.rstrip() + ","
                        fixes += 1

                fixed_lines.append(line)

            return decorator + header + "\n".join(fixed_lines) + footer

        # Match @classmethod with multiline parameters
        pattern = r"(@classmethod\s*\n\s*)(def\s+\w+\s*\(\s*\n)(.*?)(\n\s*\):)"
        content = re.sub(pattern, fix_classmethod_block, content, flags=re.DOTALL)

        return content, fixes

    def fix_function_parameters(self, content: str) -> tuple[str, int]:
        """Fix missing commas in function parameter definitions."""
        fixes = 0

        def fix_param_block(match):
            nonlocal fixes
            header = match.group(1)  # "def function_name("
            params_block = match.group(2)  # parameter block
            footer = match.group(3)  # "):"

            lines = params_block.split("\n")
            fixed_lines = []

            for i, line in enumerate(lines):
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    fixed_lines.append(line)
                    continue

                # If this line has a parameter and next line also has a parameter, add comma
                if i < len(lines) - 1 and ":" in stripped and not stripped.endswith(",") and not stripped.endswith(")"):
                    next_line = lines[i + 1].strip()
                    if (
                        next_line
                        and not next_line.startswith(")")
                        and not next_line.startswith("#")
                        and (":" in next_line or next_line.startswith("**"))
                    ):
                        line = line.rstrip() + ","
                        fixes += 1

                fixed_lines.append(line)

            return header + "\n".join(fixed_lines) + footer

        # Match function definitions with multiline parameters
        pattern = r"(def\s+\w+\s*\(\s*\n)(.*?)(\n\s*\):)"
        content = re.sub(pattern, fix_param_block, content, flags=re.DOTALL)

        return content, fixes

    def fix_tuple_trailing_commas(self, content: str) -> tuple[str, int]:
        """Fix trailing commas in single-element tuples that cause syntax errors."""
        fixes = 0

        # Remove trailing commas that cause syntax errors
        patterns = [
            # Fix: (item,) when it should be (item)
            r"\(\s*([^,\(\)]+),\s*\)(?=\s*[=\)])",
            # Fix: constraints = ([],) should be constraints = []
            r"=\s*\(\s*\[\s*\]\s*,\s*\)",
        ]

        for pattern in patterns:
            if "constraints = " in pattern:
                content = re.sub(pattern, "= []", content)
            else:
                content = re.sub(pattern, r"(\1)", content)
            fixes += content.count("(") - content.count(")")  # Rough estimate

        return content, fixes

    def fix_future_imports(self, content: str) -> tuple[str, int]:
        """Move __future__ imports to the top of the file."""
        fixes = 0

        lines = content.split("\n")
        future_imports = []
        other_lines = []

        for line in lines:
            if "from __future__ import" in line:
                if line.strip() not in [fi.strip() for fi in future_imports]:
                    future_imports.append(line)
                continue
            other_lines.append(line)

        if future_imports:
            # Reconstruct with __future__ imports at top
            result_lines = []
            docstring_lines = []
            code_lines = []
            in_docstring = False

            for line in other_lines:
                stripped = line.strip()
                if not in_docstring and (stripped.startswith('"""') or stripped.startswith("'''")):
                    in_docstring = True
                    docstring_lines.append(line)
                elif in_docstring:
                    docstring_lines.append(line)
                    if stripped.endswith('"""') or stripped.endswith("'''"):
                        in_docstring = False
                        if not line.strip():
                            pass
                        else:
                            docstring_lines.append("")
                else:
                    code_lines.append(line)

            result_lines.extend(docstring_lines)
            result_lines.extend(future_imports)
            if future_imports and code_lines:
                result_lines.append("")
            result_lines.extend(code_lines)

            content = "\n".join(result_lines)
            fixes += 1

        return content, fixes

    def fix_typing_imports(self, content: str) -> tuple[str, int]:
        """Fix common typing import issues."""
        fixes = 0

        # Fix ListTuple -> List, Tuple
        content = re.sub(r"\bListTuple\b", "List, Tuple", content)
        fixes += content.count("ListTuple")

        # Fix DictList -> Dict, List
        content = re.sub(r"\bDictList\b", "Dict, List", content)
        fixes += content.count("DictList")

        return content, fixes

    def fix_incomplete_lines(self, content: str) -> tuple[str, int]:
        """Fix incomplete lines that are just identifiers."""
        fixes = 0

        lines = content.split("\n")
        fixed_lines = []

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Check if line is just an identifier
            if (
                stripped
                and stripped.replace("_", "a")
                .replace("0", "a")
                .replace("1", "a")
                .replace("2", "a")
                .replace("3", "a")
                .replace("4", "a")
                .replace("5", "a")
                .replace("6", "a")
                .replace("7", "a")
                .replace("8", "a")
                .replace("9", "a")
                .isidentifier()
                and i > 0
            ):
                prev_line = lines[i - 1].strip()

                # This might be a continuation of an import or call
                if "import" in prev_line or prev_line.endswith("(") or prev_line.endswith(","):
                    # Add comma to previous line if missing
                    if not prev_line.endswith(",") and not prev_line.endswith("("):
                        fixed_lines[-1] = fixed_lines[-1].rstrip() + ","
                        fixes += 1

            fixed_lines.append(line)

        return "\n".join(fixed_lines), fixes

    def fix_sql_tuples(self, content: str) -> tuple[str, int]:
        """Fix SQL query tuples missing commas."""
        fixes = 0

        # Pattern: SQL VALUES tuples
        pattern = r"(\) VALUES \([^)]*\))\n(\s*\(\n)"
        content = re.sub(pattern, r"\1,\n\2", content)
        fixes += len(re.findall(pattern, content))

        # Specific bus.py SQL pattern
        bus_pattern = r"(\) VALUES \(\?, \?, \?, \?, \?, \?, \?, \?, \?, \?\))\n(\s*\()"
        content = re.sub(bus_pattern, r"\1,\n\2", content)
        fixes += len(re.findall(bus_pattern, content))

        return content, fixes

    def remove_bad_commas(self, content: str) -> tuple[str, int]:
        """Remove commas that were incorrectly added - ALL patterns from all scripts."""
        fixes = 0

        # Remove double commas
        content = re.sub(r",,+", ",", content)

        # Remove comma before closing braces/brackets/parentheses if it's the last item
        content = re.sub(r",(\s*[}\]\)])", r"\1", content)

        # Remove commas after opening braces
        patterns = [(r"\{,\s*\n", "{\n"), (r"\[,\s*\n", "[\n"), (r"\(\s*\n", "(\n")]

        for pattern, replacement in patterns:
            new_content = re.sub(pattern, replacement, content)
            if new_content != content:
                fixes += 1
                content = new_content

        # Remove trailing commas from control structures (if/for/while/try/def/class)
        content = re.sub(
            r"^(\s*(?:if|for|while|try|except|finally|def|class|with|elif|else)[^:\n]*):,(\s*)$",
            r"\1:\2",
            content,
            flags=re.MULTILINE,
        )

        # Remove trailing commas from decorators
        content = re.sub(r"^(\s*@\w+),(\s*)$", r"\1\2", content, flags=re.MULTILINE)

        # Remove trailing commas from empty containers
        content = re.sub(r"(\{\s*),(\s*)", r"\1\2", content)  # Empty dict
        content = re.sub(r"(\[\s*),(\s*)", r"\1\2", content)  # Empty list

        # Remove trailing commas from function calls at end of line
        content = re.sub(r"^(\s*[^#\n]+\([^)]*\)):,(\s*)$", r"\1:\2", content, flags=re.MULTILINE)
        content = re.sub(r"^(\s*[^#\n]+\([^)]*\)),(\s*)$", r"\1\2", content, flags=re.MULTILINE)

        # Remove trailing commas from assignments
        content = re.sub(r"^(\s*[^#\n]+ = [^#\n]+),(\s*)$", r"\1\2", content, flags=re.MULTILINE)

        # Remove trailing commas from return statements
        content = re.sub(r"^(\s*return\s+[^#\n]+),(\s*)$", r"\1\2", content, flags=re.MULTILINE)

        # Remove trailing commas from logger assignments
        content = re.sub(r"^(\s*logger\s*=\s*[^#\n]+),(\s*)$", r"\1\2", content, flags=re.MULTILINE)

        # Fix single-element tuples with trailing commas
        content = re.sub(r"\(\s*([^,\(\)]+),\s*\)(?=\s*[=\)])", r"(\1)", content)
        content = re.sub(r"=\s*\(\s*\[\s*\]\s*,\s*\)", "= []", content)

        # Remove trailing commas from import statements
        content = re.sub(r"^(\s*import\s[^#\n]+),(\s*)$", r"\1\2", content, flags=re.MULTILINE)
        content = re.sub(r"^(\s*from\s.*import\s[^#\n]+),(\s*)$", r"\1\2", content, flags=re.MULTILINE)

        # Fix common typing import issues
        content = re.sub(r"\bListTuple\b", "List, Tuple", content)
        content = re.sub(r"\bDictList\b", "Dict, List", content)

        return content, fixes

    def fix_file(self, filepath: Path) -> bool:
        """Fix a single file using ALL patterns from all scripts."""
        try:
            # Create backup
            backup_path = self.create_backup(filepath)

            # Read original content
            with open(filepath, encoding="utf-8", errors="ignore") as f:
                original_content = f.read()

            # Check if already valid
            try:
                ast.parse(original_content, filename=str(filepath))
                return True  # Already valid
            except SyntaxError:
                pass  # Continue with fixing

            # Apply ALL fixing strategies
            content = original_content
            stats = {}

            # Function call commas
            content, count = self.fix_function_call_commas(content)
            stats["function_calls"] = count

            # Dictionary commas
            content, count = self.fix_dictionary_commas(content)
            stats["dictionaries"] = count

            # List commas
            content, count = self.fix_list_commas(content)
            stats["lists"] = count

            # Enum commas
            content, count = self.fix_enum_commas(content)
            stats["enums"] = count

            # Multiline expressions
            content, count = self.fix_multiline_expressions(content)
            stats["expressions"] = count

            # Boolean conditions
            content, count = self.fix_boolean_conditions(content)
            stats["boolean_conditions"] = count

            # Import commas
            content, count = self.fix_import_commas(content)
            stats["imports"] = count

            # Classmethod parameters
            content, count = self.fix_classmethod_parameters(content)
            stats["classmethod_params"] = count

            # Function parameters
            content, count = self.fix_function_parameters(content)
            stats["function_params"] = count

            # Tuple trailing commas
            content, count = self.fix_tuple_trailing_commas(content)
            stats["tuple_trailing"] = count

            # Future imports
            content, count = self.fix_future_imports(content)
            stats["future_imports"] = count

            # Typing imports
            content, count = self.fix_typing_imports(content)
            stats["typing_imports"] = count

            # Incomplete lines
            content, count = self.fix_incomplete_lines(content)
            stats["incomplete_lines"] = count

            # SQL tuples
            content, count = self.fix_sql_tuples(content)
            stats["sql_tuples"] = count

            # Remove bad commas (overcorrections)
            content, count = self.remove_bad_commas(content)
            stats["bad_commas_removed"] = count

            # Test if fixes worked
            try:
                ast.parse(content, filename=str(filepath))
                syntax_valid = True
            except SyntaxError:
                syntax_valid = False

            # Only write if we made improvements
            if content != original_content:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)

                if syntax_valid:
                    self.files_fixed += 1
                    self.fixes_applied += sum(stats.values())
                    self.stats.update(stats)
                    print(f"✓ FIXED: {filepath}")
                    return True
                else:
                    # Restore backup if fix failed
                    self.restore_backup(filepath, backup_path)
                    self.files_failed += 1
                    print(f"✗ FAILED: {filepath} - syntax still invalid")
                    return False
            else:
                # No changes needed
                return True

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

        # Print comprehensive summary
        print(f"\n{'=' * 60}")
        print("EMERGENCY SYNTAX FIX - CONSOLIDATED RESULTS")
        print(f"{'=' * 60}")
        print(f"Files processed: {self.files_processed}")
        print(f"Files fixed: {self.files_fixed}")
        print(f"Files failed: {self.files_failed}")
        print(f"Total fixes applied: {self.fixes_applied}")
        print("\nDetailed statistics:")
        for category, count in self.stats.items():
            if count > 0:
                print(f"  {category}: {count}")

        if self.files_fixed > 0:
            print(f"\n✓ SUCCESS: Fixed {self.files_fixed} files")
        if self.files_failed > 0:
            print(f"\n✗ WARNING: {self.files_failed} files still have issues")

        print(f"\nBackups created in: {self.backup_dir}")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/emergency_syntax_fix_consolidated.py <directory_or_file>")
        print("Example: python scripts/emergency_syntax_fix_consolidated.py apps/ecosystemiser")
        sys.exit(1)

    target = Path(sys.argv[1])

    if not target.exists():
        print(f"ERROR: {target} not found")
        sys.exit(1)

    fixer = EmergencySyntaxFixer()

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
