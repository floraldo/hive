#!/usr/bin/env python3
"""
Configuration Conflict Analysis
==============================

This script analyzes configuration conflicts that might cause circular ruff reversion.
It checks for conflicting settings between different configuration sources.
"""

import json
import os
from datetime import datetime
from pathlib import Path

import toml


def analyze_pyproject_toml_files():
    """Analyze all pyproject.toml files for conflicting ruff settings"""
    print("📋 PYPROJECT.TOML CONFLICT ANALYSIS")
    print("=" * 50)

    # Find all pyproject.toml files
    pyproject_files = list(Path(".").rglob("pyproject.toml"))

    print(f"Found {len(pyproject_files)} pyproject.toml files:")
    for file in pyproject_files:
        print(f"  {file}")

    print("\nAnalyzing ruff configurations...")

    ruff_configs = {}

    for file_path in pyproject_files:
        try:
            with open(file_path) as f:
                content = f.read()

            if "[tool.ruff" in content:
                print(f"\n📄 {file_path}:")

                # Parse the file
                try:
                    config = toml.loads(content)
                    ruff_config = config.get("tool", {}).get("ruff", {})

                    if ruff_config:
                        ruff_configs[str(file_path)] = ruff_config

                        # Display key settings
                        for key, value in ruff_config.items():
                            if isinstance(value, dict):
                                print(f"  [{key}]")
                                for subkey, subvalue in value.items():
                                    print(f"    {subkey} = {subvalue}")
                            else:
                                print(f"  {key} = {value}")
                    else:
                        print("  (No ruff configuration found)")

                except Exception as e:
                    print(f"  ❌ Error parsing TOML: {e}")
                    print("  Raw content preview:")
                    lines = content.split("\n")
                    in_ruff = False
                    for line in lines:
                        if line.strip().startswith("[tool.ruff"):
                            in_ruff = True
                            print(f"    {line}")
                        elif in_ruff and line.strip().startswith("[") and not line.strip().startswith("[tool.ruff"):
                            break
                        elif in_ruff:
                            print(f"    {line}")
            else:
                print(f"\n📄 {file_path}: No ruff configuration")

        except Exception as e:
            print(f"❌ Error reading {file_path}: {e}")

    # Check for conflicts
    print("\n🔍 CONFLICT ANALYSIS:")
    if len(ruff_configs) > 1:
        print("Multiple ruff configurations found - checking for conflicts...")

        # Compare configurations
        base_config = None
        conflicts = []

        for file_path, config in ruff_configs.items():
            if base_config is None:
                base_config = config
                print(f"Using {file_path} as baseline")
            else:
                # Compare with baseline
                for key, value in config.items():
                    if key in base_config and base_config[key] != value:
                        conflicts.append(
                            {
                                "setting": key,
                                "baseline": base_config[key],
                                "conflict_file": file_path,
                                "conflict_value": value,
                            },
                        )
                        print(f"  ⚠️  CONFLICT: {key}")
                        print(f"    Baseline: {base_config[key]}")
                        print(f"    {file_path}: {value}")

        if conflicts:
            print(f"\n🚨 Found {len(conflicts)} configuration conflicts!")
        else:
            print("✅ No configuration conflicts found")
    else:
        print("✅ Only one ruff configuration found (no conflicts possible)")


