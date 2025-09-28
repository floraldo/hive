#!/usr/bin/env python3
"""
Comprehensive Repository Cleanup Tool

Performs systematic cleanup and reorganization of:
- All documentation files (.md, .txt, .rst)
- Root directory cleanup
- Apps directory organization
- Test directory standardization
- Removal of obsolete/redundant files

Part of the Operational Excellence Campaign for complete platform hardening.
"""

import os
import re
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Set, Tuple


class ComprehensiveCleanup:
    def __init__(self, project_root: Path = None, dry_run: bool = True):
        self.project_root = project_root or Path.cwd()
        self.dry_run = dry_run
        self.changes = []
        self.stats = {
            'files_moved': 0,
            'files_deleted': 0,
            'directories_created': 0,
            'directories_removed': 0
        }
    
    def log_change(self, action: str, source: str, target: str = None):
        """Log a change for reporting"""
        change = {
            'action': action,
            'source': source,
            'target': target,
            'timestamp': datetime.now()
        }
        self.changes.append(change)
        
        if action == 'move':
            self.stats['files_moved'] += 1
        elif action == 'delete':
            self.stats['files_deleted'] += 1
        elif action == 'create_dir':
            self.stats['directories_created'] += 1
        elif action == 'remove_dir':
            self.stats['directories_removed'] += 1
    
    def safe_move(self, source: Path, target: Path):
        """Safely move a file or directory"""
        try:
            if self.dry_run:
                print(f"[DRY RUN] Would move: {source} -> {target}")
                self.log_change('move', str(source), str(target))
                return True
            
            # Create target directory if it doesn't exist
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(target))
            print(f"Moved: {source} -> {target}")
            self.log_change('move', str(source), str(target))
            return True
        except Exception as e:
            print(f"Error moving {source} to {target}: {e}")
            return False
    
    def safe_delete(self, path: Path):
        """Safely delete a file or directory"""
        try:
            if self.dry_run:
                print(f"[DRY RUN] Would delete: {path}")
                self.log_change('delete', str(path))
                return True
            
            if path.is_file():
                path.unlink()
                print(f"Deleted file: {path}")
            elif path.is_dir():
                shutil.rmtree(path)
                print(f"Deleted directory: {path}")
            
            self.log_change('delete', str(path))
            return True
        except Exception as e:
            print(f"Error deleting {path}: {e}")
            return False
    
    def create_directory(self, path: Path):
        """Create directory structure"""
        try:
            if self.dry_run:
                print(f"[DRY RUN] Would create directory: {path}")
                self.log_change('create_dir', str(path))
                return True
            
            path.mkdir(parents=True, exist_ok=True)
            print(f"Created directory: {path}")
            self.log_change('create_dir', str(path))
            return True
        except Exception as e:
            print(f"Error creating directory {path}: {e}")
            return False
    
    def find_all_documentation(self) -> Dict[str, List[Path]]:
        """Find all documentation files categorized by type and location"""
        docs = {
            'root_docs': [],
            'claudedocs': [],
            'apps_docs': [],
            'packages_docs': [],
            'tests_docs': [],
            'archive_docs': [],
            'other_docs': []
        }
        
        doc_extensions = {'.md', '.txt', '.rst', '.adoc'}
        
        for file_path in self.project_root.rglob('*'):
            if not file_path.is_file():
                continue
            
            if file_path.suffix.lower() not in doc_extensions:
                continue
            
            # Skip hidden files and common ignore patterns
            if any(part.startswith('.') for part in file_path.parts):
                continue
            
            relative_path = file_path.relative_to(self.project_root)
            path_parts = relative_path.parts
            
            # Categorize by location
            if len(path_parts) == 1:  # Root level
                docs['root_docs'].append(file_path)
            elif path_parts[0] == 'claudedocs':
                docs['claudedocs'].append(file_path)
            elif path_parts[0] == 'apps':
                docs['apps_docs'].append(file_path)
            elif path_parts[0] == 'packages':
                docs['packages_docs'].append(file_path)
            elif path_parts[0] == 'tests':
                docs['tests_docs'].append(file_path)
            elif 'archive' in str(file_path).lower():
                docs['archive_docs'].append(file_path)
            else:
                docs['other_docs'].append(file_path)
        
        return docs
    
    def analyze_documentation_relevance(self, docs: Dict[str, List[Path]]) -> Dict[str, Dict[str, List[Path]]]:
        """Analyze documentation for relevance and organization needs"""
        analysis = {}
        
        for category, files in docs.items():
            analysis[category] = {
                'keep_current': [],
                'archive': [],
                'delete': [],
                'reorganize': []
            }
            
            for file_path in files:
                filename = file_path.name.lower()
                content_sample = self.get_file_sample(file_path)
                age_days = self.get_file_age_days(file_path)
                
                # Determine action based on filename and content analysis
                if self.should_delete(filename, content_sample, age_days):
                    analysis[category]['delete'].append(file_path)
                elif self.should_archive(filename, content_sample, age_days):
                    analysis[category]['archive'].append(file_path)
                elif self.should_reorganize(filename, content_sample):
                    analysis[category]['reorganize'].append(file_path)
                else:
                    analysis[category]['keep_current'].append(file_path)
        
        return analysis
    
    def get_file_sample(self, file_path: Path, lines: int = 10) -> str:
        """Get sample of file content for analysis"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                sample_lines = []
                for i, line in enumerate(f):
                    if i >= lines:
                        break
                    sample_lines.append(line.strip())
                return '\n'.join(sample_lines)
        except Exception:
            return ""
    
    def get_file_age_days(self, file_path: Path) -> int:
        """Get file age in days"""
        try:
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            return (datetime.now() - mtime).days
        except Exception:
            return 0
    
    def should_delete(self, filename: str, content: str, age_days: int) -> bool:
        """Determine if file should be deleted"""
        delete_patterns = [
            # Temporary files
            'temp', 'tmp', 'scratch', 'test_', 'debug_',
            # Old logs and reports that are superseded
            'old_', 'backup_', 'copy_', '_backup', '_old',
            # Very old files with no current relevance
        ]
        
        # Files that are clearly temporary or superseded
        if any(pattern in filename for pattern in delete_patterns):
            return True
        
        # Very old files (>6 months) with minimal content
        if age_days > 180 and len(content) < 500:
            return True
        
        # Empty or nearly empty files
        if len(content.strip()) < 50:
            return True
        
        return False
    
    def should_archive(self, filename: str, content: str, age_days: int) -> bool:
        """Determine if file should be archived"""
        archive_patterns = [
            # Version-specific reports that are superseded
            'v1_', 'v2_', 'v3_', 'phase_', 'report_', 
            # Historical analysis
            'analysis_', 'summary_', '_summary', '_analysis',
            # Completed migration/implementation docs
            'migration_', 'implementation_', 'strategy_'
        ]
        
        # Historical documents
        if any(pattern in filename for pattern in archive_patterns):
            return True
        
        # Old certification reports (keep only latest)
        if 'certification' in filename and age_days > 30:
            return True
        
        # Phase reports and similar historical docs
        if any(word in filename for word in ['phase', 'sprint', 'milestone']) and age_days > 14:
            return True
        
        return False
    
    def should_reorganize(self, filename: str, content: str) -> bool:
        """Determine if file needs reorganization"""
        # Files that should be in specific locations
        reorganize_indicators = [
            'architecture', 'design', 'api', 'integration',
            'deployment', 'setup', 'configuration'
        ]
        
        return any(indicator in filename or indicator in content.lower() 
                  for indicator in reorganize_indicators)
    
    def clean_root_directory(self):
        """Clean up root directory files"""
        print("\n=== CLEANING ROOT DIRECTORY ===")
        
        root_files = list(self.project_root.glob('*'))
        
        # Analyze root files
        for file_path in root_files:
            if not file_path.is_file():
                continue
            
            filename = file_path.name.lower()
            
            # Files to definitely keep in root
            keep_in_root = {
                'readme.md', 'license', 'license.txt', 'license.md',
                'changelog.md', 'contributing.md', 'code_of_conduct.md',
                'pyproject.toml', 'poetry.lock', 'makefile',
                '.gitignore', '.pre-commit-config.yaml',
                'docker-compose.yml', 'docker-compose.yaml',
                'dockerfile', 'dockerfile.dev'
            }
            
            if filename in keep_in_root:
                continue
            
            # Large documentation files that should be organized
            if file_path.suffix.lower() == '.md' and file_path.stat().st_size > 10000:
                # Move large docs to docs/reports/
                target_dir = self.project_root / 'docs' / 'reports'
                self.create_directory(target_dir)
                target_path = target_dir / file_path.name
                self.safe_move(file_path, target_path)
            
            # Analysis and report files
            elif any(keyword in filename for keyword in ['analysis', 'report', 'summary', 'plan']):
                if 'operational' in filename or 'cleanup' in filename:
                    # Recent operational docs go to docs/operations/
                    target_dir = self.project_root / 'docs' / 'operations'
                    self.create_directory(target_dir)
                    target_path = target_dir / file_path.name
                    self.safe_move(file_path, target_path)
                else:
                    # Other reports go to docs/reports/
                    target_dir = self.project_root / 'docs' / 'reports'
                    self.create_directory(target_dir)
                    target_path = target_dir / file_path.name
                    self.safe_move(file_path, target_path)
            
            # Old/temporary files to delete
            elif any(pattern in filename for pattern in ['temp', 'tmp', 'old', 'backup', 'test_']):
                self.safe_delete(file_path)
    
    def clean_apps_directories(self):
        """Clean up documentation in apps directories"""
        print("\n=== CLEANING APPS DIRECTORIES ===")
        
        apps_dir = self.project_root / 'apps'
        if not apps_dir.exists():
            return
        
        for app_dir in apps_dir.iterdir():
            if not app_dir.is_dir():
                continue
            
            print(f"\nCleaning app: {app_dir.name}")
            
            # Create standard docs structure for each app
            docs_dir = app_dir / 'docs'
            self.create_directory(docs_dir)
            
            # Find all docs in this app
            app_docs = []
            for doc_file in app_dir.rglob('*.md'):
                if 'docs' not in doc_file.parts:  # Not already in docs/
                    app_docs.append(doc_file)
            
            # Organize app docs
            for doc_file in app_docs:
                filename = doc_file.name.lower()
                
                # Keep README.md at app root
                if filename == 'readme.md' and doc_file.parent == app_dir:
                    continue
                
                # Move other docs to docs/
                target_path = docs_dir / doc_file.name
                self.safe_move(doc_file, target_path)
    
    def clean_test_directories(self):
        """Clean up and standardize test directories"""
        print("\n=== CLEANING TEST DIRECTORIES ===")
        
        # Clean main tests directory
        tests_dir = self.project_root / 'tests'
        if tests_dir.exists():
            self.standardize_test_directory(tests_dir)
        
        # Clean package test directories
        packages_dir = self.project_root / 'packages'
        if packages_dir.exists():
            for package_dir in packages_dir.iterdir():
                if package_dir.is_dir():
                    package_tests = package_dir / 'tests'
                    if package_tests.exists():
                        self.standardize_test_directory(package_tests)
        
        # Clean app test directories
        apps_dir = self.project_root / 'apps'
        if apps_dir.exists():
            for app_dir in apps_dir.iterdir():
                if app_dir.is_dir():
                    app_tests = app_dir / 'tests'
                    if app_tests.exists():
                        self.standardize_test_directory(app_tests)
    
    def standardize_test_directory(self, test_dir: Path):
        """Standardize a single test directory structure"""
        print(f"Standardizing test directory: {test_dir}")
        
        # Create standard structure
        standard_dirs = ['unit', 'integration', 'e2e']
        for dir_name in standard_dirs:
            dir_path = test_dir / dir_name
            self.create_directory(dir_path)
            
            # Create __init__.py if it doesn't exist
            init_file = dir_path / '__init__.py'
            if not init_file.exists() and not self.dry_run:
                init_file.touch()
        
        # Move test files to appropriate directories
        for test_file in test_dir.glob('test_*.py'):
            if test_file.parent.name in standard_dirs:
                continue  # Already in correct location
            
            # Determine appropriate directory based on filename
            filename = test_file.name.lower()
            if 'integration' in filename or 'e2e' in filename:
                target_dir = test_dir / 'integration'
            elif 'unit' in filename:
                target_dir = test_dir / 'unit'
            else:
                target_dir = test_dir / 'unit'  # Default to unit tests
            
            target_path = target_dir / test_file.name
            self.safe_move(test_file, target_path)
        
        # Clean up empty directories and old files
        for item in test_dir.iterdir():
            if item.is_dir() and item.name not in standard_dirs and item.name != '__pycache__':
                # Check if directory is empty or contains only __init__.py
                contents = list(item.iterdir())
                if not contents or (len(contents) == 1 and contents[0].name == '__init__.py'):
                    self.safe_delete(item)
    
    def reorganize_documentation(self):
        """Main documentation reorganization process"""
        print("\n=== COMPREHENSIVE DOCUMENTATION REORGANIZATION ===")
        
        # Find all documentation
        docs = self.find_all_documentation()
        
        # Analyze what to do with each category
        analysis = self.analyze_documentation_relevance(docs)
        
        # Create organized structure
        self.create_documentation_structure()
        
        # Process each category
        for category, actions in analysis.items():
            print(f"\nProcessing {category}:")
            
            # Archive old documents
            if actions['archive']:
                archive_dir = self.project_root / 'docs' / 'archive' / category
                self.create_directory(archive_dir)
                for file_path in actions['archive']:
                    target_path = archive_dir / file_path.name
                    self.safe_move(file_path, target_path)
            
            # Delete obsolete documents
            for file_path in actions['delete']:
                self.safe_delete(file_path)
            
            # Reorganize documents that need better placement
            for file_path in actions['reorganize']:
                new_location = self.determine_new_location(file_path)
                if new_location and new_location != file_path.parent:
                    self.create_directory(new_location)
                    target_path = new_location / file_path.name
                    self.safe_move(file_path, target_path)
    
    def create_documentation_structure(self):
        """Create organized documentation structure"""
        doc_structure = [
            'docs/architecture',
            'docs/operations', 
            'docs/reports',
            'docs/archive/claudedocs',
            'docs/archive/reports',
            'docs/archive/analysis',
            'docs/guides',
            'docs/api'
        ]
        
        for dir_path in doc_structure:
            full_path = self.project_root / dir_path
            self.create_directory(full_path)
    
    def determine_new_location(self, file_path: Path) -> Path:
        """Determine the best new location for a file"""
        filename = file_path.name.lower()
        content_sample = self.get_file_sample(file_path)
        
        # Architecture documents
        if any(word in filename or word in content_sample.lower() 
               for word in ['architecture', 'design', 'adr', 'pattern']):
            return self.project_root / 'docs' / 'architecture'
        
        # Operational documents
        elif any(word in filename for word in ['operational', 'deployment', 'setup', 'config']):
            return self.project_root / 'docs' / 'operations'
        
        # Reports and analysis
        elif any(word in filename for word in ['report', 'analysis', 'summary', 'certification']):
            return self.project_root / 'docs' / 'reports'
        
        # Guides and tutorials
        elif any(word in filename for word in ['guide', 'tutorial', 'howto', 'setup']):
            return self.project_root / 'docs' / 'guides'
        
        # Default to reports
        return self.project_root / 'docs' / 'reports'
    
    def generate_cleanup_report(self) -> str:
        """Generate comprehensive cleanup report"""
        report = []
        report.append("# Comprehensive Repository Cleanup Report")
        report.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"**Mode**: {'DRY RUN' if self.dry_run else 'LIVE EXECUTION'}")
        report.append("")
        
        # Statistics
        report.append("## Summary Statistics")
        report.append(f"- **Files moved**: {self.stats['files_moved']}")
        report.append(f"- **Files deleted**: {self.stats['files_deleted']}")
        report.append(f"- **Directories created**: {self.stats['directories_created']}")
        report.append(f"- **Directories removed**: {self.stats['directories_removed']}")
        report.append(f"- **Total changes**: {len(self.changes)}")
        report.append("")
        
        # Detailed changes
        report.append("## Detailed Changes")
        report.append("")
        
        # Group changes by action
        changes_by_action = {}
        for change in self.changes:
            action = change['action']
            if action not in changes_by_action:
                changes_by_action[action] = []
            changes_by_action[action].append(change)
        
        for action, action_changes in changes_by_action.items():
            report.append(f"### {action.replace('_', ' ').title()} ({len(action_changes)})")
            for change in action_changes[:20]:  # Limit to first 20
                if change['target']:
                    report.append(f"- `{change['source']}` → `{change['target']}`")
                else:
                    report.append(f"- `{change['source']}`")
            if len(action_changes) > 20:
                report.append(f"- ... and {len(action_changes) - 20} more")
            report.append("")
        
        return "\n".join(report)
    
    def run_comprehensive_cleanup(self):
        """Run the complete cleanup process"""
        print("COMPREHENSIVE REPOSITORY CLEANUP")
        print("=" * 60)
        print(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE EXECUTION'}")
        print(f"Root: {self.project_root}")
        print()
        
        try:
            # 1. Clean root directory
            self.clean_root_directory()
            
            # 2. Reorganize all documentation
            self.reorganize_documentation()
            
            # 3. Clean apps directories
            self.clean_apps_directories()
            
            # 4. Clean and standardize test directories
            self.clean_test_directories()
            
            # Generate and save report
            report = self.generate_cleanup_report()
            report_path = self.project_root / "COMPREHENSIVE_CLEANUP_REPORT.md"
            
            if not self.dry_run:
                with open(report_path, 'w', encoding='utf-8') as f:
                    f.write(report)
                print(f"\nReport saved to: {report_path}")
            else:
                print(f"\n[DRY RUN] Report would be saved to: {report_path}")
            
            print("\nCOMPREHENSIVE CLEANUP COMPLETE")
            print(f"Total changes: {len(self.changes)}")
            
            return True
            
        except Exception as e:
            print(f"\nCleanup failed: {e}")
            return False

def main():
    """Main execution function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Comprehensive Repository Cleanup Tool")
    parser.add_argument("--execute", action="store_true", 
                       help="Actually perform cleanup (default is dry-run)")
    parser.add_argument("--root", type=str, default=".",
                       help="Project root directory")
    
    args = parser.parse_args()
    
    project_root = Path(args.root).resolve()
    dry_run = not args.execute
    
    cleanup = ComprehensiveCleanup(project_root, dry_run)
    success = cleanup.run_comprehensive_cleanup()
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
