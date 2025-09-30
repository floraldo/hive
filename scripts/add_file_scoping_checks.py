#!/usr/bin/env python3
"""
Script to add file-level scoping checks after rglob iterations.
"""
from pathlib import Path
import re

def add_scoping_checks():
    """Add _should_validate_file checks after each rglob loop."""
    file_path = Path("packages/hive-tests/src/hive_tests/architectural_validators.py")
    content = file_path.read_text()
    lines = content.split('\n')

    output_lines = []
    i = 0
    modifications = 0

    while i < len(lines):
        line = lines[i]
        output_lines.append(line)

        # Check if this is a rglob line
        if '.rglob(' in line and 'for py_file in' in line:
            # Look ahead for the next non-comment, non-blank line after any continue statements
            j = i + 1
            found_continue = False
            indent_level = None

            # Skip ahead to find where to insert
            while j < len(lines):
                next_line = lines[j]
                stripped = next_line.strip()

                # Get indent level from first real line
                if indent_level is None and stripped and not stripped.startswith('#'):
                    indent_level = len(next_line) - len(next_line.lstrip())

                # Check if it's already there
                if '_should_validate_file' in next_line:
                    found_continue = True
                    break

                # Check for existing continue statements or blank lines
                if stripped.startswith('continue') or stripped.startswith('if') or not stripped or stripped.startswith('#'):
                    output_lines.append(next_line)
                    i = j
                    j += 1
                    continue

                # Found the place to insert
                if stripped and not stripped.startswith('#'):
                    # Insert the scoping check here
                    if indent_level is not None and not found_continue:
                        check_line = ' ' * indent_level + '# File-level scoping optimization'
                        code_line = ' ' * indent_level + 'if not _should_validate_file(py_file, scope_files):'
                        continue_line = ' ' * indent_level + '    continue'
                        blank_line = ''

                        output_lines.append(check_line)
                        output_lines.append(code_line)
                        output_lines.append(continue_line)
                        output_lines.append(blank_line)
                        modifications += 1
                    break

                j += 1

        i += 1

    # Write back
    file_path.write_text('\n'.join(output_lines))
    print(f"Added {modifications} file-level scoping checks")

if __name__ == "__main__":
    add_scoping_checks()
    print("All scoping checks added")