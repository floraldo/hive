#!/usr/bin/env python3
"""
PVGIS Circular Reversion Analysis
================================

This script specifically analyzes the pvgis.py circular reversion issue
where line 607 keeps reverting from fixed to broken state.
"""

import subprocess
import time
from datetime import datetime
from pathlib import Path


def check_pvgis_file_status():
    """Check the current status of pvgis.py file"""
    print("🔍 PVGIS FILE STATUS ANALYSIS")
    print("=" * 50)

    pvgis_path = Path("apps/ecosystemiser/src/ecosystemiser/profile_loader/climate/adapters/pvgis.py")

    if not pvgis_path.exists():
        print("❌ pvgis.py does not exist!")
        return False

    print(f"✅ pvgis.py exists at: {pvgis_path}")
    print(f"📏 File size: {pvgis_path.stat().st_size} bytes")
    print(f"🕒 Last modified: {datetime.fromtimestamp(pvgis_path.stat().st_mtime)}")

    # Check git status
    result = subprocess.run(f"git status --porcelain {pvgis_path}", shell=True, capture_output=True, text=True)
    if result.stdout.strip():
        print(f"📋 Git status: {result.stdout.strip()}")
    else:
        print("📋 Git status: No changes")

    return True


def analyze_problematic_line():
    """Analyze the specific problematic line 607"""
    print("\n🎯 PROBLEMATIC LINE ANALYSIS")
    print("=" * 50)

    pvgis_path = Path("apps/ecosystemiser/src/ecosystemiser/profile_loader/climate/adapters/pvgis.py")

    try:
        with open(pvgis_path) as f:
            lines = f.readlines()

        print(f"📄 Total lines in file: {len(lines)}")

        # Check around line 607
        start_line = max(600, 0)
        end_line = min(615, len(lines))

        print(f"\n🔍 Lines {start_line + 1}-{end_line} (around problematic line 607):")
        for i in range(start_line, end_line):
            line_num = i + 1
            line_content = lines[i].rstrip()

            # Highlight the problematic line
            if "pvgis_cols" in line_content:
                print(f"  {line_num:3d}: {repr(line_content)} ⚠️  <-- PROBLEMATIC LINE")
            else:
                print(f"  {line_num:3d}: {repr(line_content)}")

        # Check for syntax issues
        print("\n🔍 SYNTAX ANALYSIS:")

        # Look for the specific pattern
        problematic_lines = []
        for i, line in enumerate(lines):
            if "pvgis_cols = {" in line and line.strip().endswith(",") and not line.strip().endswith("{"):
                problematic_lines.append((i + 1, line.strip()))

        if problematic_lines:
            print("❌ Found problematic patterns:")
            for line_num, content in problematic_lines:
                print(f"  Line {line_num}: {repr(content)}")
        else:
            print("✅ No problematic patterns found")

    except Exception as e:
        print(f"❌ Error reading file: {e}")


def check_ruff_configuration():
    """Check ruff configuration that might affect this file"""
    print("\n🔧 RUFF CONFIGURATION CHECK")
    print("=" * 50)

    # Check root pyproject.toml
    pyproject_path = Path("pyproject.toml")
    if pyproject_path.exists():
        with open(pyproject_path) as f:
            content = f.read()

        print("📋 Root pyproject.toml ruff settings:")

        # Extract ruff section
        lines = content.split("\n")
        in_ruff = False
        ruff_lines = []

        for line in lines:
            if line.strip().startswith("[tool.ruff"):
                in_ruff = True
                ruff_lines.append(line)
            elif in_ruff and line.strip().startswith("[") and not line.strip().startswith("[tool.ruff"):
                break
            elif in_ruff:
                ruff_lines.append(line)

        for line in ruff_lines:
            print(f"  {line}")

            # Check for skip-magic-trailing-comma
            if "skip-magic-trailing-comma" in line:
                if "true" in line:
                    print("    ⚠️  WARNING: skip-magic-trailing-comma = true (might cause issues)")
                elif "false" in line:
                    print("    ✅ skip-magic-trailing-comma = false (correct setting)")

    # Check for other pyproject.toml files in the ecosystemiser directory
    ecosystemiser_pyproject = Path("apps/ecosystemiser/pyproject.toml")
    if ecosystemiser_pyproject.exists():
        print(f"\n📋 Ecosystemiser pyproject.toml exists at: {ecosystemiser_pyproject}")

        with open(ecosystemiser_pyproject) as f:
            content = f.read()

        if "[tool.ruff" in content:
            print("  ⚠️  WARNING: Has ruff configuration (might conflict with root config)")
        else:
            print("  ✅ No ruff configuration (inherits from root)")


def check_active_processes():
    """Check for active processes that might be modifying the file"""
    print("\n⚡ ACTIVE PROCESSES CHECK")
    print("=" * 50)

    # Check for ruff processes
    result = subprocess.run("ps aux | grep ruff | grep -v grep", shell=True, capture_output=True, text=True)
    if result.stdout:
        print("🔍 Active ruff processes:")
        print(result.stdout)
    else:
        print("✅ No active ruff processes")

    # Check for VS Code processes
    result = subprocess.run(
        "ps aux | grep -i 'visual studio code' | grep -v grep", shell=True, capture_output=True, text=True,
    )
    if result.stdout:
        print("\n💻 Active VS Code processes:")
        print(result.stdout)
    else:
        print("\n✅ No active VS Code processes")

    # Check for Python processes that might be running formatters
    result = subprocess.run(
        "ps aux | grep python | grep -E '(format|lint|ruff)' | grep -v grep", shell=True, capture_output=True, text=True,
    )
    if result.stdout:
        print("\n🐍 Python processes with format/lint/ruff:")
        print(result.stdout)
    else:
        print("\n✅ No Python format/lint/ruff processes")


