from hive_logging import get_logger

logger = get_logger(__name__)
#!/usr/bin/env python3
"""
Run the Queen orchestrator as a module with proper Python paths.
This is the recommended way to run Queen on Windows.
"""

import sys

# Now import HiveCore and Queen
from hive_orchestrator.hive_core import HiveCore
from hive_orchestrator.queen import QueenLite


def main():
    """Run the Queen orchestrator"""
    import argparse

    parser = argparse.ArgumentParser(description="QueenLite - Streamlined Queen Orchestrator")
    parser.add_argument("--live", action="store_true", help="Enable live streaming output from workers")
    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("Starting Hive Queen Orchestrator")
    logger.info("=" * 70)
    logger.info(f"Project root: {project_root}")
    logger.info(f"Python: {sys.executable}")
    logger.info(f"Live output: {args.live}")
    logger.info("=" * 70)

    # Create HiveCore instance (the shared Hive Mind)
    hive_core = HiveCore()

    # Create and run Queen with HiveCore
    queen = QueenLite(hive_core, live_output=args.live)

    try:
        queen.run_forever()
    except KeyboardInterrupt:
        logger.info("\n[QUEEN] Shutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"[QUEEN] Fatal error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
