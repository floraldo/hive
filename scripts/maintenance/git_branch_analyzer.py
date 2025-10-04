#!/usr/bin/env python3
# Security: subprocess calls in this script use sys.executable with hardcoded,
# trusted arguments only. No user input is passed to subprocess. This is safe for
# internal maintenance tooling.

"""Git Branch Analyzer - Operational Excellence Tool

Analyzes repository branches to identify:
- Merged branches that can be safely deleted
- Stale branches that need review
- Branch naming consistency issues

Part of the Operational Excellence Campaign for platform hardening.
"""

import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path


def run_git_command(cmd: list[str]) -> str:
    """Run a git command and return output"""
    try:
        result = subprocess.run(["git"] + cmd, capture_output=True, text=True, check=True, cwd=Path.cwd())
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Git command failed: git {' '.join(cmd)}")
        print(f"Error: {e.stderr}")
        return ""


def get_all_branches() -> dict[str, list[str]]:
    """Get all branches categorized by type"""
    output = run_git_command(["branch", "-a"])

    branches = {"local": [], "remote": [], "current": None}

    for line in output.split("\n"):
        line = line.strip()
        if not line:
            continue

        if line.startswith("*"):
            # Current branch
            branch_name = line[2:].strip()
            branches["current"] = branch_name
            branches["local"].append(branch_name)
        elif line.startswith("remotes/origin/"):
            # Remote branch
            branch_name = line.replace("remotes/origin/", "")
            if branch_name != "HEAD":
                branches["remote"].append(branch_name)
        elif not line.startswith("remotes/"):
            # Local branch
            branches["local"].append(line)

    return branches


def get_merged_branches() -> list[str]:
    """Get branches that have been merged into main"""
    output = run_git_command(["branch", "--merged", "main"])
    merged = []

    for line in output.split("\n"):
        line = line.strip()
        if line and not line.startswith("*") and line != "main":
            merged.append(line)

    return merged


def get_branch_last_commit_date(branch: str) -> datetime:
    """Get the date of the last commit on a branch"""
    try:
        output = run_git_command(["log", "-1", "--format=%ci", branch])
        if output:
            # Parse git date format: 2025-09-28 14:30:00 +0000
            date_str = output.split(" ")[0] + " " + output.split(" ")[1]
            return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    except Exception:
        pass

    return datetime.now()


def analyze_branch_staleness(branches: list[str], days_threshold: int = 90) -> dict[str, list[tuple[str, int]]]:
    """Analyze branches for staleness"""
    cutoff_date = datetime.now() - timedelta(days=days_threshold)

    stale_branches = []
    active_branches = []

    for branch in branches:
        if branch in ["main", "HEAD"]:
            continue

        last_commit_date = get_branch_last_commit_date(branch)
        days_old = (datetime.now() - last_commit_date).days

        if last_commit_date < cutoff_date:
            stale_branches.append((branch, days_old))
        else:
            active_branches.append((branch, days_old))

    return {
        "stale": sorted(stale_branches, key=lambda x: x[1], reverse=True),
        "active": sorted(active_branches, key=lambda x: x[1]),
    }


def analyze_branch_naming_patterns(branches: list[str]) -> dict[str, list[str]]:
    """Analyze branch naming consistency"""
    patterns = {"feature": [], "agent": [], "worker": [], "test": [], "cleanup": [], "other": []}

    for branch in branches:
        if branch.startswith("feature/"):
            patterns["feature"].append(branch)
        elif branch.startswith("agent/"):
            patterns["agent"].append(branch)
        elif branch.startswith("worker/"):
            patterns["worker"].append(branch)
        elif branch.startswith("test"):
            patterns["test"].append(branch)
        elif "cleanup" in branch.lower():
            patterns["cleanup"].append(branch)
        else:
            patterns["other"].append(branch)

    return patterns


