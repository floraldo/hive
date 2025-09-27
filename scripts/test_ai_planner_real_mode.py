#!/usr/bin/env python3
"""
Test AI Planner in real Claude API mode
"""

import sys
from pathlib import Path

# Add necessary paths
hive_root = Path(__file__).parent.parent
sys.path.insert(0, str(hive_root / "packages" / "hive-config" / "src"))
sys.path.insert(0, str(hive_root / "apps" / "ai-planner" / "src"))

from hive_config import setup_hive_paths
setup_hive_paths()

from ai_planner.claude_bridge import RobustClaudePlannerBridge

def test_real_mode():
    """Test AI Planner in real Claude mode"""
    print("Testing AI Planner in Real Claude API Mode")
    print("=" * 60)

    # Initialize in REAL mode (not mock)
    bridge = RobustClaudePlannerBridge(mock_mode=False)

    if bridge.claude_cmd:
        print(f"SUCCESS: Claude CLI detected at: {bridge.claude_cmd}")
        print("AI Planner is now configured for REAL Claude API mode")
        print("")
        print("To run the AI Planner daemon in real mode:")
        print("  python scripts/ai_planner_daemon.py")
        print("")
        print("To run in mock mode for testing:")
        print("  python scripts/ai_planner_daemon.py --mock")
        return True
    else:
        print("WARNING: Claude CLI not found")
        print("AI Planner will use fallback mode")
        print("")
        print("To enable real Claude API mode:")
        print("  1. Install Claude CLI: npm install -g @anthropic-ai/claude-cli")
        print("  2. Authenticate: claude auth login")
        print("  3. Run this test again")
        return False

if __name__ == "__main__":
    success = test_real_mode()
    sys.exit(0 if success else 1)