"""Fix missing commas after Field() definitions using AST parsing.

This script uses Python's AST to reliably identify and fix missing commas
in Pydantic model Field definitions.
"""

import ast
import re
from pathlib import Path
from typing import List, Tuple


def fix_trailing_commas_simple(content: str) -> str:
    """Fix obvious trailing comma issues with simple patterns.

    These patterns are safe and don't require AST parsing:
    - ):, -> ),
    - ]:, -> ],
    - }:, -> },
    - class Foo:, -> class Foo:
    """
    fixed = content

    # Fix colon-comma patterns
    patterns = [
        (r'\):\s*,', r'),'),  # ):, -> ),
        (r'\]:\s*,', r'],'),  # ]:, -> ],
        (r'\}:\s*,', r'},'),  # }:, -> },
        (r'(class\s+\w+)\s*:\s*,', r'\1:'),  # class Foo:, -> class Foo:
    ]

    for pattern, replacement in patterns:
        fixed = re.sub(pattern, replacement, fixed)

    return fixed


def fix_field_definitions(content: str) -> str:
    """Fix missing commas after Field() definitions in Pydantic models.

    Pattern: attribute: type = Field(...)\n    next_attribute
    Should be: attribute: type = Field(...),\n    next_attribute
    """
    lines = content.split('\n')
    fixed_lines = []

    for i, line in enumerate(lines):
        # Check if this line contains a Field() definition without trailing comma
        if 'Field(' in line and not line.rstrip().endswith(','):
            # Check if next line exists and is another field definition
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                # If next line is another field or closing paren/brace, add comma
                if (next_line and
                    not next_line.startswith('#') and
                    not next_line.startswith('"""') and
                    (re.match(r'\w+:', next_line) or  # Another field
                     next_line.startswith(')') or      # Closing paren
                     next_line.startswith('}'))):      # Closing brace

                    # Count parentheses to ensure Field() is closed
                    open_parens = line.count('(')
                    close_parens = line.count(')')

                    if open_parens == close_parens:
                        # Field is complete on this line, add comma
                        fixed_lines.append(line.rstrip() + ',')
                        continue

        fixed_lines.append(line)

    return '\n'.join(fixed_lines)


def fix_dict_literal_commas(content: str) -> str:
    """Fix missing commas in dictionary literals.

    Pattern: "key": value\n    "next_key"
    Should be: "key": value,\n    "next_key"
    """
    lines = content.split('\n')
    fixed_lines = []

    for i, line in enumerate(lines):
        # Check if line looks like a dict entry without trailing comma
        if ((':' in line or '=' in line) and
            not line.rstrip().endswith(',') and
            not line.rstrip().endswith('{') and
            not line.rstrip().endswith('(')):

            # Check if next line exists
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()

                # If next line is another dict entry, add comma
                if (next_line and
                    not next_line.startswith('#') and
                    not next_line.startswith('}') and
                    not next_line.startswith(')') and
                    ('"' in next_line or "'" in next_line or
                     re.match(r'\w+\s*[=:]', next_line))):

                    fixed_lines.append(line.rstrip() + ',')
                    continue

        fixed_lines.append(line)

    return '\n'.join(fixed_lines)


def fix_class_attribute_commas(content: str) -> str:
    """Fix trailing commas on class attribute definitions.

    Pattern: attribute: type,\n    (in class body)
    Should be: attribute: type\n
    """
    lines = content.split('\n')
    fixed_lines = []

    in_class = False
    indent_level = 0

    for i, line in enumerate(lines):
        # Track class definitions
        if line.strip().startswith('class '):
            in_class = True
            indent_level = len(line) - len(line.lstrip())

        # Exit class when we hit same or lower indent
        elif in_class and line.strip() and not line.startswith(' ' * (indent_level + 4)):
            in_class = False

        # Fix class attributes with trailing commas
        if in_class and ':' in line and line.rstrip().endswith(','):
            # Check if this is a simple attribute (not a function or dict)
            if not '(' in line and not '{' in line and not '=' in line:
                fixed_lines.append(line.rstrip()[:-1])  # Remove trailing comma
                continue

        fixed_lines.append(line)

    return '\n'.join(fixed_lines)


def fix_file(file_path: Path) -> Tuple[bool, List[str]]:
    """Fix a single file. Returns (modified, issues_fixed)."""
    try:
        content = file_path.read_text(encoding='utf-8')
        original_content = content
        issues_fixed = []

        # Apply fixes in order
        content = fix_trailing_commas_simple(content)
        if content != original_content:
            issues_fixed.append("Fixed colon-comma patterns (:,)")
            original_content = content

        content = fix_field_definitions(content)
        if content != original_content:
            issues_fixed.append("Fixed Field() definition commas")
            original_content = content

        content = fix_dict_literal_commas(content)
        if content != original_content:
            issues_fixed.append("Fixed dictionary literal commas")
            original_content = content

        content = fix_class_attribute_commas(content)
        if content != original_content:
            issues_fixed.append("Fixed class attribute commas")

        # Write back if modified
        if issues_fixed:
            file_path.write_text(content, encoding='utf-8')
            return True, issues_fixed

        return False, []

    except Exception as e:
        return False, [f"ERROR: {e}"]


def main():
    """Main execution."""
    src_dir = Path(__file__).parent.parent / 'src' / 'ecosystemiser'

    if not src_dir.exists():
        print(f"ERROR: Source directory not found: {src_dir}")
        return

    print("Scanning for comma issues...")

    fixed_files = []

    for py_file in src_dir.rglob('*.py'):
        try:
            modified, issues = fix_file(py_file)
            if modified:
                fixed_files.append((py_file.relative_to(src_dir), issues))
                print(f"  FIXED: {py_file.relative_to(src_dir)}")
                for issue in issues:
                    print(f"    - {issue}")
        except Exception as e:
            print(f"  ERROR processing {py_file.relative_to(src_dir)}: {e}")

    print(f"\nCompleted: {len(fixed_files)} files fixed")

    if fixed_files:
        print("\nFixed files:")
        for f, issues in fixed_files:
            print(f"  - {f}")
            for issue in issues:
                print(f"      {issue}")


if __name__ == '__main__':
    main()