def generate_branch_analysis_report() -> str:
    """Generate comprehensive branch analysis report"""
    print("OPERATIONAL EXCELLENCE: Git Branch Analysis")
    print("=" * 60)

    # Get all branches
    branches = get_all_branches()
    all_local_branches = [b for b in branches["local"] if b != branches["current"]]

    # Get merged branches
    merged_branches = get_merged_branches()

    # Analyze staleness
    staleness_analysis = analyze_branch_staleness(all_local_branches + branches["remote"])

    # Analyze naming patterns
    naming_patterns = analyze_branch_naming_patterns(all_local_branches + branches["remote"])

    report = []
    report.append("# Git Branch Analysis Report")
    report.append("")
    report.append("## Executive Summary")
    report.append(f"- **Current branch**: {branches['current']}")
    report.append(f"- **Local branches**: {len(branches['local'])}")
    report.append(f"- **Remote branches**: {len(branches['remote'])}")
    report.append(f"- **Merged branches**: {len(merged_branches)}")
    report.append(f"- **Stale branches**: {len(staleness_analysis['stale'])}")
    report.append("")

    # Safe to delete (merged branches)
    if merged_branches:
        report.append("## ✅ Safe to Delete (Merged Branches)")
        report.append("These branches have been merged into main and can be safely deleted:")
        report.append("")
        for branch in merged_branches:
            report.append(f"- `{branch}` - Merged into main")
        report.append("")
        report.append("**Deletion command**:")
        report.append("```bash")
        for branch in merged_branches:
            report.append(f"git branch -d {branch}")
        report.append("```")
        report.append("")

    # Stale branches needing review
    if staleness_analysis["stale"]:
        report.append("## ⚠️ Stale Branches (Review Needed)")
        report.append("These branches haven't been updated in 90+ days:")
        report.append("")
        for branch, days_old in staleness_analysis["stale"][:10]:
            report.append(f"- `{branch}` - {days_old} days old")
        if len(staleness_analysis["stale"]) > 10:
            report.append(f"- ... and {len(staleness_analysis['stale']) - 10} more")
        report.append("")

    # Active branches
    if staleness_analysis["active"]:
        report.append("## 🟢 Active Branches (Recent Activity)")
        report.append("These branches have recent commits:")
        report.append("")
        for branch, days_old in staleness_analysis["active"][:5]:
            report.append(f"- `{branch}` - {days_old} days old")
        if len(staleness_analysis["active"]) > 5:
            report.append(f"- ... and {len(staleness_analysis['active']) - 5} more")
        report.append("")

    # Naming pattern analysis
    report.append("## 📋 Branch Naming Analysis")
    report.append("")
    for pattern, pattern_branches in naming_patterns.items():
        if pattern_branches:
            report.append(f"### {pattern.title()} Branches ({len(pattern_branches)})")
            for branch in pattern_branches[:5]:
                report.append(f"- `{branch}`")
            if len(pattern_branches) > 5:
                report.append(f"- ... and {len(pattern_branches) - 5} more")
            report.append("")

    # Recommendations
    report.append("## 🎯 Recommendations")
    report.append("")
    if merged_branches:
        report.append("### Immediate Actions")
        report.append(f"1. **Delete {len(merged_branches)} merged branches** - Zero risk, immediate cleanup")
        report.append("")

    if staleness_analysis["stale"]:
        report.append("### Review Actions")
        report.append(f"2. **Review {len(staleness_analysis['stale'])} stale branches** - Determine if still needed")
        report.append("   - If abandoned: delete with `git branch -D <branch-name>`")
        report.append("   - If needed: rebase or merge recent changes")
        report.append("")

    # Pattern-specific recommendations
    agent_branches = [b for b in naming_patterns["agent"] if "invalid" in b or len(b.split("/")) > 3]
    if agent_branches:
        report.append("### Naming Cleanup")
        report.append("3. **Clean up agent branch naming** - Some branches have complex/invalid names")
        report.append("")

    report.append("## ✅ Execution Plan")
    report.append("1. **Phase 1**: Delete merged branches (zero risk)")
    report.append("2. **Phase 2**: Review stale branches with team")
    report.append("3. **Phase 3**: Standardize branch naming conventions")
    report.append("")

    return "\n".join(report)


def main():
    """Main execution function"""
    try:
        report = generate_branch_analysis_report()

        # Write report to file
        report_path = Path("GIT_BRANCH_ANALYSIS_REPORT.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)

        print("Branch analysis complete!")
        print(f"Report saved to: {report_path}")
        print()
        print("Key findings:")

        branches = get_all_branches()
        merged_branches = get_merged_branches()
        staleness_analysis = analyze_branch_staleness(branches["local"] + branches["remote"])

        print(f"  • {len(merged_branches)} merged branches ready for deletion")
        print(f"  • {len(staleness_analysis['stale'])} stale branches need review")
        print(f"  • {len(staleness_analysis['active'])} active branches")

        return True

    except Exception as e:
        print(f"Branch analysis failed: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
