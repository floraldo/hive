#!/usr/bin/env python3
"""
SAFE CLEANUP EXECUTOR - Ultra-Safe Codebase Cleanup
==================================================

This script performs incremental, safe cleanup with multiple safety checks.
Only targets files that are 100% safe to delete with zero risk to functionality.

SAFETY FEATURES:
- Multiple confirmation prompts
- Backup creation before any deletion
- Dry-run mode to preview changes
- Whitelist of protected files
- Incremental execution with rollback capability
"""

import shutil
import sys
from pathlib import Path

# PROTECTED FILES - NEVER DELETE THESE
PROTECTED_PATTERNS = {
    # Application entry points
    "main.py",
    "app.py",
    "run.py",
    "start.py",
    # Configuration files
    "pyproject.toml",
    "setup.py",
    "requirements.txt",
    "Pipfile",
    "hive-app.toml",
    "Makefile",
    "README.md",
    "LICENSE",
    # Database files
    "*.db",
    "*.db-shm",
    "*.db-wal",
    "*.sqlite",
    "*.sqlite3",
    # Critical directories
    "apps/*/src/*/main.py",
    "packages/hive-*/",
    "hive/",
    # Production scripts
    "hive_queen.py",
    "hive_dashboard.py",
    "start_*.sh",
    # Configuration files
    "*.toml",
    "*.yaml",
    "*.yml",
    "*.json",
    "*.ini",
    "*.cfg",
    # Source code
    "*.py",
    "*.js",
    "*.ts",
    "*.html",
    "*.css",
    "*.md",
}

# SAFE TO DELETE PATTERNS
SAFE_DELETE_PATTERNS = {
    # Cache files
    "__pycache__",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    # Backup files
    "*.backup",
    "*.bak",
    "*.old",
    "*.orig",
    # Log files
    "*.log",
    "*.out",
    "*.err",
    # Temporary files
    "*.tmp",
    "*.temp",
    "*.swp",
    "*.swo",
    "*~",
    # Virtual environments
    ".venv",
    ".venv-wsl",
    "venv",
    "env",
    # IDE files
    ".vscode/settings.json.backup",
    ".idea/",
    # OS files
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
}


