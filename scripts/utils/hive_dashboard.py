#!/usr/bin/env python3
"""Launch the Hive Dashboard."""
import sys
from pathlib import Path

# Add apps directories to path
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "hive-orchestrator" / "src"))

from hive_orchestrator.dashboard import main

if __name__ == "__main__":
    main()