def analyze_vscode_settings():
    """Analyze VS Code settings for conflicts"""
    print("\n💻 VS CODE SETTINGS ANALYSIS")
    print("=" * 50)

    vscode_settings = Path(".vscode/settings.json")
    if not vscode_settings.exists():
        print("❌ No VS Code settings found")
        return

    try:
        with open(vscode_settings) as f:
            settings = json.load(f)

        print("VS Code settings that might affect formatting:")

        formatting_settings = {}
        for key, value in settings.items():
            if any(keyword in key.lower() for keyword in ["format", "ruff", "python", "black", "isort"]):
                formatting_settings[key] = value
                print(f"  {key}: {value}")

        # Check for potential conflicts
        print("\n🔍 POTENTIAL CONFLICTS:")

        # Check line length settings
        vscode_line_length = None
        for key, value in settings.items():
            if "line-length" in key.lower() or "linelength" in key.lower():
                vscode_line_length = value
                break

        if vscode_line_length:
            print(f"  VS Code line length: {vscode_line_length}")

            # Check against pyproject.toml
            root_pyproject = Path("pyproject.toml")
            if root_pyproject.exists():
                try:
                    with open(root_pyproject) as f:
                        content = f.read()

                    # Look for line-length in ruff config
                    lines = content.split("\n")
                    in_ruff = False
                    for line in lines:
                        if line.strip().startswith("[tool.ruff"):
                            in_ruff = True
                        elif in_ruff and line.strip().startswith("[") and not line.strip().startswith("[tool.ruff"):
                            break
                        elif in_ruff and "line-length" in line:
                            pyproject_line_length = line.split("=")[1].strip()
                            print(f"  PyProject.toml line length: {pyproject_line_length}")

                            if str(vscode_line_length) != pyproject_line_length:
                                print("  ⚠️  CONFLICT: Line length mismatch!")
                                print(f"    VS Code: {vscode_line_length}")
                                print(f"    PyProject: {pyproject_line_length}")
                            else:
                                print("  ✅ Line length settings match")
                            break
                except Exception as e:
                    print(f"  ❌ Error checking pyproject.toml: {e}")

        # Check format on save
        format_on_save = settings.get("editor.formatOnSave")
        if format_on_save:
            print(f"  ⚠️  Format on save: {format_on_save}")
            print("    This might cause automatic formatting conflicts")

        # Check Python formatter
        python_formatter = settings.get("python.formatting.provider")
        if python_formatter:
            print(f"  Python formatter: {python_formatter}")

        ruff_enabled = settings.get("python.linting.ruffEnabled")
        if ruff_enabled:
            print(f"  Ruff linting enabled: {ruff_enabled}")

    except Exception as e:
        print(f"❌ Error reading VS Code settings: {e}")


def analyze_pre_commit_config():
    """Analyze pre-commit configuration"""
    print("\n🔗 PRE-COMMIT CONFIGURATION ANALYSIS")
    print("=" * 50)

    pre_commit_config = Path(".pre-commit-config.yaml")
    if not pre_commit_config.exists():
        print("❌ No pre-commit configuration found")
        return

    try:
        with open(pre_commit_config) as f:
            content = f.read()

        print("Pre-commit hooks configuration:")

        lines = content.split("\n")
        in_hooks = False
        current_repo = None

        for i, line in enumerate(lines):
            line = line.strip()

            if line.startswith("repos:"):
                in_hooks = True
                print("  Repositories:")
            elif in_hooks and line.startswith("- repo:"):
                current_repo = line.replace("- repo:", "").strip()
                print(f"    {current_repo}")
            elif in_hooks and line.startswith("hooks:"):
                print("    Hooks:")
            elif in_hooks and line.startswith("- id:"):
                hook_id = line.replace("- id:", "").strip()
                print(f"      - {hook_id}")

                # Check if it's a ruff-related hook
                if "ruff" in hook_id.lower():
                    print("        ⚠️  Ruff hook found!")

                    # Look for arguments
                    for j in range(i + 1, min(i + 5, len(lines))):
                        next_line = lines[j].strip()
                        if next_line.startswith("args:") or next_line.startswith("args ="):
                            print(f"        Arguments: {next_line}")
                        elif next_line.startswith("-") and not next_line.startswith("- repo:"):
                            print(f"        {next_line}")
                        elif next_line == "":
                            break
            elif in_hooks and line.startswith("args:"):
                args = line.replace("args:", "").strip()
                print(f"        Arguments: {args}")
            elif in_hooks and line.startswith("- ") and not line.startswith("- repo:"):
                print(f"        {line}")

        # Check for ruff-specific settings
        if "ruff" in content.lower():
            print("\n🔍 Ruff-specific settings:")
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if "ruff" in line.lower():
                    print(f"  Line {i + 1}: {line}")

    except Exception as e:
        print(f"❌ Error reading pre-commit config: {e}")


