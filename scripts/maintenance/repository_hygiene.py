#!/usr/bin/env python3
"""
Repository Hygiene - Consolidated Cleanup Tool

This script consolidates the functionality of multiple cleanup scripts:
- automated_hygiene.py
- comprehensive_cleanup.py
- hive_clean.py

Features:
- File organization and cleanup
- Backup file removal
- Documentation consolidation
- Branch staleness analysis
- TODO comment tracking

Usage:
    python repository_hygiene.py --help
    python repository_hygiene.py --all
    python repository_hygiene.py --scan
"""

import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


class RepositoryHygieneScanner:
    """Repository hygiene scanner and cleanup tool"""

    def __init__(self, repo_root: Path = None, dry_run: bool = True):
        self.repo_root = repo_root or Path.cwd()
        self.dry_run = dry_run
        self.findings = {
            "backup_files": [],
            "todo_comments": [],
            "stale_branches": [],
        }
        self.stats = {
            "files_cleaned": 0,
            "branches_analyzed": 0,
            "todos_found": 0,
        }

    def scan_backup_files(self) -> None:
        """Scan for backup files that can be removed"""
        print("Scanning for backup files...")

        backup_patterns = ["*.backup", "*.bak", "*~", "*.old"]
        backup_files = []

        for pattern in backup_patterns:
            backup_files.extend(self.repo_root.rglob(pattern))

        self.findings["backup_files"] = backup_files
        print(f"Found {len(backup_files)} backup files")

    def scan_todo_comments(self) -> None:
        """Scan for TODO comments in code"""
        print("Scanning for TODO comments...")

        py_files = list(self.repo_root.rglob("*.py"))
        py_files = [f for f in py_files if not any(part.startswith(".") for part in f.parts)]

        todo_patterns = [
            (r"#\s*(TODO[:\s].*)", "TODO"),
            (r"#\s*(FIXME[:\s].*)", "FIXME"),
            (r"#\s*(XXX[:\s].*)", "XXX"),
        ]

        for py_file in py_files:
            try:
                with open(py_file, encoding="utf-8") as f:
                    for line_num, line in enumerate(f, 1):
                        for pattern, comment_type in todo_patterns:
                            match = re.search(pattern, line, re.IGNORECASE)
                            if match:
                                self.findings["todo_comments"].append(
                                    {
                                        "file": str(py_file.relative_to(self.repo_root)),
                                        "line": line_num,
                                        "type": comment_type,
                                        "comment": match.group(1).strip(),
                                    }
                                )
                                self.stats["todos_found"] += 1

            except Exception:
                pass

        print(f"Found {self.stats['todos_found']} TODO comments")

    def analyze_stale_branches(self) -> None:
        """Analyze branches for staleness"""
        print("Analyzing repository branches...")

        try:
            branches_output = self._run_git_command(["branch", "-a"])
            if not branches_output:
                return

            merged_output = self._run_git_command(["branch", "--merged", "main"])
            merged_branches = set()

            for line in merged_output.split("\n"):
                line = line.strip()
                if line and not line.startswith("*") and line != "main":
                    merged_branches.add(line)

            for line in branches_output.split("\n"):
                line = line.strip()
                if not line or line.startswith("*") or "HEAD ->" in line:
                    continue

                branch_name = line.replace("remotes/origin/", "")
                if branch_name == "main":
                    continue

                self.stats["branches_analyzed"] += 1

                if branch_name in merged_branches:
                    self.findings["stale_branches"].append(
                        {"name": branch_name, "type": "merged", "action": "Can be safely deleted"}
                    )

        except Exception as e:
            print(f"Error analyzing branches: {e}")

        print(f"Analyzed {self.stats['branches_analyzed']} branches")

    def cleanup_backup_files(self) -> None:
        """Remove backup files"""
        print("\nCleaning up backup files...")

        if self.dry_run:
            print(f"[DRY RUN] Would remove {len(self.findings['backup_files'])} backup files")
            return

        for backup_file in self.findings["backup_files"]:
            try:
                backup_file.unlink()
                self.stats["files_cleaned"] += 1
                print(f"Removed: {backup_file}")
            except Exception as e:
                print(f"Error removing {backup_file}: {e}")

        print(f"Cleaned {self.stats['files_cleaned']} backup files")

    def generate_report(self) -> str:
        """Generate hygiene report"""
        report_lines = [
            "# Repository Hygiene Report",
            "",
            f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Mode**: {'DRY RUN' if self.dry_run else 'LIVE EXECUTION'}",
            "",
            "## Summary",
            "",
            f"- **Backup Files**: {len(self.findings['backup_files'])}",
            f"- **TODO Comments**: {len(self.findings['todo_comments'])}",
            f"- **Stale Branches**: {len(self.findings['stale_branches'])}",
            f"- **Files Cleaned**: {self.stats['files_cleaned']}",
            "",
        ]

        if self.findings["backup_files"]:
            report_lines.extend(
                [
                    "## Backup Files",
                    "",
                    f"Found {len(self.findings['backup_files'])} backup files to clean:",
                    "",
                ]
            )
            for backup_file in self.findings["backup_files"][:10]:
                report_lines.append(f"- {backup_file.relative_to(self.repo_root)}")
            if len(self.findings["backup_files"]) > 10:
                report_lines.append(f"- ... and {len(self.findings['backup_files']) - 10} more")
            report_lines.append("")

        if self.findings["todo_comments"]:
            report_lines.extend([f"## TODO Comments ({len(self.findings['todo_comments'])})", ""])

            todos_by_type = {}
            for todo in self.findings["todo_comments"]:
                todo_type = todo["type"]
                if todo_type not in todos_by_type:
                    todos_by_type[todo_type] = []
                todos_by_type[todo_type].append(todo)

            for todo_type, todos in todos_by_type.items():
                report_lines.append(f"### {todo_type} ({len(todos)})")
                for todo in todos[:5]:
                    report_lines.append(f"- `{todo['file']}:{todo['line']}` - {todo['comment']}")
                if len(todos) > 5:
                    report_lines.append(f"- ... and {len(todos) - 5} more")
                report_lines.append("")

        if self.findings["stale_branches"]:
            report_lines.extend(
                [
                    f"## Stale Branches ({len(self.findings['stale_branches'])})",
                    "",
                    "These branches can be deleted:",
                    "",
                ]
            )

            for branch in self.findings["stale_branches"][:10]:
                report_lines.append(f"- `{branch['name']}` - {branch['action']}")
            if len(self.findings["stale_branches"]) > 10:
                report_lines.append(f"- ... and {len(self.findings['stale_branches']) - 10} more")
            report_lines.append("")

        return "\n".join(report_lines)

    def _run_git_command(self, cmd: list[str]) -> str:
        """Run a git command and return output"""
        try:
            result = subprocess.run(["git"] + cmd, capture_output=True, text=True, check=True, cwd=self.repo_root)
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return ""

    def run_full_scan(self) -> None:
        """Run full repository hygiene scan"""
        print("Repository Hygiene Scanner")
        print("=" * 60)
        print(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE EXECUTION'}")
        print(f"Root: {self.repo_root}")
        print()

        self.scan_backup_files()
        self.scan_todo_comments()
        self.analyze_stale_branches()

        report = self.generate_report()
        report_path = self.repo_root / "repository_hygiene_report.md"

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)

        print(f"\nReport saved to: {report_path}")
        print("\nHygiene scan complete!")


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description="Repository Hygiene - Consolidated Cleanup Tool")
    parser.add_argument("--version", action="version", version="1.0.0")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without executing")
    parser.add_argument("--scan", action="store_true", help="Scan for issues without cleanup")
    parser.add_argument("--backup-cleanup", action="store_true", help="Remove backup files")
    parser.add_argument("--all", action="store_true", help="Run all operations")

    args = parser.parse_args()

    if not any([args.scan, args.backup_cleanup, args.all]):
        parser.print_help()
        return 0

    project_root = Path(__file__).parent.parent.parent
    scanner = RepositoryHygieneScanner(project_root, dry_run=args.dry_run)

    try:
        if args.all or args.scan:
            scanner.run_full_scan()

        if args.all or args.backup_cleanup:
            if not scanner.findings["backup_files"]:
                scanner.scan_backup_files()
            scanner.cleanup_backup_files()

        return 0

    except Exception as e:
        print(f"Hygiene scan failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())




