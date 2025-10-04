#!/usr/bin/env python3
"""Bypass Review Tool for QA Agent

Purpose: Analyze bypass log and generate prioritized cleanup tasks
Reads: .git/bypass-log.txt
Outputs: Prioritized list of technical debt requiring attention

Usage:
    python scripts/qa/review-bypasses.py
    python scripts/qa/review-bypasses.py --show-recent 10
    python scripts/qa/review-bypasses.py --export-tasks cleanup-tasks.md
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import NamedTuple


class BypassEntry(NamedTuple):
    """Represents a single bypass event."""

    timestamp: datetime
    author: str
    justification: str
    raw_line: str


def parse_bypass_log(log_path: Path) -> list[BypassEntry]:
    """Parse the bypass log file into structured entries."""
    if not log_path.exists():
        return []

    entries = []
    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            # Format: "2025-10-04T15:30:00Z | John Doe | WIP: Incomplete feature"
            try:
                parts = line.split(" | ", maxsplit=2)
                if len(parts) != 3:
                    continue

                timestamp_str, author, justification = parts
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

                entries.append(
                    BypassEntry(
                        timestamp=timestamp,
                        author=author,
                        justification=justification,
                        raw_line=line,
                    )
                )
            except (ValueError, IndexError):
                # Skip malformed lines
                continue

    return sorted(entries, key=lambda e: e.timestamp, reverse=True)


def categorize_bypasses(entries: list[BypassEntry]) -> dict[str, list[BypassEntry]]:
    """Categorize bypasses by priority/type."""
    categories = {
        "emergency": [],  # Production issues, hotfixes
        "blocked": [],  # False positives, tool issues
        "wip": [],  # Work in progress
        "other": [],  # Everything else
    }

    for entry in entries:
        just_lower = entry.justification.lower()

        if any(
            keyword in just_lower
            for keyword in ["emergency", "hotfix", "production", "critical"]
        ):
            categories["emergency"].append(entry)
        elif any(
            keyword in just_lower
            for keyword in ["blocked", "false positive", "tool issue", "bug in"]
        ):
            categories["blocked"].append(entry)
        elif any(keyword in just_lower for keyword in ["wip", "incomplete", "draft"]):
            categories["wip"].append(entry)
        else:
            categories["other"].append(entry)

    return categories


def generate_cleanup_tasks(categories: dict[str, list[BypassEntry]]) -> str:
    """Generate markdown-formatted cleanup task list."""
    output = []
    output.append("# QA Agent - Bypass Cleanup Tasks\n")
    output.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    output.append("---\n")

    # Summary statistics
    total = sum(len(entries) for entries in categories.values())
    output.append(f"**Total Bypasses**: {total}\n")
    output.append(f"- Emergency/Hotfix: {len(categories['emergency'])}\n")
    output.append(f"- Blocked by Tools: {len(categories['blocked'])}\n")
    output.append(f"- Work in Progress: {len(categories['wip'])}\n")
    output.append(f"- Other: {len(categories['other'])}\n")
    output.append("\n---\n")

    # Priority 1: Emergency/Hotfix
    if categories["emergency"]:
        output.append("## Priority 1: Emergency Bypasses (Validate ASAP)\n")
        output.append(
            "These commits bypassed validation due to production issues. Validate they didn't introduce regressions.\n"
        )
        for entry in categories["emergency"]:
            output.append(f"- [ ] **{entry.timestamp.strftime('%Y-%m-%d %H:%M')}** ")
            output.append(f"by {entry.author}: {entry.justification}\n")
        output.append("\n")

    # Priority 2: Blocked by Tools
    if categories["blocked"]:
        output.append("## Priority 2: Tool Issues (Investigate)\n")
        output.append(
            "These bypasses indicate potential false positives or tool configuration issues.\n"
        )
        for entry in categories["blocked"]:
            output.append(f"- [ ] **{entry.timestamp.strftime('%Y-%m-%d %H:%M')}** ")
            output.append(f"by {entry.author}: {entry.justification}\n")
        output.append("\n")

    # Priority 3: Work in Progress
    if categories["wip"]:
        output.append("## Priority 3: Work in Progress (Consolidate)\n")
        output.append(
            "These commits were incomplete at time of commit. Ensure they are now complete.\n"
        )
        for entry in categories["wip"]:
            output.append(f"- [ ] **{entry.timestamp.strftime('%Y-%m-%d %H:%M')}** ")
            output.append(f"by {entry.author}: {entry.justification}\n")
        output.append("\n")

    # Priority 4: Other
    if categories["other"]:
        output.append("## Priority 4: Other Bypasses (Review)\n")
        for entry in categories["other"]:
            output.append(f"- [ ] **{entry.timestamp.strftime('%Y-%m-%d %H:%M')}** ")
            output.append(f"by {entry.author}: {entry.justification}\n")
        output.append("\n")

    return "".join(output)


def main():
    parser = argparse.ArgumentParser(description="Review bypass log for QA cleanup")
    parser.add_argument(
        "--show-recent", type=int, metavar="N", help="Show N most recent bypasses"
    )
    parser.add_argument(
        "--export-tasks", metavar="FILE", help="Export cleanup tasks to markdown file"
    )
    args = parser.parse_args()

    # Find bypass log
    repo_root = Path(__file__).parent.parent.parent
    log_path = repo_root / ".git" / "bypass-log.txt"

    # Parse entries
    entries = parse_bypass_log(log_path)

    if not entries:
        print("No bypass entries found.")
        print(f"Log path: {log_path}")
        return 0

    # Show recent if requested
    if args.show_recent:
        print(f"\n=== {args.show_recent} Most Recent Bypasses ===\n")
        for entry in entries[: args.show_recent]:
            print(f"{entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')} | {entry.author}")
            print(f"  {entry.justification}\n")
        return 0

    # Categorize and generate tasks
    categories = categorize_bypasses(entries)
    tasks_md = generate_cleanup_tasks(categories)

    # Export or print
    if args.export_tasks:
        output_path = Path(args.export_tasks)
        output_path.write_text(tasks_md)
        print(f"Cleanup tasks exported to: {output_path}")
    else:
        print(tasks_md)

    return 0


if __name__ == "__main__":
    sys.exit(main())
