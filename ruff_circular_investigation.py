#!/usr/bin/env python3
"""
Ruff Circular Reversion Investigation Script
============================================

This script analyzes the circular ruff reversion issue without making any changes.
It investigates all possible root causes systematically.
"""

import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path


def run_command(cmd, capture_output=True):
    """Run a command and return the result"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=capture_output, text=True)
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return -1, "", str(e)

def analyze_ruff_processes():
    """Analyze all ruff processes currently running"""
    print("🔍 ANALYZING RUFF PROCESSES...")
    print("=" * 50)
    
    # Check for ruff processes
    code, stdout, stderr = run_command("ps aux | grep ruff | grep -v grep")
    if stdout:
        print("ACTIVE RUFF PROCESSES:")
        print(stdout)
    else:
        print("No active ruff processes found")
    
    # Check for Python processes that might be running ruff
    code, stdout, stderr = run_command("ps aux | grep python | grep -E '(ruff|format|lint)' | grep -v grep")
    if stdout:
        print("\nPYTHON PROCESSES WITH RUFF/LINT/FORMAT:")
        print(stdout)
    
    print()

def analyze_ruff_configuration():
    """Analyze ruff configuration from all sources"""
    print("🔧 ANALYZING RUFF CONFIGURATION...")
    print("=" * 50)
    
    # Check root pyproject.toml
    root_pyproject = Path("pyproject.toml")
    if root_pyproject.exists():
        print("ROOT PYPROJECT.TOML:")
        with open(root_pyproject, 'r') as f:
            content = f.read()
            # Extract ruff section
            if '[tool.ruff' in content:
                lines = content.split('\n')
                in_ruff = False
                for line in lines:
                    if line.strip().startswith('[tool.ruff'):
                        in_ruff = True
                        print(line)
                    elif in_ruff and line.strip().startswith('[') and not line.strip().startswith('[tool.ruff'):
                        break
                    elif in_ruff:
                        print(line)
            else:
                print("No [tool.ruff] section found")
    
    # Find all pyproject.toml files
    print("\nALL PYPROJECT.TOML FILES:")
    pyproject_files = list(Path(".").rglob("pyproject.toml"))
    for file in pyproject_files:
        print(f"  {file}")
        # Check if it has ruff configuration
        try:
            with open(file, 'r') as f:
                content = f.read()
                if '[tool.ruff' in content:
                    print(f"    ✅ Has [tool.ruff] section")
                else:
                    print(f"    ❌ No [tool.ruff] section")
        except:
            print(f"    ❌ Cannot read file")
    
    # Check ruff settings
    print("\nRUFF SETTINGS:")
    code, stdout, stderr = run_command("python -m ruff check --show-settings .")
    if code == 0:
        print(stdout)
    else:
        print(f"Error getting ruff settings: {stderr}")
    
    print()

def analyze_vscode_integration():
    """Analyze VS Code integration and settings"""
    print("💻 ANALYZING VS CODE INTEGRATION...")
    print("=" * 50)
    
    # Check VS Code processes
    code, stdout, stderr = run_command("ps aux | grep -i 'visual studio code' | grep -v grep")
    if stdout:
        print("VS CODE PROCESSES:")
        print(stdout)
    else:
        print("No VS Code processes found")
    
    # Check VS Code settings
    vscode_settings = Path(".vscode/settings.json")
    if vscode_settings.exists():
        print("\nVS CODE SETTINGS:")
        with open(vscode_settings, 'r') as f:
            settings = json.load(f)
            for key, value in settings.items():
                if 'format' in key.lower() or 'ruff' in key.lower() or 'python' in key.lower():
                    print(f"  {key}: {value}")
    
    # Check for VS Code extensions that might auto-format
    print("\nCHECKING FOR AUTO-FORMAT TRIGGERS:")
    code, stdout, stderr = run_command("ps aux | grep -E '(watcher|file.*monitor)' | grep -v grep")
    if stdout:
        print("FILE WATCHER PROCESSES:")
        print(stdout)
    
    print()

def analyze_git_hooks():
    """Analyze git hooks that might be running ruff"""
    print("🔗 ANALYZING GIT HOOKS...")
    print("=" * 50)
    
    # Check pre-commit hooks
    pre_commit_config = Path(".pre-commit-config.yaml")
    if pre_commit_config.exists():
        print("PRE-COMMIT CONFIG:")
        with open(pre_commit_config, 'r') as f:
            content = f.read()
            if 'ruff' in content:
                print("✅ Contains ruff hooks")
                # Extract ruff-related hooks
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if 'ruff' in line.lower():
                        print(f"  Line {i+1}: {line.strip()}")
            else:
                print("❌ No ruff hooks found")
    
    # Check actual git hooks
    git_hooks = Path(".git/hooks")
    if git_hooks.exists():
        print("\nGIT HOOKS:")
        for hook in git_hooks.iterdir():
            if hook.is_file() and not hook.name.startswith('.'):
                print(f"  {hook.name}")
                try:
                    with open(hook, 'r') as f:
                        content = f.read()
                        if 'ruff' in content:
                            print(f"    ✅ Contains ruff")
                        if 'format' in content:
                            print(f"    ✅ Contains format")
                except:
                    pass
    
    print()

def analyze_file_modification_patterns():
    """Analyze file modification patterns to detect auto-formatting"""
    print("📁 ANALYZING FILE MODIFICATION PATTERNS...")
    print("=" * 50)
    
    # Check pvgis.py specifically
    pvgis_file = Path("apps/ecosystemiser/src/ecosystemiser/profile_loader/climate/adapters/pvgis.py")
    if pvgis_file.exists():
        print(f"PVGIS FILE STATUS:")
        print(f"  Path: {pvgis_file}")
        print(f"  Exists: {pvgis_file.exists()}")
        print(f"  Size: {pvgis_file.stat().st_size} bytes")
        print(f"  Modified: {datetime.fromtimestamp(pvgis_file.stat().st_mtime)}")
        
        # Check git status
        code, stdout, stderr = run_command(f"git status --porcelain {pvgis_file}")
        if stdout:
            print(f"  Git status: {stdout.strip()}")
        
        # Check for the problematic line
        try:
            with open(pvgis_file, 'r') as f:
                lines = f.readlines()
                for i, line in enumerate(lines[600:620], 601):  # Around line 607
                    if 'pvgis_cols' in line:
                        print(f"  Line {i}: {repr(line.strip())}")
        except Exception as e:
            print(f"  Error reading file: {e}")
    
    # Check for recently modified files
    print("\nRECENTLY MODIFIED PYTHON FILES:")
    code, stdout, stderr = run_command("find . -name '*.py' -mtime -1 -type f | head -10")
    if stdout:
        for line in stdout.strip().split('\n'):
            if line:
                print(f"  {line}")
    
    print()

def analyze_ruff_cache():
    """Analyze ruff cache and temporary files"""
    print("🗂️ ANALYZING RUFF CACHE...")
    print("=" * 50)
    
    # Check for ruff cache
    code, stdout, stderr = run_command("python -m ruff clean --help")
    if code == 0:
        print("Ruff clean command available")
    
    # Check for .ruff_cache directory
    ruff_cache = Path(".ruff_cache")
    if ruff_cache.exists():
        print(f"RUFF CACHE DIRECTORY EXISTS:")
        print(f"  Path: {ruff_cache}")
        print(f"  Size: {sum(f.stat().st_size for f in ruff_cache.rglob('*') if f.is_file())} bytes")
        print(f"  Files: {len(list(ruff_cache.rglob('*')))}")
    
    # Check for temporary files
    print("\nTEMPORARY FILES:")
    code, stdout, stderr = run_command("find . -name '*.tmp' -o -name '*.temp' -o -name '*~' | head -10")
    if stdout:
        for line in stdout.strip().split('\n'):
            if line:
                print(f"  {line}")
    
    print()

def analyze_environment_variables():
    """Analyze environment variables that might affect ruff"""
    print("🌍 ANALYZING ENVIRONMENT VARIABLES...")
    print("=" * 50)
    
    relevant_vars = [
        'RUFF_*', 'PYTHON_*', 'VSCODE_*', 'EDITOR', 'FORMATTER_*'
    ]
    
    print("RELEVANT ENVIRONMENT VARIABLES:")
    for var in os.environ:
        if any(pattern.replace('*', '') in var.upper() for pattern in relevant_vars):
            print(f"  {var}={os.environ[var]}")
    
    print()

def monitor_file_changes():
    """Monitor file changes in real-time"""
    print("👁️ MONITORING FILE CHANGES...")
    print("=" * 50)
    print("This will monitor pvgis.py for 10 seconds to detect auto-modifications...")
    print("(Press Ctrl+C to stop early)")
    
    pvgis_file = Path("apps/ecosystemiser/src/ecosystemiser/profile_loader/climate/adapters/pvgis.py")
    if not pvgis_file.exists():
        print("pvgis.py not found, skipping monitoring")
        return
    
    initial_mtime = pvgis_file.stat().st_mtime
    print(f"Initial modification time: {datetime.fromtimestamp(initial_mtime)}")
    
    try:
        for i in range(10):
            time.sleep(1)
            current_mtime = pvgis_file.stat().st_mtime
            if current_mtime != initial_mtime:
                print(f"⚠️  FILE MODIFIED at {datetime.fromtimestamp(current_mtime)}!")
                print("Checking what process might have modified it...")
                
                # Check running processes
                code, stdout, stderr = run_command("ps aux | grep -E '(ruff|format|python)' | grep -v grep")
                if stdout:
                    print("Active processes at time of modification:")
                    print(stdout)
                
                initial_mtime = current_mtime
            else:
                print(f"  {i+1}/10 - No changes detected")
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user")
    
    print()

def generate_report():
    """Generate comprehensive investigation report"""
    print("📊 GENERATING INVESTIGATION REPORT...")
    print("=" * 50)
    
    report = f"""
