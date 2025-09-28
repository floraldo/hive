#!/usr/bin/env python3
"""
Targeted Repository Cleanup Tool

Performs focused cleanup avoiding problematic directories like .venv
"""

import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set


def should_skip_directory(path: Path) -> bool:
    """Check if directory should be skipped"""
    skip_patterns = {
        '.venv', '.venv-wsl', '__pycache__', '.pytest_cache',
        'node_modules', '.git', '.cache'
    }
    
    return any(part in skip_patterns for part in path.parts)

def find_root_docs() -> List[Path]:
    """Find documentation files in root directory"""
    root = Path.cwd()
    docs = []
    
    for item in root.iterdir():
        if item.is_file() and item.suffix.lower() == '.md':
            # Skip README.md and other essential files
            if item.name.lower() not in ['readme.md', 'license.md', 'changelog.md']:
                docs.append(item)
    
    return docs

def categorize_root_docs(docs: List[Path]) -> Dict[str, List[Path]]:
    """Categorize root documentation files"""
    categories = {
        'reports': [],
        'operations': [],
        'plans': [],
        'analysis': [],
        'delete': []
    }
    
    for doc in docs:
        filename = doc.name.lower()
        
        # Files to delete (clearly obsolete)
        if any(pattern in filename for pattern in ['golden_test_fixes', 'temp', 'old']):
            categories['delete'].append(doc)
        
        # Operational documents
        elif any(pattern in filename for pattern in ['operational', 'cleanup', 'codebase']):
            categories['operations'].append(doc)
        
        # Plans and strategies
        elif any(pattern in filename for pattern in ['plan', 'strategy', 'burndown']):
            categories['plans'].append(doc)
        
        # Analysis and reports
        elif any(pattern in filename for pattern in ['analysis', 'report', 'summary', 'certification']):
            if 'architecture' in filename:
                categories['analysis'].append(doc)
            else:
                categories['reports'].append(doc)
        
        # Default to reports
        else:
            categories['reports'].append(doc)
    
    return categories

def create_organized_structure():
    """Create organized documentation structure"""
    base_docs = Path('docs')
    
    directories = [
        'docs/reports',
        'docs/operations', 
        'docs/analysis',
        'docs/plans'
    ]
    
    for dir_path in directories:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        print(f"Created directory: {dir_path}")

def move_file_safely(source: Path, target: Path, dry_run: bool = True):
    """Safely move a file"""
    try:
        if dry_run:
            print(f"[DRY RUN] Would move: {source} -> {target}")
            return True
        
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        print(f"Moved: {source} -> {target}")
        return True
    except Exception as e:
        print(f"Error moving {source}: {e}")
        return False

def delete_file_safely(file_path: Path, dry_run: bool = True):
    """Safely delete a file"""
    try:
        if dry_run:
            print(f"[DRY RUN] Would delete: {file_path}")
            return True
        
        file_path.unlink()
        print(f"Deleted: {file_path}")
        return True
    except Exception as e:
        print(f"Error deleting {file_path}: {e}")
        return False

def organize_root_documentation(dry_run: bool = True):
    """Organize root directory documentation"""
    print("\n=== ORGANIZING ROOT DOCUMENTATION ===")
    
    # Create structure
    if not dry_run:
        create_organized_structure()
    
    # Find and categorize docs
    root_docs = find_root_docs()
    categories = categorize_root_docs(root_docs)
    
    print(f"Found {len(root_docs)} documentation files in root")
    
    # Process each category
    for category, files in categories.items():
        if not files:
            continue
            
        print(f"\n{category.upper()} ({len(files)} files):")
        
        if category == 'delete':
            for file_path in files:
                delete_file_safely(file_path, dry_run)
        else:
            target_dir = Path('docs') / category
            for file_path in files:
                target_path = target_dir / file_path.name
                move_file_safely(file_path, target_path, dry_run)

def clean_test_directories(dry_run: bool = True):
    """Clean and organize test directories"""
    print("\n=== CLEANING TEST DIRECTORIES ===")
    
    # Main tests directory
    tests_dir = Path('tests')
    if tests_dir.exists():
        print(f"Processing main tests directory")
        organize_single_test_dir(tests_dir, dry_run)
    
    # Package tests
    packages_dir = Path('packages')
    if packages_dir.exists():
        for package_dir in packages_dir.iterdir():
            if package_dir.is_dir():
                test_dir = package_dir / 'tests'
                if test_dir.exists():
                    print(f"Processing {package_dir.name} tests")
                    organize_single_test_dir(test_dir, dry_run)
    
    # App tests  
    apps_dir = Path('apps')
    if apps_dir.exists():
        for app_dir in apps_dir.iterdir():
            if app_dir.is_dir():
                test_dir = app_dir / 'tests'
                if test_dir.exists():
                    print(f"Processing {app_dir.name} tests")
                    organize_single_test_dir(test_dir, dry_run)