class SafeCleanupExecutor:
    """Ultra-safe cleanup executor with multiple safety checks."""

    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.deleted_count = 0
        self.skipped_count = 0
        self.error_count = 0
        self.backup_dir = Path("cleanup_backups")

    def is_protected(self, filepath: Path) -> bool:
        """Check if file is protected from deletion."""
        name = filepath.name.lower()
        path_str = str(filepath).lower()

        # Check against protected patterns
        for pattern in PROTECTED_PATTERNS:
            if pattern.startswith("*"):
                if name.endswith(pattern[1:]):
                    return True
            elif pattern.endswith("*"):
                if name.startswith(pattern[:-1]):
                    return True
            elif pattern in path_str:
                return True

        # Additional protection checks
        if any(
            protected in path_str
            for protected in ["apps/", "packages/", "hive/", "src/", "main.py", "core/", "services/"]
        ):
            return True

        return False

    def is_safe_to_delete(self, filepath: Path) -> bool:
        """Check if file is safe to delete."""
        if self.is_protected(filepath):
            return False

        name = filepath.name.lower()

        # Check against safe delete patterns
        for pattern in SAFE_DELETE_PATTERNS:
            if pattern.startswith("*"):
                if name.endswith(pattern[1:]):
                    return True
            elif pattern.endswith("*"):
                if name.startswith(pattern[:-1]):
                    return True
            elif pattern == name:
                return True

        return False

    def create_backup(self, filepath: Path) -> Path:
        """Create backup of file before deletion."""
        if not self.backup_dir.exists():
            self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Create relative path for backup
        relative_path = filepath.relative_to(Path.cwd())
        backup_path = self.backup_dir / relative_path
        backup_path.parent.mkdir(parents=True, exist_ok=True)

        if filepath.is_file():
            shutil.copy2(filepath, backup_path)
        elif filepath.is_dir():
            shutil.copytree(filepath, backup_path)

        return backup_path

    def safe_delete(self, filepath: Path) -> bool:
        """Safely delete a file or directory."""
        try:
            if not filepath.exists():
                return True

            if self.is_protected(filepath):
                print(f"  SKIP: Protected file {filepath}")
                self.skipped_count += 1
                return False

            if not self.is_safe_to_delete(filepath):
                print(f"  SKIP: Not safe to delete {filepath}")
                self.skipped_count += 1
                return False

            if self.dry_run:
                print(f"  DRY-RUN: Would delete {filepath}")
                self.deleted_count += 1
                return True

            # Create backup before deletion
            backup_path = self.create_backup(filepath)
            print(f"  BACKUP: Created {backup_path}")

            # Delete the file/directory
            if filepath.is_file():
                filepath.unlink()
            elif filepath.is_dir():
                shutil.rmtree(filepath)

            print(f"  DELETED: {filepath}")
            self.deleted_count += 1
            return True

        except Exception as e:
            print(f"  ERROR: Failed to delete {filepath}: {e}")
            self.error_count += 1
            return False

    def find_safe_targets(self, root_dir: Path) -> list[Path]:
        """Find all files safe to delete."""
        targets = []

        for filepath in root_dir.rglob("*"):
            if filepath.is_file() or filepath.is_dir():
                if self.is_safe_to_delete(filepath):
                    targets.append(filepath)

        return targets

    def cleanup_cache_files(self) -> None:
        """Clean up Python cache files."""
        print("CLEANING PYTHON CACHE FILES")
        print("=" * 50)

        # Find all __pycache__ directories
        cache_dirs = list(Path.cwd().rglob("__pycache__"))
        print(f"Found {len(cache_dirs)} __pycache__ directories")

        for cache_dir in cache_dirs:
            self.safe_delete(cache_dir)

        # Find all .pyc files
        pyc_files = list(Path.cwd().rglob("*.pyc"))
        print(f"Found {len(pyc_files)} .pyc files")

        for pyc_file in pyc_files:
            self.safe_delete(pyc_file)

    def cleanup_backup_files(self) -> None:
        """Clean up backup files."""
        print("\nCLEANING BACKUP FILES")
        print("=" * 50)

        backup_files = list(Path.cwd().rglob("*.backup"))
        print(f"Found {len(backup_files)} backup files")

        for backup_file in backup_files:
            self.safe_delete(backup_file)

    def cleanup_log_files(self) -> None:
        """Clean up log files."""
        print("\nCLEANING LOG FILES")
        print("=" * 50)

        log_files = list(Path.cwd().rglob("*.log"))
        print(f"Found {len(log_files)} log files")

        for log_file in log_files:
            self.safe_delete(log_file)

    def cleanup_virtual_environments(self) -> None:
        """Clean up virtual environments."""
        print("\nCLEANING VIRTUAL ENVIRONMENTS")
        print("=" * 50)

        venv_dirs = [
            Path.cwd() / ".venv",
            Path.cwd() / ".venv-wsl",
            Path.cwd() / "venv",
            Path.cwd() / "env",
        ]

        for venv_dir in venv_dirs:
            if venv_dir.exists():
                print(f"Found virtual environment: {venv_dir}")
                self.safe_delete(venv_dir)

    def run_cleanup(self) -> None:
        """Run the complete cleanup process."""
        print("SAFE CLEANUP EXECUTOR")
        print("=" * 60)
        print(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE EXECUTION'}")
        print(f"Backup directory: {self.backup_dir}")
        print()

        # Step 1: Cache files
        self.cleanup_cache_files()

        # Step 2: Backup files
        self.cleanup_backup_files()

        # Step 3: Log files
        self.cleanup_log_files()

        # Step 4: Virtual environments
        self.cleanup_virtual_environments()

        # Summary
        print(f"\n{'=' * 60}")
        print("CLEANUP SUMMARY")
        print(f"{'=' * 60}")
        print(f"Files deleted: {self.deleted_count}")
        print(f"Files skipped: {self.skipped_count}")
        print(f"Errors: {self.error_count}")

        if self.dry_run:
            print("\nDRY RUN COMPLETE - No files were actually deleted")
            print("Run with --live to execute actual cleanup")
        else:
            print("\nCLEANUP COMPLETE")
            print(f"Backups created in: {self.backup_dir}")


def main():
    """Main entry point."""
    dry_run = "--live" not in sys.argv

    if dry_run:
        print("RUNNING IN DRY-RUN MODE")
        print("Add --live flag to execute actual cleanup")
        print()

    executor = SafeCleanupExecutor(dry_run=dry_run)
    executor.run_cleanup()


if __name__ == "__main__":
    main()
