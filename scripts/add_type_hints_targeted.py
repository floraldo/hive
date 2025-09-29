#!/usr/bin/env python
"""
Targeted type hint addition for common patterns.

This script adds type hints to functions with missing return types or parameters.
"""

import re
import sys
from pathlib import Path


def add_missing_return_types(file_path: Path, dry_run: bool = True) -> bool:
    """Add missing return type hints to functions."""
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
            original = content
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return False

    # Skip test files
    if "test" in str(file_path).lower():
        return False

    # Skip if already has type hints everywhere
    lines = content.split("\n")
    modified = False
    new_lines = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # Look for function definitions without return type hints
        func_match = re.match(r"^(\s*)def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^)]*)\)\s*:(.*)$", line)
        if func_match:
            indent, func_name, params, after_colon = func_match.groups()

            # Skip if already has return type hint
            if "->" not in line:
                # Try to infer return type from function content
                return_type = infer_return_type(lines, i, func_name)
                if return_type:
                    new_line = f"{indent}def {func_name}({params}) -> {return_type}:{after_colon}"
                    new_lines.append(new_line)
                    modified = True
                    print(f"  Added return type to {func_name}: -> {return_type}")
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

        i += 1

    if not modified:
        return False

    if not dry_run:
        try:
            new_content = "\n".join(new_lines)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            return True
        except Exception as e:
            print(f"Error writing {file_path}: {e}")
            return False
    else:
        print(f"  Would modify {file_path}")
        return True


def infer_return_type(lines: list[str], func_start: int, func_name: str) -> str | None:
    """Infer return type from function body."""

    # Look for return statements in the function
    indent_level = len(lines[func_start]) - len(lines[func_start].lstrip())

    return_statements = []
    i = func_start + 1

    # Find the end of the function
    while i < len(lines):
        line = lines[i]
        current_indent = len(line) - len(line.lstrip())

        # If we've de-indented back to the original level or less, we're done
        if line.strip() and current_indent <= indent_level:
            break

        # Look for return statements
        if "return" in line:
            return_match = re.search(r"return\s+(.+)", line.strip())
            if return_match:
                return_expr = return_match.group(1).strip()
                return_statements.append(return_expr)

        i += 1

    # Infer type from return statements
    if not return_statements:
        return "None"

    # Common patterns
    for ret in return_statements:
        if ret in ["True", "False"]:
            return "bool"
        elif ret.startswith('"') or ret.startswith("'"):
            return "str"
        elif ret.isdigit():
            return "int"
        elif "." in ret and ret.replace(".", "").isdigit():
            return "float"
        elif ret == "None":
            continue
        elif ret.startswith("[") or ret.startswith("[]"):
            return "List"
        elif ret.startswith("{") or ret.startswith("{}"):
            return "Dict"
        elif ret == "{}":
            return "Dict[str, Any]"
        elif ret == "[]":
            return "List[Any]"

    # If we have mixed return types, use Any
    unique_types = set()
    for ret in return_statements:
        if ret == "None":
            unique_types.add("None")
        elif ret in ["True", "False"]:
            unique_types.add("bool")
        elif ret.startswith('"') or ret.startswith("'"):
            unique_types.add("str")
        else:
            unique_types.add("Any")

    if len(unique_types) == 1:
        return list(unique_types)[0]
    elif len(unique_types) == 2 and "None" in unique_types:
        other_type = [t for t in unique_types if t != "None"][0]
        return f"Optional[{other_type}]"
    else:
        return "Any"


def main():
    """Main function."""

    # Check for dry-run mode (flag already processed in __main__)
    apply_requested = getattr(main, "apply_mode", False)
    dry_run = not apply_requested

    if dry_run:
        print("DRY RUN MODE - No files will be modified")
        print("=" * 50)
    else:
        print("LIVE MODE - Files will be modified")
        print("=" * 50)

    base_path = Path("C:/git/hive")

    # Focus on specific directories with type hint violations
    target_dirs = [
        base_path / "apps/ecosystemiser/examples",
        base_path / "apps/ecosystemiser/scripts",
        base_path / "packages/hive-errors/src",
        base_path / "packages/hive-performance/src",
    ]

    files_modified = 0
    total_files = 0

    for target_dir in target_dirs:
        if not target_dir.exists():
            continue

        print(f"\nProcessing directory: {target_dir.relative_to(base_path)}")

        for py_file in target_dir.rglob("*.py"):
            total_files += 1
            if add_missing_return_types(py_file, dry_run):
                files_modified += 1

    print("\nSummary:")
    print(f"Total files processed: {total_files}")
    print(f"Files {'would be' if dry_run else 'were'} modified: {files_modified}")

    if dry_run and files_modified > 0:
        print("\nTo apply changes, run with: --apply")


if __name__ == "__main__":
    # Handle --apply flag by removing dry-run behavior
    apply_mode = "--apply" in sys.argv
    if apply_mode:
        # Remove both --apply and dry-run flags
        sys.argv = [arg for arg in sys.argv if arg not in ["--apply", "--dry-run", "-n"]]

    # Pass apply mode to main function
    main.apply_mode = apply_mode
    main()