def analyze_environment_conflicts():
    """Analyze environment variables that might cause conflicts"""
    print("\n🌍 ENVIRONMENT VARIABLES ANALYSIS")
    print("=" * 50)

    relevant_vars = {}

    for var, value in os.environ.items():
        if any(keyword in var.upper() for keyword in ["RUFF", "PYTHON", "VSCODE", "FORMAT", "EDITOR"]):
            relevant_vars[var] = value

    if relevant_vars:
        print("Relevant environment variables:")
        for var, value in relevant_vars.items():
            print(f"  {var}={value}")
    else:
        print("No relevant environment variables found")

    # Check for conflicting Python versions
    python_version = os.environ.get("PYTHON_VERSION")
    python_path = os.environ.get("PYTHONPATH")

    if python_version:
        print(f"\nPython version: {python_version}")
    if python_path:
        print(f"Python path: {python_path}")


def check_file_watchers():
    """Check for file watchers that might be causing automatic formatting"""
    print("\n👁️ FILE WATCHER ANALYSIS")
    print("=" * 50)

    import subprocess

    try:
        # Check for file watcher processes
        result = subprocess.run(
            "ps aux | grep -E '(watch|monitor|inotify)' | grep -v grep",
            shell=True,
            capture_output=True,
            text=True,
        )

        if result.stdout:
            print("Active file watcher processes:")
            print(result.stdout)
        else:
            print("✅ No active file watcher processes found")

        # Check for VS Code file watchers specifically
        result = subprocess.run(
            "ps aux | grep -i 'visual studio code' | grep -E '(watch|monitor)' | grep -v grep",
            shell=True,
            capture_output=True,
            text=True,
        )

        if result.stdout:
            print("\nVS Code file watcher processes:")
            print(result.stdout)
        else:
            print("\n✅ No VS Code file watcher processes found")

    except Exception as e:
        print(f"❌ Error checking file watchers: {e}")


def generate_conflict_report():
    """Generate a comprehensive conflict report"""
    print("\n📊 GENERATING CONFLICT REPORT")
    print("=" * 50)

    report = f"""
# Configuration Conflict Analysis Report

**Generated:** {datetime.now().isoformat()}
**Purpose:** Analyze configuration conflicts causing circular ruff reversion

## Summary

This report analyzes potential configuration conflicts that might cause the circular
ruff reversion issue where syntax fixes are automatically reverted.

## Key Findings

[This would be populated with actual findings from the analysis]

## Recommendations

1. **Configuration Alignment:**
   - [To be filled based on analysis results]

2. **Process Management:**
   - [To be filled based on analysis results]

3. **Tool Integration:**
   - [To be filled based on analysis results]

## Next Steps

1. Review configuration conflicts
2. Align conflicting settings
3. Test resolution
4. Document final configuration
"""

    with open("config_conflict_report.md", "w") as f:
        f.write(report)

    print("Report generated: config_conflict_report.md")


def main():
    """Main analysis function"""
    print("🚨 CONFIGURATION CONFLICT ANALYSIS")
    print("=" * 60)
    print("Analyzing configuration conflicts that might cause circular ruff reversion")
    print()

    # Run all analyses
    analyze_pyproject_toml_files()
    analyze_vscode_settings()
    analyze_pre_commit_config()
    analyze_environment_conflicts()
    check_file_watchers()

    generate_conflict_report()

    print("\n✅ CONFLICT ANALYSIS COMPLETE")
    print("Check 'config_conflict_report.md' for the full report")


if __name__ == "__main__":
    main()
