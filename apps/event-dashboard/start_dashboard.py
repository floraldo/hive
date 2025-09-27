#!/usr/bin/env python3
"""
Event Dashboard Launcher for Hive V4.0

Simple launcher script for the real-time event dashboard.
"""

import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from dashboard import main

if __name__ == "__main__":
    print("🚀 Starting Hive V4.0 Event Dashboard...")
    main()