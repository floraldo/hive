#!/usr/bin/env python3
"""
Targeted comma fixing script for remaining Hive syntax errors.
Focuses on the specific patterns identified in the Code Red crisis.
"""

import ast
import re
import subprocess
import sys
from pathlib import Path


def find_files_with_syntax_errors():
    """Find all Python files with syntax errors using pytest."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only"],
            cwd="C:\\git\\hive",
            capture_output=True,
            text=True
        )

        # Extract files with syntax errors from pytest output
        error_files = []
        lines = result.stderr.split('\n')

        for line in lines:
            if "SyntaxError" in line and "Perhaps you forgot a comma?" in line:
                # Look for file path in previous lines
                for i in range(len(lines)):
                    if line in lines[i]:
                        # Look backwards for the file path
                        for j in range(max(0, i-10), i):
                            if "File \"" in lines[j] and ".py" in lines[j]:
                                file_match = re.search(r'File "([^"]+\.py)"', lines[j])
                                if file_match:
                                    error_files.append(file_match.group(1))
                                    break

        return list(set(error_files))  # Remove duplicates
    except Exception as e:
        print(f"Error finding syntax error files: {e}")
        return []


def fix_comma_patterns_in_file(filepath):
    """Fix missing comma patterns in a single file."""
    print(f"Fixing comma patterns in: {filepath}")

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content
        fixes_applied = 0

        # Pattern 1: Function definition parameters - missing comma after self/cls
        pattern1 = re.compile(r'def\s+\w+\(\s*(self|cls)\s+(\w+[^,)]*)', re.MULTILINE)
        content = pattern1.sub(r'def \g<0>(\1, \2', content)
        if content != original_content:
            fixes_applied += 1
            original_content = content

        # Pattern 2: Function calls - missing commas between arguments
        # Look for lines ending with identifier/string/number without comma, followed by line with identifier
        lines = content.split('\n')
        fixed_lines = []

        for i, line in enumerate(lines):
            fixed_line = line

            # Check if this line is inside a function call and missing comma
            if i < len(lines) - 1:
                next_line = lines[i + 1].strip()

                # Pattern: line ends with value, next line starts with parameter name
                if (re.search(r'["\'\w\d\]}\)]\s*$', line.strip()) and
                    re.search(r'^\s*\w+\s*[=:]', next_line) and
                    not line.strip().endswith(',') and
                    not line.strip().endswith('(') and
                    '"""' not in line):

                    # Add comma to current line
                    fixed_line = line.rstrip() + ','
                    fixes_applied += 1

            fixed_lines.append(fixed_line)

        content = '\n'.join(fixed_lines)

        # Pattern 3: Dictionary entries - missing commas between key-value pairs
        # This is trickier, let's use a more targeted approach
        dict_pattern = re.compile(r'(\w+\s*=\s*[^,\n]+)\s*\n\s*(\w+\s*=)', re.MULTILINE)
        matches = dict_pattern.findall(content)
        if matches:
            content = dict_pattern.sub(r'\1,\n    \2', content)
            fixes_applied += len(matches)

        # Only write if we made fixes
        if fixes_applied > 0:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Applied {fixes_applied} comma fixes to {filepath}")
            return True
        else:
            print(f"No comma patterns found in {filepath}")
            return False

    except Exception as e:
        print(f"Error fixing {filepath}: {e}")
        return False


def test_syntax_after_fix(filepath):
    """Test if file has valid syntax after fixes."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
        ast.parse(source, filename=str(filepath))
        return True, "OK"
    except SyntaxError as e:
        return False, f"SyntaxError line {e.lineno}: {e.msg}"
    except Exception as e:
        return False, f"Error: {e}"


def main():
    """Main comma fixing workflow."""
    print("Starting targeted comma fixing for Code Red Stabilization...")

    # Find files with syntax errors
    error_files = find_files_with_syntax_errors()

    if not error_files:
        print("No syntax error files found via pytest!")
        return

    print(f"Found {len(error_files)} files with syntax errors:")
    for f in error_files:
        print(f"  - {f}")

    # Fix comma patterns in each file
    total_fixes = 0
    successful_fixes = 0

    for filepath_str in error_files:
        filepath = Path(filepath_str)

        if not filepath.exists():
            print(f"File not found: {filepath}")
            continue

        # Apply comma fixes
        if fix_comma_patterns_in_file(filepath):
            successful_fixes += 1

            # Test syntax after fix
            is_valid, message = test_syntax_after_fix(filepath)
            if is_valid:
                print(f"OK {filepath}: Syntax now valid")
            else:
                print(f"WARNING {filepath}: Still has issues - {message}")

        total_fixes += 1

    print(f"\nFixed comma patterns in {successful_fixes}/{total_fixes} files")
    print("Re-running pytest to check progress...")

    # Test overall progress
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only"],
            cwd="C:\\git\\hive",
            capture_output=True,
            text=True,
            timeout=60
        )

        if "SyntaxError" not in result.stderr:
            print("SUCCESS: No more syntax errors detected!")
        else:
            remaining_errors = result.stderr.count("SyntaxError")
            print(f"Progress: Reduced syntax errors (still {remaining_errors} remaining)")
    except Exception as e:
        print(f"Error testing progress: {e}")


if __name__ == "__main__":
    main()