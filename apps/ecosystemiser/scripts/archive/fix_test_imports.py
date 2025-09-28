#!/usr/bin/env python
"""Fix imports in test files to use absolute imports from EcoSystemiser package."""

import re
from pathlib import Path

def fix_test_imports(file_path):
    """Fix imports in a test file."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Remove old sys.path manipulation
    content = re.sub(r'# Use relative imports.*?\n.*?sys\.path\.insert.*?\n', '', content, flags=re.DOTALL)
    content = re.sub(r'# Add parent directory.*?\n.*?sys\.path\.insert.*?\n', '', content, flags=re.DOTALL)
    content = re.sub(r'import sys\n', '', content)
    content = re.sub(r'from pathlib import Path\n', '', content) 
    
    # Fix imports
    replacements = [
        (r'from profile_loader\.', 'from EcoSystemiser.profile_loader.'),
        (r'from errors import', 'from EcoSystemiser.errors import'),
        (r'from shared\.', 'from EcoSystemiser.shared.'),
        (r'import profile_loader\.', 'import EcoSystemiser.profile_loader.'),
    ]
    
    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content)
    
    # Fix specific data_models vs models issue
    content = content.replace(
        'from EcoSystemiser.profile_loader.climate.models import',
        'from EcoSystemiser.profile_loader.climate.data_models import'
    )
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"Fixed imports in {file_path}")

# Fix all test files
test_files = Path('tests').glob('test_*.py')
for test_file in test_files:
    if test_file.name != 'test_adapters.py':  # Already fixed this one
        fix_test_imports(test_file)

print("Import fixing complete!")