def test_file_modification():
    """Test if the file gets automatically modified"""
    print("\n🧪 FILE MODIFICATION TEST")
    print("=" * 50)
    print("This test will make a small change to pvgis.py and monitor if it gets reverted...")

    pvgis_path = Path("apps/ecosystemiser/src/ecosystemiser/profile_loader/climate/adapters/pvgis.py")

    if not pvgis_path.exists():
        print("❌ pvgis.py not found, cannot run test")
        return

    # Record initial state
    initial_mtime = pvgis_path.stat().st_mtime
    print(f"📅 Initial modification time: {datetime.fromtimestamp(initial_mtime)}")

    # Read the file content
    with open(pvgis_path) as f:
        original_content = f.read()

    # Find a safe line to modify (add a comment)
    lines = original_content.split("\n")
    test_line = None
    test_line_num = None

    # Look for a line with just whitespace or a comment
    for i, line in enumerate(lines):
        if line.strip().startswith("#") or line.strip() == "":
            test_line = i
            test_line_num = i + 1
            break

    if test_line is None:
        print("❌ Could not find a safe line to modify for testing")
        return

    print(f"🎯 Will test modification on line {test_line_num}: {repr(lines[test_line])}")

    # Make a test modification
    test_comment = f"# TEST MODIFICATION AT {datetime.now().isoformat()}"
    lines[test_line] = test_comment

    modified_content = "\n".join(lines)

    try:
        # Write the modification
        with open(pvgis_path, "w") as f:
            f.write(modified_content)

        print(f"✅ Made test modification: {test_comment}")
        print("⏱️  Waiting 5 seconds to see if it gets reverted...")

        # Wait and check
        for i in range(5):
            time.sleep(1)
            current_mtime = pvgis_path.stat().st_mtime
            if current_mtime != initial_mtime:
                print(f"  {i + 1}/5 - File modified at {datetime.fromtimestamp(current_mtime)}")

                # Check if our modification is still there
                with open(pvgis_path) as f:
                    current_content = f.read()

                if test_comment in current_content:
                    print("  ✅ Our modification is still present")
                else:
                    print("  ❌ Our modification was REVERTED!")
                    print("  🚨 CIRCULAR REVERSION CONFIRMED!")
                    return True
            else:
                print(f"  {i + 1}/5 - No changes detected")

        print("✅ Test modification remained intact (no circular reversion detected)")

    except Exception as e:
        print(f"❌ Error during test: {e}")

    finally:
        # Restore original content
        try:
            with open(pvgis_path, "w") as f:
                f.write(original_content)
            print("🔄 Restored original file content")
        except Exception as e:
            print(f"❌ Error restoring original content: {e}")

    return False


def check_git_hooks():
    """Check git hooks that might be running ruff"""
    print("\n🔗 GIT HOOKS CHECK")
    print("=" * 50)

    # Check pre-commit configuration
    pre_commit_config = Path(".pre-commit-config.yaml")
    if pre_commit_config.exists():
        with open(pre_commit_config) as f:
            content = f.read()

        if "ruff" in content.lower():
            print("📋 Pre-commit config contains ruff:")
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if "ruff" in line.lower():
                    print(f"  Line {i + 1}: {line.strip()}")
        else:
            print("✅ Pre-commit config does not contain ruff")

    # Check actual git hooks
    git_hooks = Path(".git/hooks")
    if git_hooks.exists():
        print(f"\n📁 Git hooks directory: {git_hooks}")
        hooks = list(git_hooks.iterdir())
        if hooks:
            print("Active hooks:")
            for hook in hooks:
                if hook.is_file() and not hook.name.startswith("."):
                    print(f"  {hook.name}")
                    try:
                        with open(hook) as f:
                            hook_content = f.read()
                            if "ruff" in hook_content:
                                print("    ⚠️  Contains ruff")
                    except Exception:
                        pass
        else:
            print("✅ No active git hooks")


def main():
    """Main analysis function"""
    print("🚨 PVGIS CIRCULAR REVERSION ANALYSIS")
    print("=" * 60)
    print("Analyzing the specific circular reversion issue with pvgis.py line 607")
    print()

    # Run all checks
    if not check_pvgis_file_status():
        return

    analyze_problematic_line()
    check_ruff_configuration()
    check_active_processes()
    check_git_hooks()

    # Ask user if they want to run the modification test
    response = input("\nDo you want to run the file modification test? (y/n): ")
    if response.lower() == "y":
        circular_reversion = test_file_modification()

        if circular_reversion:
            print("\n🚨 CONCLUSION: CIRCULAR REVERSION CONFIRMED!")
            print("Some process is automatically reverting file modifications.")
            print("This needs to be investigated and fixed.")
        else:
            print("\n✅ CONCLUSION: No circular reversion detected")
            print("The issue might be intermittent or resolved.")

    print("\n📊 ANALYSIS COMPLETE")


if __name__ == "__main__":
    main()
