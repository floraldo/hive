#!/usr/bin/env python3
"""
Log Management Utility for Hive Platform V4.4

Organizes scattered log files into a clean, structured hierarchy and provides
cleanup capabilities for log file maintenance.
"""

import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

from hive_logging import get_logger

logger = get_logger(__name__)


@dataclass
class LogFileInfo:
    """Information about a log file"""

    path: Path
    size: int
    modified: datetime
    category: str
    component: str


class LogOrganizer:
    """Organizes and cleans up scattered log files"""

    def __init__(self, hive_root: Path = None):
        self.hive_root = hive_root or Path.cwd()
        self.logs_root = self.hive_root / "logs"
        self.archive_root = self.logs_root / "archive"

        # Create standard directory structure
        self.directories = {
            "current": self.logs_root / "current",
            "archive": self.archive_root,
            "components": self.logs_root / "components",
            "workers": self.logs_root / "workers",
            "apps": self.logs_root / "apps",
            "tests": self.logs_root / "tests",
        }

    def scan_log_files(self) -> List[LogFileInfo]:
        """Scan for all log files in the project"""
        log_files = []

        # Define patterns to exclude from scanning
        exclude_patterns = [
            r"\.git/",
            r"__pycache__/",
            r"\.pyc$",
            r"node_modules/",
            r"\.env",
        ]

        logger.info("Scanning for log files...")

        for log_file in self.hive_root.rglob("*.log"):
            # Skip excluded patterns
            if any(re.search(pattern, str(log_file)) for pattern in exclude_patterns):
                continue

            try:
                stat = log_file.stat()
                category, component = self._categorize_log_file(log_file)

                log_info = LogFileInfo(
                    path=log_file,
                    size=stat.st_size,
                    modified=datetime.fromtimestamp(stat.st_mtime),
                    category=category,
                    component=component,
                )
                log_files.append(log_info)

            except (OSError, IOError) as e:
                logger.warning(f"Could not access log file {log_file}: {e}")

        logger.info(f"Found {len(log_files)} log files")
        return log_files

    def _categorize_log_file(self, log_path: Path) -> tuple[str, str]:
        """Categorize a log file by type and component"""
        path_str = str(log_path).lower()
        name = log_path.stem.lower()

        # Component identification
        if "queen" in name:
            component = "queen"
        elif "worker" in name:
            component = "worker"
        elif "reviewer" in name:
            component = "reviewer"
        elif "planner" in name:
            component = "planner"
        elif "orchestrator" in name:
            component = "orchestrator"
        elif "ecosystemiser" in name:
            component = "ecosystemiser"
        elif "dashboard" in name:
            component = "dashboard"
        elif any(app in path_str for app in ["ai-reviewer", "ai-planner"]):
            component = "apps"
        elif "test" in path_str:
            component = "tests"
        else:
            component = "misc"

        # Category identification
        if "stderr" in name:
            category = "stderr"
        elif "stdout" in name:
            category = "stdout"
        elif "archive" in path_str:
            category = "archive"
        elif any(test_indicator in path_str for test_indicator in ["test", "benchmark"]):
            category = "tests"
        else:
            category = "application"

        return category, component

    def organize_logs(self, dry_run: bool = True) -> Dict[str, int]:
        """Organize scattered logs into proper structure"""
        log_files = self.scan_log_files()

        # Group files by target location
        operations = {"moved": 0, "skipped": 0, "errors": 0, "archived": 0}

        # Create directories
        if not dry_run:
            for dir_path in self.directories.values():
                dir_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Organizing {len(log_files)} log files (dry_run={dry_run})")

        for log_file in log_files:
            try:
                target_path = self._get_target_path(log_file)

                # Skip if already in correct location
                if log_file.path == target_path:
                    operations["skipped"] += 1
                    continue

                logger.info(f"{'Would move' if dry_run else 'Moving'} {log_file.path} -> {target_path}")

                if not dry_run:
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(log_file.path), str(target_path))

                operations["moved"] += 1

            except Exception as e:
                logger.error(f"Error processing {log_file.path}: {e}")
                operations["errors"] += 1

        return operations

    def _get_target_path(self, log_file: LogFileInfo) -> Path:
        """Determine target path for a log file"""

        # Archive old files
        if log_file.modified < datetime.now() - timedelta(days=7):
            date_str = log_file.modified.strftime("%Y%m%d")
            return self.archive_root / date_str / log_file.path.name

        # Current files go to category-based structure
        if log_file.category == "tests":
            return self.directories["tests"] / log_file.path.name
        elif log_file.component == "apps":
            return self.directories["apps"] / log_file.path.name
        elif log_file.component in ["worker"]:
            return self.directories["workers"] / log_file.path.name
        elif log_file.component in ["queen", "reviewer", "planner", "orchestrator", "dashboard"]:
            return self.directories["components"] / f"{log_file.component}.log"
        else:
            return self.directories["current"] / log_file.path.name

    def cleanup_old_logs(self, days_old: int = 30, dry_run: bool = True) -> Dict[str, int]:
        """Clean up log files older than specified days"""
        cutoff_date = datetime.now() - timedelta(days=days_old)

        operations = {"deleted": 0, "size_freed": 0, "errors": 0}

        logger.info(f"Cleaning up logs older than {days_old} days (dry_run={dry_run})")

        for log_file in self.scan_log_files():
            if log_file.modified < cutoff_date:
                try:
                    logger.info(
                        f"{'Would delete' if dry_run else 'Deleting'} {log_file.path} "
                        f"(modified: {log_file.modified.strftime('%Y-%m-%d')}, "
                        f"size: {log_file.size} bytes)"
                    )

                    if not dry_run:
                        log_file.path.unlink()

                    operations["deleted"] += 1
                    operations["size_freed"] += log_file.size

                except Exception as e:
                    logger.error(f"Error deleting {log_file.path}: {e}")
                    operations["errors"] += 1

        return operations

    def consolidate_duplicate_logs(self, dry_run: bool = True) -> Dict[str, int]:
        """Consolidate duplicate log files"""
        log_files = self.scan_log_files()

        # Group by name and component
        file_groups = {}
        for log_file in log_files:
            key = (log_file.component, log_file.path.stem.split("-")[0])  # Base name without IDs
            if key not in file_groups:
                file_groups[key] = []
            file_groups[key].append(log_file)

        operations = {"consolidated": 0, "removed": 0, "errors": 0}

        logger.info(f"Consolidating duplicate logs (dry_run={dry_run})")

        for key, files in file_groups.items():
            if len(files) > 1:
                # Keep the newest file, remove others
                files.sort(key=lambda f: f.modified, reverse=True)
                newest = files[0]

                for old_file in files[1:]:
                    try:
                        logger.info(f"{'Would remove' if dry_run else 'Removing'} duplicate: {old_file.path}")

                        if not dry_run:
                            old_file.path.unlink()

                        operations["removed"] += 1

                    except Exception as e:
                        logger.error(f"Error removing duplicate {old_file.path}: {e}")
                        operations["errors"] += 1

                operations["consolidated"] += 1

        return operations

    def generate_report(self) -> str:
        """Generate a report of current log file status"""
        log_files = self.scan_log_files()

        # Statistics
        total_files = len(log_files)
        total_size = sum(f.size for f in log_files)

        # Group by category and component
        by_category = {}
        by_component = {}

        for log_file in log_files:
            by_category[log_file.category] = by_category.get(log_file.category, 0) + 1
            by_component[log_file.component] = by_component.get(log_file.component, 0) + 1

        # Recent activity
        recent_files = [f for f in log_files if f.modified > datetime.now() - timedelta(days=1)]
        old_files = [f for f in log_files if f.modified < datetime.now() - timedelta(days=30)]

        report = f"""
# Hive Log Management Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Summary
- Total log files: {total_files}
- Total size: {total_size / 1024 / 1024:.1f} MB
- Recent files (< 1 day): {len(recent_files)}
- Old files (> 30 days): {len(old_files)}

## By Category
"""
        for category, count in sorted(by_category.items()):
            report += f"- {category}: {count} files\n"

        report += "\n## By Component\n"
        for component, count in sorted(by_component.items()):
            report += f"- {component}: {count} files\n"

        # Recommendations
        report += f"""
## Recommendations
- Consider archiving {len(old_files)} old files
- Clean up files older than 30 days to free {sum(f.size for f in old_files) / 1024 / 1024:.1f} MB
- Organize scattered files into standard structure
"""

        return report


def main():
    """Main entry point for log management utility"""
    import argparse

    parser = argparse.ArgumentParser(description="Hive Log Management Utility")
    parser.add_argument("--organize", action="store_true", help="Organize scattered log files")
    parser.add_argument("--cleanup", type=int, metavar="DAYS", help="Clean up logs older than N days")
    parser.add_argument("--consolidate", action="store_true", help="Consolidate duplicate log files")
    parser.add_argument("--report", action="store_true", help="Generate log status report")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--hive-root", type=Path, help="Hive project root directory")

    args = parser.parse_args()

    organizer = LogOrganizer(args.hive_root)

    if args.report:
        print(organizer.generate_report())

    if args.organize:
        results = organizer.organize_logs(dry_run=args.dry_run)
        print(f"Organization results: {results}")

    if args.cleanup:
        results = organizer.cleanup_old_logs(days_old=args.cleanup, dry_run=args.dry_run)
        print(f"Cleanup results: {results}")

    if args.consolidate:
        results = organizer.consolidate_duplicate_logs(dry_run=args.dry_run)
        print(f"Consolidation results: {results}")

    if not any([args.organize, args.cleanup, args.consolidate, args.report]):
        print("No action specified. Use --help for options.")


if __name__ == "__main__":
    main()
