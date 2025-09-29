#!/usr/bin/env python
"""
Core package type hint addition for high-priority functions.

Focuses on the most critical type hint violations in hive packages.
"""

import re
import sys
from pathlib import Path


def add_comprehensive_type_hints(file_path: Path, dry_run: bool = True) -> bool:
    """Add type hints to functions with comprehensive pattern matching."""
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

    lines = content.split("\n")
    modified = False
    new_lines = []

    # Track if we need to add typing import
    needs_typing = False
    has_typing = any("from typing import" in line or "import typing" in line for line in lines)

    i = 0
    while i < len(lines):
        line = lines[i]

        # Look for function definitions without return type hints
        func_match = re.match(r"^(\s*)def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^)]*)\)\s*:(.*)$", line)
        if func_match:
            indent, func_name, params, after_colon = func_match.groups()

            # Skip if already has return type hint
            if "->" not in line:
                # Add parameter type hints if missing
                enhanced_params = enhance_parameters(params)
                if enhanced_params != params:
                    needs_typing = True

                # Try to infer return type
                return_type = infer_comprehensive_return_type(lines, i, func_name)
                if return_type:
                    if return_type not in ["None", "bool", "str", "int", "float"]:
                        needs_typing = True

                    new_line = f"{indent}def {func_name}({enhanced_params}) -> {return_type}:{after_colon}"
                    new_lines.append(new_line)
                    modified = True
                    print(f"  Enhanced {func_name}: params={enhanced_params != params}, return={return_type}")
                else:
                    # Just add enhanced parameters if no return type
                    if enhanced_params != params:
                        new_line = f"{indent}def {func_name}({enhanced_params}):{after_colon}"
                        new_lines.append(new_line)
                        modified = True
                        print(f"  Enhanced {func_name}: params only")
                    else:
                        new_lines.append(line)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

        i += 1

    # Add typing import if needed
    if modified and needs_typing and not has_typing:
        # Find the best place to add import
        import_added = False
        final_lines = []
        for i, line in enumerate(new_lines):
            if not import_added and (line.startswith("from ") or line.startswith("import ")):
                # Add before first import
                final_lines.append("from typing import Any, Dict, List, Optional")
                final_lines.append("")
                final_lines.append(line)
                import_added = True
            elif not import_added and line.strip() and not line.startswith("#"):
                # Add before first non-comment line
                final_lines.append("from typing import Any, Dict, List, Optional")
                final_lines.append("")
                final_lines.append(line)
                import_added = True
            else:
                final_lines.append(line)

        if not import_added:
            # Add at beginning if no good spot found
            final_lines = ["from typing import Any, Dict, List, Optional", ""] + new_lines

        new_lines = final_lines

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


def enhance_parameters(params: str) -> str:
    """Add type hints to parameters that are missing them."""
    if not params.strip():
        return params

    # Simple parameter enhancement patterns
    enhanced = params

    # Common patterns
    patterns = [
        (r"\bconfig\b(?!\s*:)", "config: Dict[str, Any]"),
        (r"\bdata\b(?!\s*:)", "data: Dict[str, Any]"),
        (r"\bfilepath\b(?!\s*:)", "filepath: str"),
        (r"\bfile_path\b(?!\s*:)", "file_path: str"),
        (r"\bpath\b(?!\s*:)", "path: str"),
        (r"\bname\b(?!\s*:)", "name: str"),
        (r"\bmessage\b(?!\s*:)", "message: str"),
        (r"\burl\b(?!\s*:)", "url: str"),
        (r"\bid\b(?!\s*:)", "id: str"),
        (r"\bcount\b(?!\s*:)", "count: int"),
        (r"\bsize\b(?!\s*:)", "size: int"),
        (r"\btimeout\b(?!\s*:)", "timeout: float"),
        (r"\benable\b(?!\s*:)", "enable: bool"),
        (r"\bvalid\b(?!\s*:)", "valid: bool"),
        (r"\bitems\b(?!\s*:)", "items: List[Any]"),
        (r"\bresults\b(?!\s*:)", "results: List[Any]"),
    ]

    for pattern, replacement in patterns:
        enhanced = re.sub(pattern, replacement, enhanced)

    return enhanced