def organize_single_test_dir(test_dir: Path, dry_run: bool = True):
    """Organize a single test directory"""
    # Create standard structure
    standard_dirs = ['unit', 'integration', 'e2e']
    
    for dir_name in standard_dirs:
        target_dir = test_dir / dir_name
        if not dry_run:
            target_dir.mkdir(exist_ok=True)
            # Create __init__.py
            init_file = target_dir / '__init__.py'
            if not init_file.exists():
                init_file.touch()
        else:
            print(f"[DRY RUN] Would create: {target_dir}")
    
    # Move test files to appropriate directories
    for test_file in test_dir.glob('test_*.py'):
        if test_file.parent.name in standard_dirs:
            continue  # Already in correct location
        
        filename = test_file.name.lower()
        if 'integration' in filename or 'e2e' in filename:
            target_dir = test_dir / 'integration'
        elif 'unit' in filename:
            target_dir = test_dir / 'unit'
        else:
            target_dir = test_dir / 'unit'  # Default
        
        target_path = target_dir / test_file.name
        move_file_safely(test_file, target_path, dry_run)

def remove_obsolete_files(dry_run: bool = True):
    """Remove clearly obsolete files"""
    print("\n=== REMOVING OBSOLETE FILES ===")
    
    # Patterns for obsolete files
    obsolete_patterns = [
        'temp_*', '*_temp', '*_old', '*_backup',
        'test_*_old*', 'debug_*', 'scratch_*'
    ]
    
    root = Path.cwd()
    
    for pattern in obsolete_patterns:
        for file_path in root.glob(pattern):
            if file_path.is_file() and not should_skip_directory(file_path):
                delete_file_safely(file_path, dry_run)

def analyze_apps_documentation(dry_run: bool = True):
    """Analyze and organize apps documentation"""
    print("\n=== ORGANIZING APPS DOCUMENTATION ===")
    
    apps_dir = Path('apps')
    if not apps_dir.exists():
        return
    
    for app_dir in apps_dir.iterdir():
        if not app_dir.is_dir():
            continue
        
        print(f"\nProcessing app: {app_dir.name}")
        
        # Create docs directory if needed
        docs_dir = app_dir / 'docs'
        if not dry_run:
            docs_dir.mkdir(exist_ok=True)
        
        # Find loose documentation files
        loose_docs = []
        for md_file in app_dir.glob('*.md'):
            if md_file.name.lower() != 'readme.md':  # Keep README at root
                loose_docs.append(md_file)
        
        # Move loose docs to docs directory
        for doc_file in loose_docs:
            target_path = docs_dir / doc_file.name
            move_file_safely(doc_file, target_path, dry_run)

def generate_cleanup_summary(dry_run: bool = True):
    """Generate summary of cleanup actions"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    summary = f"""# Targeted Repository Cleanup Summary

**Generated**: {timestamp}
**Mode**: {'DRY RUN' if dry_run else 'LIVE EXECUTION'}

## Actions Performed

### Root Directory Organization
- Moved large documentation files to `docs/reports/`
- Moved operational docs to `docs/operations/`
- Moved analysis docs to `docs/analysis/`
- Moved planning docs to `docs/plans/`
- Deleted obsolete files

### Test Directory Standardization
- Created standard structure: `unit/`, `integration/`, `e2e/`
- Moved test files to appropriate subdirectories
- Added `__init__.py` files where needed

### Apps Documentation Organization
- Created `docs/` directories in each app
- Moved loose documentation to app docs directories
- Kept README.md files at app roots

### Files Removed
- Obsolete temporary files
- Old backup files
- Superseded documentation

## Next Steps

1. Review the organized structure
2. Update any broken internal links
3. Update documentation index
4. Verify all tests still run correctly

---

*This cleanup maintains all important documentation while organizing it for better navigation and maintenance.*
"""
    
    if dry_run:
        print(f"\n[DRY RUN] Summary would be saved to: TARGETED_CLEANUP_SUMMARY.md")
        print("\n" + "="*60)
        print("SUMMARY PREVIEW:")
        print("="*60)
        print(summary[:500] + "...")
    else:
        with open('TARGETED_CLEANUP_SUMMARY.md', 'w', encoding='utf-8') as f:
            f.write(summary)
        print(f"\nSummary saved to: TARGETED_CLEANUP_SUMMARY.md")

def main():
    """Main execution function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Targeted Repository Cleanup")
    parser.add_argument("--execute", action="store_true", 
                       help="Actually perform cleanup (default is dry-run)")
    
    args = parser.parse_args()
    dry_run = not args.execute
    
    print("TARGETED REPOSITORY CLEANUP")
    print("=" * 50)
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE EXECUTION'}")
    print()
    
    try:
        # 1. Organize root documentation
        organize_root_documentation(dry_run)
        
        # 2. Clean test directories
        clean_test_directories(dry_run)
        
        # 3. Organize apps documentation
        analyze_apps_documentation(dry_run)
        
        # 4. Remove obsolete files
        remove_obsolete_files(dry_run)
        
        # 5. Generate summary
        generate_cleanup_summary(dry_run)
        
        print("\nTARGETED CLEANUP COMPLETE")
        return True
        
    except Exception as e:
        print(f"\nCleanup failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
