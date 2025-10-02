#!/usr/bin/env python3
"""
Cleanup script to safely delete redundant comma fixing scripts.
All patterns are now consolidated in emergency_syntax_fix_consolidated.py
"""

import shutil
from pathlib import Path

# Scripts to DELETE (redundant - patterns consolidated)
REDUNDANT_SCRIPTS = [
    # Main scripts directory
    "scripts/aggressive_comma_fix.py",
    "scripts/comprehensive_comma_fixer.py",
    "scripts/direct_comma_fixer.py",
    "scripts/emergency_comma_fix.py",
    "scripts/final_comma_fix.py",
    "scripts/fix_comma_overcorrections.py",
    "scripts/pattern_comma_fixer.py",
    "scripts/remove_invalid_trailing_commas.py",
    "scripts/safe_comma_fixer.py",
    "scripts/simple_comma_fixer.py",
    "scripts/targeted_comma_fix.py",
    "scripts/targeted_comma_fixer.py",
    "scripts/emergency_syntax_fix.py",
    "scripts/master_syntax_fixer.py",
    "scripts/final_syntax_fixer.py",
    "scripts/code_red_stabilization.py",
    "scripts/fix_critical_files.py",
    "scripts/fix_async_agents.py",
    "scripts/fix_agent_targeted.py",
    "scripts/final_agent_fix.py",
    "scripts/master_cleanup.py",
    # Archive comma_fixes directory (entire directory)
    "scripts/archive/comma_fixes/",
    # Archive syntax_fixes directory (entire directory)
    "scripts/archive/syntax_fixes/",
    # Archive misplaced directory
    "scripts/archive/misplaced/",
    # Archive individual files
    "scripts/archive/fix_syntax_errors.py",
    "scripts/archive/fix_dict_commas.py",
    "scripts/archive/fix_all_syntax_errors.py",
]

# Scripts to KEEP (unique functionality)
KEEP_SCRIPTS = [
    "scripts/emergency_syntax_fix_consolidated.py",  # Our master script
]


def delete_file_or_dir(path_str: str) -> bool:
    """Safely delete a file or directory."""
    try:
        path = Path(path_str)
        if not path.exists():
            print(f"  WARNING: Not found: {path_str}")
            return False

        if path.is_file():
            path.unlink()
            print(f"  SUCCESS: Deleted file: {path_str}")
        elif path.is_dir():
            shutil.rmtree(path)
            print(f"  SUCCESS: Deleted directory: {path_str}")
        return True
    except Exception as e:
        print(f"  ERROR: Error deleting {path_str}: {e}")
        return False


def main():
    """Delete all redundant comma fixing scripts."""
    print("CLEANING UP REDUNDANT COMMA FIXING SCRIPTS")
    print("=" * 60)
    print("All patterns are now consolidated in emergency_syntax_fix_consolidated.py")
    print()

    deleted_count = 0
    failed_count = 0

    print("Deleting redundant scripts...")
    for script_path in REDUNDANT_SCRIPTS:
        if delete_file_or_dir(script_path):
            deleted_count += 1
        else:
            failed_count += 1

    print()
    print("=" * 60)
    print("CLEANUP SUMMARY")
    print("=" * 60)
    print(f"SUCCESS: Successfully deleted: {deleted_count} items")
    print(f"FAILED: Failed to delete: {failed_count} items")
    print()
    print("KEPT: emergency_syntax_fix_consolidated.py (master script)")
    print("All patterns from 46+ scripts are now consolidated!")

    if failed_count == 0:
        print("\nCLEANUP COMPLETE - All redundant scripts removed!")
    else:
        print(f"\nWARNING: {failed_count} items could not be deleted - check manually")


if __name__ == "__main__":
    main()
