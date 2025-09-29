#!/usr/bin/env python3
"""Fix false positives in the Golden Rules validator."""

import re
from pathlib import Path

def fix_validator():
    """Fix the architectural validator to reduce false positives."""

    validator_path = Path("/c/git/hive/packages/hive-tests/src/hive_tests/architectural_validators.py")

    with open(validator_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find and replace the print detection section
    # The current logic has issues with strings containing "print("

    # Better print detection pattern
    better_print_detection = '''
                        # Check for actual print() statements
                        if "print(" in line and not line.strip().startswith("#"):
                            stripped_line = line.strip()

                            # Skip if print( appears inside a string literal
                            # Check for various string patterns
                            in_string = False

                            # Pattern 1: "...print(..." or '...print(...'
                            if ('"' in line and 'print(' in line):
                                # Check if print( is between quotes
                                parts = line.split('"')
                                for i in range(1, len(parts), 2):  # Odd indices are inside quotes
                                    if 'print(' in parts[i]:
                                        in_string = True
                                        break

                            if not in_string and ("'" in line and 'print(' in line):
                                # Check single quotes
                                parts = line.split("'")
                                for i in range(1, len(parts), 2):
                                    if 'print(' in parts[i]:
                                        in_string = True
                                        break

                            # Pattern 2: Docstrings or multiline strings
                            if '"""' in line or "'''" in line:
                                in_string = True

                            # Pattern 3: Comments (even inline)
                            if '#' in line:
                                comment_start = line.index('#')
                                if 'print(' in line[comment_start:]:
                                    in_string = True

                            if not in_string and (
                                not stripped_line.startswith("from ")
                                and not stripped_line.startswith("import ")
                                and not stripped_line.startswith('"')
                                and not stripped_line.startswith("'")
                                and not (is_cli_tool and in_main_section)
                            ):
                                violations.append(
                                    f"Print statement in production code: {py_file.relative_to(project_root)}:{line_num}"
                                )'''

    # This is too complex to replace with simple string replacement
    # Let's just add better checks
    print("Validator improvements would require manual editing")
    print("Recommend: Add better string detection to avoid false positives")
    return False

if __name__ == "__main__":
    fix_validator()
