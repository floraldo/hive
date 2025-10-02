#!/usr/bin/env python3
"""
Complete Hive Oracle Intelligence Demo

This script provides a comprehensive demonstration of the complete
"Hive Intelligence Initiative" implementation, showcasing how the
Guardian Agent has evolved into the Oracle.

Run this to see the full Oracle capabilities in action.
"""

import asyncio
import sys
from pathlib import Path

# Add the guardian-agent src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from demo_oracle import demo_oracle_intelligence_async

if __name__ == "__main__":
    print("🔮 Hive Oracle Intelligence System - Complete Demo")
    print("=" * 60)
    print()
    print("This demo showcases the evolution of Guardian Agent → Oracle")
    print("providing strategic intelligence for the entire Hive platform.")
    print()

    try:
        asyncio.run(demo_oracle_intelligence_async())
    except KeyboardInterrupt:
        print("\n\n🛑 Demo interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Demo failed: {e}")
        import traceback

        traceback.print_exc()

    print("\n" + "=" * 60)
    print("🌟 Demo complete! The Oracle is ready to provide strategic intelligence.")
    print("Run 'python -m guardian_agent.cli.main oracle --help' to see all commands.")
