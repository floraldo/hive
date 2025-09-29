#!/usr/bin/env python3
"""
Fix sys.path manipulation violations in EcoSystemiser

This script removes sys.path.insert() calls and ensures proper imports work
through the Poetry workspace setup.
"""

import re
from pathlib import Path
from typing import List


class SysPathFixer:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.fixed_files = []

    def fix_file(self, file_path: Path) -> bool:
        """Fix sys.path violations in a single file."""
        if not file_path.exists():
            return False

        content = file_path.read_text(encoding="utf-8")
        original_content = content

        # Remove sys.path.insert() lines
        content = re.sub(r"^sys\.path\.insert\(.*\)\n?", "", content, flags=re.MULTILINE)

        # Remove comments about adding to path
        content = re.sub(r"^# Add.*to path\n?", "", content, flags=re.MULTILINE)
        content = re.sub(r"^# Add.*paths?\n?", "", content, flags=re.MULTILINE)

        # Clean up any extra blank lines
        content = re.sub(r"\n\n\n+", "\n\n", content)

        if content != original_content:
            file_path.write_text(content, encoding="utf-8")
            self.fixed_files.append(str(file_path))
            print(f"Fixed: {file_path}")
            return True

        return False

    def fix_ecosystemiser_files(self):
        """Fix all ecosystemiser files with sys.path violations."""
        ecosystemiser_root = self.project_root / "apps" / "ecosystemiser"

        # Files identified in golden rule violations
        violation_files = [
            "debug_milp.py",
            "debug_milp_extraction.py",
            "debug_objective.py",
            "test_milp_minimal.py",
            "scripts/extract_yearly_profiles.py",
            "scripts/integrate_climate_data.py",
            "tests/test_corrected_validation.py",
            "tests/test_simple_golden_validation.py",
            "tests/test_milp_validation.py",
        ]

        for file_rel_path in violation_files:
            file_path = ecosystemiser_root / file_rel_path
            if file_path.exists():
                self.fix_file(file_path)

        # Also scan for any other files with sys.path violations
        for py_file in ecosystemiser_root.rglob("*.py"):
            if py_file.is_file():
                content = py_file.read_text(encoding="utf-8")
                if "sys.path.insert" in content:
                    self.fix_file(py_file)

    def create_summary(self):
        """Create a summary of fixes applied."""
        summary_path = self.project_root / "docs/reports/syspath_fixes_summary.md"

        summary_content = f"""# Sys.Path Violations Fix Summary

**Generated**: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Files Fixed

{chr(10).join(f"- {file}" for file in self.fixed_files)}

## Changes Made

1. Removed all `sys.path.insert()` calls
2. Removed path manipulation comments
3. Cleaned up extra blank lines

## Next Steps

1. Ensure Poetry workspace is properly installed: `poetry install`
2. Run tests to verify imports still work
3. Run golden tests to verify violations are resolved

## Notes

The EcoSystemiser should now rely on proper Poetry workspace imports instead of
path manipulation. All imports should work through the installed packages in
development mode.

---

*Fixed {len(self.fixed_files)} files with sys.path violations.*
"""

        summary_path.write_text(summary_content)
        print(f"Created summary at: {summary_path}")


if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent
    fixer = SysPathFixer(project_root)
    fixer.fix_ecosystemiser_files()
    fixer.create_summary()
    print(f"Fixed {len(fixer.fixed_files)} files with sys.path violations.")
