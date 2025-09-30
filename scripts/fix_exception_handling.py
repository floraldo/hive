#!/usr/bin/env python3
"""
Fix exception handling issues (E722, B904)
- E722: Replace bare except with except Exception
- B904: Add exception chaining with 'from e'
"""

import re
import subprocess
from pathlib import Path


def get_files_with_violations():
    """Get list of files with E722/B904 violations"""
    result = subprocess.run(
        ["python", "-m", "ruff", "check", ".", "--select", "E722,B904", "--output-format=json"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0 and not result.stdout:
        print("No JSON output from ruff")
        return []

    import json
    try:
        data = json.loads(result.stdout)
        files = list(set(d["filename"] for d in data))
        return files
    except json.JSONDecodeError:
        print("Failed to parse ruff JSON output")
        return []


def fix_bare_except(content):
    """Replace bare except with except Exception"""
    # Pattern: except: or except :
    pattern = r'(\s+)except\s*:\s*$'
    replacement = r'\1except Exception:'

    return re.sub(pattern, replacement, content, flags=re.MULTILINE)


def fix_exception_chaining(content):
    """Add exception chaining where missing"""
    # This is complex - needs AST analysis
    # For now, just skip this as it requires understanding context
    return content


def main():
    """Main fixing function"""
    files = get_files_with_violations()
    print(f"Found {len(files)} files with E722/B904 violations")

    fixed_count = 0

    for file_path_str in files:
        file_path = Path(file_path_str)
        if not file_path.exists():
            continue

        try:
            content = file_path.read_text(encoding="utf-8")
            original = content

            # Fix bare except
            content = fix_bare_except(content)

            if content != original:
                file_path.write_text(content, encoding="utf-8")
                fixed_count += 1
                print(f"Fixed: {file_path}")

        except Exception as e:
            print(f"Error processing {file_path}: {e}")

    print(f"\nFixed {fixed_count} files")

    # Check new violation count
    result = subprocess.run(
        ["python", "-m", "ruff", "check", ".", "--statistics"],
        capture_output=True,
        text=True,
    )
    print("\nNew violation count:")
    for line in result.stdout.split("\n"):
        if "Found" in line or "E722" in line or "B904" in line:
            print(line)


if __name__ == "__main__":
    main()