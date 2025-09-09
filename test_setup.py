#!/usr/bin/env python3
"""Test script to verify Hive setup"""

import sys
import subprocess
from pathlib import Path

def check_requirement(name, check_cmd):
    """Check if a requirement is met"""
    try:
        result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {name}")
            return True
        else:
            print(f"❌ {name}")
            return False
    except Exception as e:
        print(f"❌ {name}: {e}")
        return False

def main():
    print("🐝 Hive Setup Verification")
    print("=" * 40)
    
    checks = [
        ("Git installed", "git --version"),
        ("GitHub CLI installed", "gh --version"),
        ("Python 3.10+", "python --version"),
        ("tmux installed", "tmux -V"),
        ("GitHub authenticated", "gh auth status"),
    ]
    
    all_good = True
    for name, cmd in checks:
        if not check_requirement(name, cmd):
            all_good = False
    
    print("\n📁 Directory Structure:")
    required_dirs = [
        "orchestrator",
        "plugins/gitops",
        "workspaces/backend",
        "workspaces/frontend",
        "workspaces/infra",
        ".github/workflows",
        "logs",
    ]
    
    for dir_path in required_dirs:
        if Path(dir_path).exists():
            print(f"  ✅ {dir_path}/")
        else:
            print(f"  ❌ {dir_path}/ (missing)")
            all_good = False
    
    print("\n📄 Key Files:")
    required_files = [
        "setup.sh",
        "run.py",
        "requirements.txt",
        ".github/workflows/ci.yml",
        "orchestrator/tmux_controller.py",
        "plugins/gitops/workflow.py",
    ]
    
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"  ✅ {file_path}")
        else:
            print(f"  ❌ {file_path} (missing)")
            all_good = False
    
    print("\n🌳 Git Worktrees:")
    worktree_result = subprocess.run("git worktree list", shell=True, capture_output=True, text=True)
    for line in worktree_result.stdout.strip().split("\n"):
        if "workspaces" in line:
            print(f"  ✅ {line}")
    
    print("\n" + "=" * 40)
    if all_good:
        print("✅ All checks passed! Hive is ready.")
        print("\nNext steps:")
        print("1. Terminal 1: ./setup.sh")
        print("2. Terminal 2: python run.py --dry-run")
    else:
        print("⚠️ Some checks failed. Please fix the issues above.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())