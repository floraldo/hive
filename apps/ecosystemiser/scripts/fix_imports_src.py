from hive_logging import get_logger

logger = get_logger(__name__)
#!/usr/bin/env python3
"""
Fix all imports in the src/EcoSystemiser package to use absolute imports.
This script updates imports after restructuring to the src layout.
"""

import os
import re
from pathlib import Path

def fix_imports_in_file(file_path):
    """Fix imports in a single Python file."""
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Define import replacements for common patterns
    replacements = [
        # Fix imports from root modules
        (r'^from errors import', 'from EcoSystemiser.errors import'),
        (r'^from settings import', 'from EcoSystemiser.settings import'),
        (r'^from observability import', 'from EcoSystemiser.observability import'),
        (r'^from worker import', 'from EcoSystemiser.worker import'),
        (r'^from main import', 'from EcoSystemiser.main import'),
        (r'^from cli import', 'from EcoSystemiser.cli import'),
        
        # Fix imports from subdirectories (when not using relative imports)
        (r'^from profile_loader\.', 'from EcoSystemiser.profile_loader.'),
        (r'^from analyser\.', 'from EcoSystemiser.analyser.'),
        (r'^from solver\.', 'from EcoSystemiser.solver.'),
        (r'^from reporting\.', 'from EcoSystemiser.reporting.'),
        (r'^from services\.', 'from EcoSystemiser.services.'),
        
        # Fix import statements (not from imports)
        (r'^import errors$', 'import EcoSystemiser.errors as errors'),
        (r'^import settings$', 'import EcoSystemiser.settings as settings'),
        (r'^import observability$', 'import EcoSystemiser.observability as observability'),
    ]
    
    # Apply replacements line by line
    lines = content.split('\n')
    new_lines = []
    for line in lines:
        new_line = line
        for pattern, replacement in replacements:
            new_line = re.sub(pattern, replacement, new_line)
        new_lines.append(new_line)
    
    content = '\n'.join(new_lines)
    
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def main():
    """Fix imports in all Python files in src/EcoSystemiser."""
    
    src_dir = Path(__file__).parent / "src" / "EcoSystemiser"
    
    if not src_dir.exists():
        logger.error(f"Error: Directory {src_dir} does not exist!")
        return
    
    fixed_files = []
    
    # Walk through all Python files in src/EcoSystemiser
    for root, dirs, files in os.walk(src_dir):
        # Skip __pycache__ directories
        dirs[:] = [d for d in dirs if d != '__pycache__']
        
        for file in files:
            if file.endswith('.py'):
                file_path = Path(root) / file
                if fix_imports_in_file(file_path):
                    relative_path = file_path.relative_to(src_dir)
                    fixed_files.append(str(relative_path))
                    logger.info(f"Fixed: {relative_path}")
    
    logger.info(f"\nFixed {len(fixed_files)} files")
    
    if fixed_files:
        logger.info("\nFiles modified:")
        for f in sorted(fixed_files):
            logger.info(f"  - {f}")

if __name__ == "__main__":
    main()