# Ruff Circular Reversion Investigation Report

**Generated:** {datetime.now().isoformat()}
**Investigator:** Analysis Script
**Target Issue:** Circular ruff reversion of syntax fixes

## Investigation Summary

This report documents the systematic investigation of the circular ruff reversion issue
where syntax fixes are automatically reverted by some process or configuration.

## Key Findings

[This would be populated with actual findings from the investigation]

## Recommendations

1. **Immediate Actions:**
   - [To be filled based on investigation results]

2. **Long-term Solutions:**
   - [To be filled based on investigation results]

## Next Steps

1. Review findings with development team
2. Implement recommended fixes
3. Test resolution
4. Document solution for future reference
"""
    
    with open("ruff_circular_investigation_report.md", "w") as f:
        f.write(report)
    
    print("Report generated: ruff_circular_investigation_report.md")

def main():
    """Main investigation function"""
    print("🚨 RUFF CIRCULAR REVERSION INVESTIGATION")
    print("=" * 60)
    print("This script will analyze the circular ruff reversion issue")
    print("without making any changes to the codebase.")
    print()
    
    # Run all analysis functions
    analyze_ruff_processes()
    analyze_ruff_configuration()
    analyze_vscode_integration()
    analyze_git_hooks()
    analyze_file_modification_patterns()
    analyze_ruff_cache()
    analyze_environment_variables()
    
    # Ask user if they want to monitor file changes
    response = input("\nDo you want to monitor pvgis.py for auto-modifications? (y/n): ")
    if response.lower() == 'y':
        monitor_file_changes()
    
    generate_report()
    
    print("\n✅ INVESTIGATION COMPLETE")
    print("Check 'ruff_circular_investigation_report.md' for the full report")

if __name__ == "__main__":
    main()