def infer_comprehensive_return_type(lines: list[str], func_start: int, func_name: str) -> str | None:
    """Infer return type from function body with comprehensive patterns."""

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

    # Enhanced pattern matching
    for ret in return_statements:
        if ret in ["True", "False"]:
            return "bool"
        elif ret.startswith('"') or ret.startswith("'"):
            return "str"
        elif ret.isdigit():
            return "int"
        elif "." in ret and ret.replace(".", "").replace("-", "").isdigit():
            return "float"
        elif ret == "None":
            continue
        elif ret.startswith("[") or ret == "[]":
            return "List[Any]"
        elif ret.startswith("{") or ret == "{}":
            return "Dict[str, Any]"
        elif "dict(" in ret:
            return "Dict[str, Any]"
        elif "list(" in ret:
            return "List[Any]"
        elif ret.endswith(".json()") or "json" in ret:
            return "Dict[str, Any]"
        elif ret.endswith(".text") or "str(" in ret:
            return "str"
        elif ret.endswith("_connection") or "connection" in ret:
            return "Any"
        elif ret.endswith("_config") or "config" in ret:
            return "Dict[str, Any]"
        elif "response" in ret.lower():
            return "Any"

    # If we have mixed return types, use Union or Optional
    unique_types = set()
    for ret in return_statements:
        if ret == "None":
            unique_types.add("None")
        elif ret in ["True", "False"]:
            unique_types.add("bool")
        elif ret.startswith('"') or ret.startswith("'"):
            unique_types.add("str")
        elif ret.isdigit():
            unique_types.add("int")
        elif "." in ret and ret.replace(".", "").replace("-", "").isdigit():
            unique_types.add("float")
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

    # Check for dry-run mode
    apply_requested = getattr(main, "apply_mode", False)
    dry_run = not apply_requested

    if dry_run:
        print("DRY RUN MODE - No files will be modified")
        print("=" * 50)
    else:
        print("LIVE MODE - Files will be modified")
        print("=" * 50)

    base_path = Path("C:/git/hive")

    # Focus on high-priority core package directories
    target_dirs = [
        base_path / "packages/hive-errors/src",
        base_path / "packages/hive-config/src",
        base_path / "packages/hive-db/src",
        base_path / "packages/hive-logging/src",
        base_path / "packages/hive-performance/src",
        base_path / "packages/hive-async/src",
        base_path / "packages/hive-cache/src",
        base_path / "apps/ecosystemiser/src/ecosystemiser/core",
        base_path / "apps/guardian-agent/src/guardian_agent/core",
        base_path / "apps/ai-deployer/src/ai_deployer/core",
    ]

    files_modified = 0
    total_files = 0

    for target_dir in target_dirs:
        if not target_dir.exists():
            continue

        print(f"\nProcessing directory: {target_dir.relative_to(base_path)}")

        for py_file in target_dir.rglob("*.py"):
            if "__pycache__" in str(py_file) or ".pyc" in str(py_file):
                continue
            total_files += 1
            if add_comprehensive_type_hints(py_file, dry_run):
                files_modified += 1

    print("\nSummary:")
    print(f"Total files processed: {total_files}")
    print(f"Files {'would be' if dry_run else 'were'} modified: {files_modified}")

    if dry_run and files_modified > 0:
        print("\nTo apply changes, run with: --apply")


if __name__ == "__main__":
    # Handle --apply flag
    apply_mode = "--apply" in sys.argv
    if apply_mode:
        sys.argv = [arg for arg in sys.argv if arg != "--apply"]

    # Pass apply mode to main function
    main.apply_mode = apply_mode
    main()
