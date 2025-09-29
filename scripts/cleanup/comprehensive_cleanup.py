#!/usr/bin/env python3
"""
Comprehensive Hive Codebase Cleanup Script

This script performs systematic cleanup of the Hive codebase:
1. Moves root Python files to appropriate locations
2. Consolidates documentation structure
3. Removes backup files
4. Fixes basic golden rule violations
"""

import os
import re
import shutil
from pathlib import Path
from typing import List


class HiveCleanup:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.cleanup_log = []
    
    def log_action(self, action: str):
        """Log cleanup actions for review."""
        self.cleanup_log.append(action)
        print(f"[OK] {action}")
    
    def move_root_python_files(self):
        """Move Python files from root to appropriate locations."""
        root_files = {
            'async_resource_patterns.py': 'scripts/analysis/',
            'check_current_violations.py': 'scripts/validation/',
            'debug_path_matching.py': 'scripts/debug/',
            'fix_all_syntax_errors.py': 'scripts/fixes/',
            'smart_final_fixer.py': 'scripts/fixes/'
        }
        
        for file_name, target_dir in root_files.items():
            source = self.project_root / file_name
            if source.exists():
                target_path = self.project_root / target_dir
                target_path.mkdir(parents=True, exist_ok=True)
                target_file = target_path / file_name
                shutil.move(str(source), str(target_file))
                self.log_action(f"Moved {file_name} to {target_dir}")
    
    def consolidate_documentation(self):
        """Consolidate docs and claudedocs directories."""
        claudedocs_path = self.project_root / "claudedocs"
        docs_path = self.project_root / "docs"
        
        if not claudedocs_path.exists():
            return
        
        # Create target directories in docs
        target_dirs = {
            'ADR-*.md': 'docs/architecture/adr/',
            '*_CERTIFICATION_*.md': 'docs/reports/certifications/',
            '*_REPORT*.md': 'docs/reports/',
            'optimization_*.md': 'docs/optimization/',
            'performance_*.md': 'docs/performance/',
            'V*_*.md': 'docs/reports/versions/',
            'PHASE_*.md': 'docs/reports/phases/',
            'hive_*.md': 'docs/reports/platform/',
            'ecosystemiser_*.md': 'docs/reports/ecosystemiser/',
        }
        
        # Move files based on patterns
        for pattern, target_dir in target_dirs.items():
            target_path = self.project_root / target_dir
            target_path.mkdir(parents=True, exist_ok=True)
            
            for file_path in claudedocs_path.glob(pattern):
                if file_path.is_file():
                    target_file = target_path / file_path.name
                    shutil.move(str(file_path), str(target_file))
                    self.log_action(f"Moved {file_path.name} to {target_dir}")
        
        # Move remaining files to docs/reports/misc/
        misc_dir = docs_path / "reports" / "misc"
        misc_dir.mkdir(parents=True, exist_ok=True)
        
        for file_path in claudedocs_path.iterdir():
            if file_path.is_file() and file_path.suffix == '.md':
                target_file = misc_dir / file_path.name
                shutil.move(str(file_path), str(target_file))
                self.log_action(f"Moved {file_path.name} to docs/reports/misc/")
        
        # Move archive subdirectory
        archive_src = claudedocs_path / "archive"
        if archive_src.exists():
            archive_dst = docs_path / "reports" / "archive" / "claudedocs"
            archive_dst.mkdir(parents=True, exist_ok=True)
            shutil.move(str(archive_src), str(archive_dst))
            self.log_action("Moved claudedocs/archive to docs/reports/archive/claudedocs/")
        
        # Remove empty claudedocs directory
        if claudedocs_path.exists() and not any(claudedocs_path.iterdir()):
            claudedocs_path.rmdir()
            self.log_action("Removed empty claudedocs directory")
    
    def remove_backup_files(self):
        """Remove .backup files throughout the codebase."""
        backup_count = 0
        for backup_file in self.project_root.rglob("*.backup"):
            backup_file.unlink()
            backup_count += 1
        
        if backup_count > 0:
            self.log_action(f"Removed {backup_count} .backup files")
    
    def fix_print_statements_sample(self):
        """Fix a sample of print statements to show the pattern."""
        # Focus on ai-deployer as it has many violations
        deployer_agent = self.project_root / "apps/ai-deployer/src/ai_deployer/agent.py"
        
        if deployer_agent.exists():
            content = deployer_agent.read_text()
            
            # Add logging import if not present
            if "from hive_logging import get_logger" not in content:
                # Find the first import and add after it
                lines = content.split('\n')
                import_added = False
                for i, line in enumerate(lines):
                    if line.startswith('import ') or line.startswith('from '):
                        if not import_added:
                            lines.insert(i + 1, "from hive_logging import get_logger")
                            lines.insert(i + 2, "")
                            lines.insert(i + 3, "logger = get_logger(__name__)")
                            import_added = True
                            break
                
                if import_added:
                    content = '\n'.join(lines)
            
            # Replace some print statements with logger calls
            replacements = [
                (r'print\(f?"([^"]*)"?\)', r'logger.info("\1")'),
                (r'print\(f"([^"]*)", ([^)]+)\)', r'logger.info("\1", extra={"context": \2})'),
            ]
            
            changes_made = 0
            for pattern, replacement in replacements:
                new_content, count = re.subn(pattern, replacement, content)
                if count > 0:
                    content = new_content
                    changes_made += count
            
            if changes_made > 0:
                deployer_agent.write_text(content)
                self.log_action(f"Fixed {changes_made} print statements in ai-deployer/agent.py")
    
    def create_cleanup_summary(self):
        """Create a summary of cleanup actions performed."""
        summary_path = self.project_root / "docs/reports/cleanup_summary.md"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        
        summary_content = f"""# Hive Codebase Cleanup Summary

**Generated**: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Actions Performed

{chr(10).join(f"- {action}" for action in self.cleanup_log)}

## Next Steps

1. Run golden tests to verify improvements: `python -m pytest packages/hive-tests/tests/unit/test_architecture.py`
2. Review moved files and update any broken links
3. Continue fixing remaining golden rule violations
4. Update documentation index

## Files Moved

Root Python files have been relocated to appropriate directories under `scripts/`.
Documentation has been consolidated from `claudedocs/` into organized `docs/` structure.
Backup files have been removed to clean up the repository.

---

*This cleanup maintains all important code and documentation while organizing for better maintainability.*
"""
        
        summary_path.write_text(summary_content)
        self.log_action(f"Created cleanup summary at {summary_path}")
    
    def run_cleanup(self):
        """Execute the full cleanup process."""
        print("Starting Hive Codebase Cleanup...")
        print("=" * 50)
        
        self.move_root_python_files()
        self.consolidate_documentation()
        self.remove_backup_files()
        self.fix_print_statements_sample()
        self.create_cleanup_summary()
        
        print("=" * 50)
        print(f"Cleanup completed! {len(self.cleanup_log)} actions performed.")
        print("Review the cleanup summary in docs/reports/cleanup_summary.md")

if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent
    cleanup = HiveCleanup(project_root)
    cleanup.run_cleanup()
