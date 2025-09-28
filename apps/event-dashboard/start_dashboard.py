from hive_logging import get_logger

logger = get_logger(__name__)
#!/usr/bin/env python3
"""
Event Dashboard Launcher for Hive V4.0

Simple launcher script for the real-time event dashboard.
"""

import sys
from pathlib import Path

from dashboard import main

if __name__ == "__main__":
    logger.info("🚀 Starting Hive V4.0 Event Dashboard...")
    main()
