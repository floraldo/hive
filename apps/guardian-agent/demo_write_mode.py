"""
Guardian Write Mode Demonstration.

Demonstrates progressive deployment of Guardian's write capabilities,
starting with safe typo fixes and progressing to more complex changes.

Usage:
    # Dry run (safe - no actual changes)
    python apps/guardian-agent/demo_write_mode.py --dry-run

    # Enable Level 1 (typos only)
    python apps/guardian-agent/demo_write_mode.py --level 1

    # Show proposals
    python apps/guardian-agent/demo_write_mode.py --show-proposals
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add to path for demo
sys.path.insert(0, str(Path(__file__).parent / "src"))

from guardian_agent.review.write_capable_engine import WriteCapableEngine
from guardian_agent.review.write_mode import (
    ChangeLevel,
    WriteModeConfig,
)


async def demo_dry_run():
    """Demonstrate dry-run mode (safest)."""
    print("=" * 70)
    print("Guardian Write Mode - Dry Run Demonstration")
    print("=" * 70)

    config = WriteModeConfig(
        enabled_levels=[ChangeLevel.LEVEL_1_TYPO],
        dry_run=True,
    )

    engine = WriteCapableEngine(
        rag_index_dir="data/rag_index",
        write_config=config,
    )

    print("\nConfiguration:")
    print(f"  Dry run: {config.dry_run}")
    print(f"  Enabled levels: {[l.name for l in config.enabled_levels]}")
    print(f"  Require approval: {config.require_approval}")

    # Simulate PR analysis
    pr_files = [
        {
            "filename": "example.py",
            "patch": "+    print('Helo world')  # Typo in comment",
        }
    ]

    print("\nAnalyzing PR with write mode enabled...")
    result = await engine.analyze_pr_with_proposals(
        pr_number=1,
        pr_files=pr_files,
        pr_title="Example PR",
        pr_description="Demo PR for write mode",
    )

    print("\nResults:")
    print(f"  Comments: {result['metrics']['total_comments']}")
    print(f"  Proposals created: {result['metrics']['proposals_created']}")
    print(f"  By level: {result['metrics']['proposals_by_level']}")

    if result["proposals"]:
        print("\nSample proposal:")
        proposal = result["proposals"][0]
        print(f"  ID: {proposal['proposal_id']}")
        print(f"  Category: {proposal['category']}")
        print(f"  Level: {proposal['level']}")
        print(f"  Risk: {proposal['risk_level']}")
        print(f"  Description: {proposal['description']}")
        print(f"  Old: {proposal['old_code'][:50]}...")
        print(f"  New: {proposal['new_code'][:50]}...")

    print("\n✓ Dry run complete - no changes applied")


async def demo_level_1():
    """Demonstrate Level 1 (typo fixes) with approval."""
    print("=" * 70)
    print("Guardian Write Mode - Level 1 (Typos)")
    print("=" * 70)

    config = WriteModeConfig(
        enabled_levels=[ChangeLevel.LEVEL_1_TYPO],
        require_approval=True,
        auto_commit=False,
        dry_run=False,
    )

    engine = WriteCapableEngine(
        rag_index_dir="data/rag_index",
        write_config=config,
    )

    print("\nConfiguration:")
    print(f"  Dry run: {config.dry_run}")
    print(f"  Enabled levels: {[l.name for l in config.enabled_levels]}")
    print(f"  Require approval: {config.require_approval}")
    print(f"  Auto commit: {config.auto_commit}")

    print("\nWorkflow:")
    print("  1. Analyze PR → Generate proposals")
    print("  2. Human reviews proposals")
    print("  3. Approve safe changes")
    print("  4. Apply approved changes")
    print("  5. Create git commit for rollback")

    print("\n✓ Level 1 demonstration complete")


async def demo_progressive_deployment():
    """Demonstrate progressive level deployment."""
    print("=" * 70)
    print("Guardian Write Mode - Progressive Deployment")
    print("=" * 70)

    levels = [
        (ChangeLevel.LEVEL_1_TYPO, "Typos in comments/docstrings", "minimal"),
        (ChangeLevel.LEVEL_2_DOCSTRING, "Missing docstrings", "low"),
        (ChangeLevel.LEVEL_3_FORMATTING, "Code formatting", "moderate"),
        (ChangeLevel.LEVEL_4_LOGIC, "Logic fixes", "elevated"),
        (ChangeLevel.LEVEL_5_FEATURE, "Feature enhancements", "high"),
    ]

    print("\nProgressive deployment path:")
    for level, description, risk in levels:
        print(f"\n  {level.name}:")
        print(f"    Description: {description}")
        print(f"    Risk level: {risk}")
        print(f"    Requires tests: {level.requires_tests}")
        print(f"    Requires review: {level.requires_review}")

    print("\nDeployment strategy:")
    print("  1. Start: Level 1 only, dry-run mode")
    print("  2. Validate: Run for 1 week, collect metrics")
    print("  3. Enable: Level 1, require approval, real changes")
    print("  4. Monitor: Success rate >95% for 1 month")
    print("  5. Expand: Add Level 2, repeat validation")
    print("  6. Iterate: Progressive expansion based on metrics")


async def show_proposals():
    """Show existing proposals."""
    print("=" * 70)
    print("Guardian Write Mode - Proposals")
    print("=" * 70)

    proposals_dir = Path("data/guardian_proposals")
    if not proposals_dir.exists():
        print("\nNo proposals found.")
        return

    proposal_files = list(proposals_dir.glob("*.json"))
    print(f"\nFound {len(proposal_files)} proposals:")

    for i, pfile in enumerate(proposal_files[:10], 1):  # Show first 10
        import json

        data = json.loads(pfile.read_text())
        print(f"\n  {i}. {data['proposal_id']}")
        print(f"     File: {data['file_path']}")
        print(f"     Category: {data['category']}")
        print(f"     Status: {data['review_status']}")
        print(f"     Risk: {data['risk_level']}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Guardian Write Mode Demo")
    parser.add_argument("--dry-run", action="store_true", help="Run dry-run demo")
    parser.add_argument("--level", type=int, choices=[1, 2, 3, 4, 5], help="Demo specific level")
    parser.add_argument("--show-proposals", action="store_true", help="Show existing proposals")
    parser.add_argument("--progressive", action="store_true", help="Show progressive deployment")

    args = parser.parse_args()

    if args.show_proposals:
        asyncio.run(show_proposals())
    elif args.progressive:
        asyncio.run(demo_progressive_deployment())
    elif args.level == 1:
        asyncio.run(demo_level_1())
    else:
        # Default to dry-run
        asyncio.run(demo_dry_run())


if __name__ == "__main__":
    main()
