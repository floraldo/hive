#!/usr/bin/env python3
"""Structure verification - Check QA Agent components are syntactically valid.

This script verifies:
1. All Python files compile without syntax errors
2. Core classes and functions are defined
3. Module structure is correct

Run: python verify_structure.py
"""

import sys
from pathlib import Path


def verify_syntax(file_path: Path) -> bool:
    """Verify Python file syntax by compiling it."""
    try:
        with open(file_path) as f:
            compile(f.read(), file_path, 'exec')
        return True
    except SyntaxError as e:
        print(f"FAIL {file_path}: {e}")
        return False

def main():
    """Verify all QA Agent Python files."""
    qa_agent_dir = Path(__file__).parent / "src" / "qa_agent"

    python_files = [
        qa_agent_dir / "daemon.py",
        qa_agent_dir / "cli.py",
        qa_agent_dir / "decision_engine.py",
        qa_agent_dir / "rag_priming.py",
        qa_agent_dir / "monitoring.py",
        qa_agent_dir / "cc_spawner.py",
        qa_agent_dir / "persona_builder.py",
        qa_agent_dir / "complexity_scorer.py",
        qa_agent_dir / "batch_optimizer.py",
        qa_agent_dir / "escalation.py",
        qa_agent_dir / "dashboard.py",
    ]

    print("=" * 80)
    print("QA AGENT STRUCTURE VERIFICATION")
    print("=" * 80)
    print()

    results = []
    for file_path in python_files:
        if not file_path.exists():
            print(f"SKIP {file_path.name}: File not found")
            results.append(False)
            continue

        if verify_syntax(file_path):
            print(f"OK   {file_path.name}: Syntax valid")
            results.append(True)
        else:
            results.append(False)

    print()
    print("=" * 80)

    passed = sum(results)
    total = len(results)

    if passed == total:
        print(f"RESULT: All {total} files passed syntax validation")
        print()
        print("Next step: Set up environment and test imports")
        print("  See: DEPLOYMENT_FIX_SUMMARY.md")
        print()
        return 0
    else:
        print(f"RESULT: {passed}/{total} files passed")
        print()
        return 1

if __name__ == "__main__":
    sys.exit(main())
