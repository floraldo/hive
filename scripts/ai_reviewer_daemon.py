#!/usr/bin/env python3
"""Launch the AI Reviewer daemon."""
import sys
import os
from pathlib import Path

# Add apps directories to path
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "ai-reviewer" / "src"))

from ai_reviewer.agent import main

if __name__ == "__main__":
    main()