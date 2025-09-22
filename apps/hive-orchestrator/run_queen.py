#!/usr/bin/env python3
"""
Run the Queen orchestrator as a module with proper Python paths.
This is the recommended way to run Queen on Windows.
"""

import sys
import os
from pathlib import Path

# Add necessary paths for module imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "apps" / "hive-orchestrator" / "src"))
sys.path.insert(0, str(project_root / "packages" / "hive-utils" / "src"))
sys.path.insert(0, str(project_root / "packages" / "hive-logging" / "src"))
sys.path.insert(0, str(project_root / "packages" / "hive-core-db" / "src"))

# Now import and run Queen
from hive_orchestrator.queen import QueenLite


def main():
    """Run the Queen orchestrator"""
    import argparse

    parser = argparse.ArgumentParser(description="QueenLite - Streamlined Queen Orchestrator")
    parser.add_argument("--live", action="store_true", help="Enable live streaming output from workers")
    args = parser.parse_args()

    print("=" * 70)
    print("Starting Hive Queen Orchestrator")
    print("=" * 70)
    print(f"Project root: {project_root}")
    print(f"Python: {sys.executable}")
    print(f"Live output: {args.live}")
    print("=" * 70)

    # Create and run Queen
    queen = QueenLite(live_output=args.live)

    try:
        queen.run()
    except KeyboardInterrupt:
        print("\n[QUEEN] Shutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        print(f"[QUEEN] Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()