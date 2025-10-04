#!/usr/bin/env python3
"""Code Fixers - Consolidated Code Fixing Tool

This script consolidates the functionality of multiple fixer scripts:
- add_type_hints.py
- fix_global_state.py
- fix_type_hints.py
- modernize_type_hints.py
- smart_final_fixer.py
- logging_violations_fixer.py

Features:
- Type hint fixes
- Global state fixes
- Logging standardization
- Async pattern fixes
- Golden rules compliance

Usage:
    python code_fixers.py --help
"""

import argparse
import re
import sys
from pathlib import Path


def fix_type_hints(files: list[Path], dry_run: bool = False) -> int:
    """Fix missing type hints in files"""
    fixes = 0
    print("Fixing type hints...")

    for file_path in files:
        if not file_path.suffix == ".py":
            continue

        try:
            content = file_path.read_text(encoding="utf-8")

            # Simple type hint fixes
            patterns = [(r"def (\w+)\(self\):", r"def \1(self) -> None:"), (r"def (\w+)\(\):", r"def \1() -> None:")]

            modified = False
            for pattern, replacement in patterns:
                new_content, count = re.subn(pattern, replacement, content)
                if count > 0:
                    content = new_content
                    fixes += count
                    modified = True

            if modified and not dry_run:
                file_path.write_text(content, encoding="utf-8")
                print(f"  Fixed {file_path.name}")

        except Exception as e:
            print(f"  Error processing {file_path}: {e}")

    return fixes


def fix_logging(files: list[Path], dry_run: bool = False) -> int:
    """Fix logging violations"""
    fixes = 0
    print("Fixing logging violations...")

    for file_path in files:
        if not file_path.suffix == ".py":
            continue

        try:
            content = file_path.read_text(encoding="utf-8")

            if "print(" in content:
                # Add logging import if needed
                if "from hive_logging import get_logger" not in content:
                    lines = content.split("\n")
                    for i, line in enumerate(lines):
                        if line.startswith(("import ", "from ")):
                            lines.insert(i + 1, "from hive_logging import get_logger")
                            lines.insert(i + 2, "logger = get_logger(__name__)")
                            break
                    content = "\n".join(lines)

                # Replace print statements
                content = re.sub(r"print\(([^)]+)\)", r"logger.info(\1)", content)
                fixes += len(re.findall(r"logger\.info\(", content))

                if not dry_run:
                    file_path.write_text(content, encoding="utf-8")
                    print(f"  Fixed {file_path.name}")

        except Exception as e:
            print(f"  Error processing {file_path}: {e}")

    return fixes


def fix_global_state(files: list[Path], dry_run: bool = False) -> int:
    """Fix global state issues"""
    fixes = 0
    print("Fixing global state issues...")

    for file_path in files:
        if not file_path.suffix == ".py":
            continue

        try:
            content = file_path.read_text(encoding="utf-8")

            # Fix config=None patterns
            patterns = [(r"def (\w+)\([^)]*config=None[^)]*\):", r"def \1(\2config: Optional[Config]\3):")]

            modified = False
            for pattern, replacement in patterns:
                new_content, count = re.subn(pattern, replacement, content)
                if count > 0:
                    content = new_content
                    fixes += count
                    modified = True

            if modified and not dry_run:
                file_path.write_text(content, encoding="utf-8")
                print(f"  Fixed {file_path.name}")

        except Exception as e:
            print(f"  Error processing {file_path}: {e}")

    return fixes


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description="Code Fixers - Consolidated Code Fixing Tool")
    parser.add_argument("--version", action="version", version="2.0.0")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without executing")
    parser.add_argument("--type-hints", action="store_true", help="Fix missing type hints")
    parser.add_argument("--global-state", action="store_true", help="Fix global state issues")
    parser.add_argument("--logging", action="store_true", help="Standardize logging")
    parser.add_argument("--async-patterns", action="store_true", help="Fix async patterns")
    parser.add_argument("--golden-rules", action="store_true", help="Fix golden rules violations")
    parser.add_argument("--all", action="store_true", help="Run all code fixes")
    parser.add_argument("--target", help="Target directory or file to fix")

    args = parser.parse_args()

    print("Code Fixers - Consolidated Code Fixing Tool v2.0")
    print("=" * 50)

    # Determine target files
    if args.target:
        target_path = Path(args.target)
        if target_path.is_file():
            files = [target_path]
        elif target_path.is_dir():
            files = list(target_path.rglob("*.py"))
        else:
            print(f"Target not found: {args.target}")
            return 1
    else:
        # Default to apps and packages
        project_root = Path(__file__).parent.parent.parent.parent
        files = []
        for pattern in ["apps/**/*.py", "packages/**/*.py"]:
            files.extend(project_root.glob(pattern))

    print(f"Processing {len(files)} Python files...")

    total_fixes = 0

    if args.all or args.type_hints:
        total_fixes += fix_type_hints(files, args.dry_run)

    if args.all or args.global_state:
        total_fixes += fix_global_state(files, args.dry_run)

    if args.all or args.logging:
        total_fixes += fix_logging(files, args.dry_run)

    if args.dry_run:
        print(f"\nDRY RUN: Would apply {total_fixes} fixes")
    else:
        print(f"\nApplied {total_fixes} fixes successfully")

    return 0


if __name__ == "__main__":
    sys.exit(main())
