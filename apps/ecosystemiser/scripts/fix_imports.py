#!/usr/bin/env python3
"""
Fix import issues in EcoSystemiser modules.

This script fixes the relative import issues that cause ImportError
when running the application from different contexts.
"""

import os
import re
from pathlib import Path

def fix_imports_in_file(file_path):
    """Fix imports in a single file."""
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Define import replacements
    replacements = [
        # Fix triple-dot imports to absolute imports
        (r'from \.\.\.errors import', 'from errors import'),
        (r'from \.\.\.settings import', 'from settings import'),
        (r'from \.\.\.observability import', 'from observability import'),
        
        # Fix quad-dot imports 
        (r'from \.\.\.\.errors import', 'from errors import'),
        (r'from \.\.\.\.settings import', 'from settings import'),
        (r'from \.\.\.\.observability import', 'from observability import'),
        
        # Fix five-dot imports
        (r'from \.\.\.\.\.settings import', 'from settings import'),
        
        # Fix shared module imports
        (r'from \.\.shared\.', 'from profile_loader.shared.'),
        (r'from \.\.\.shared\.', 'from profile_loader.shared.'),
    ]
    
    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content)
    
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def main():
    """Fix imports in all Python files."""
    
    root_dir = Path(__file__).parent
    fixed_files = []
    
    # Files to fix
    files_to_fix = [
        'profile_loader/climate/service.py',
        'profile_loader/climate/api.py',
        'profile_loader/climate/main.py',
        'profile_loader/climate/logging_config.py',
        'profile_loader/climate/adapters/factory.py',
        'profile_loader/climate/adapters/base.py',
        'profile_loader/climate/adapters/meteostat.py',
        'profile_loader/climate/adapters/era5.py',
        'profile_loader/climate/adapters/nasa_power.py',
        'profile_loader/climate/processing/resampling.py',
    ]
    
    for file_path in files_to_fix:
        full_path = root_dir / file_path
        if full_path.exists():
            if fix_imports_in_file(full_path):
                fixed_files.append(file_path)
                print(f"Fixed: {file_path}")
        else:
            print(f"Not found: {file_path}")
    
    print(f"\nFixed {len(fixed_files)} files")
    
    if fixed_files:
        print("\nFiles modified:")
        for f in fixed_files:
            print(f"  - {f}")

if __name__ == "__main__":
    main()