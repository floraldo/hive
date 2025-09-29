#!/usr/bin/env python3
"""
Fix all obvious syntax errors from bulk automation
"""
import re
from pathlib import Path

def fix_missing_commas_in_dict(content):
    """Fix missing commas in dictionary definitions"""
    # Pattern to match lines that should have commas but don't
    # Look for: "key": value followed by newline and "key": value
    pattern = r'("[\w_]+": [^,\n]+)\n(\s+")([^}])'
    replacement = r'\1,\n\2\3'
    content = re.sub(pattern, replacement, content)
    return content

def fix_missing_commas_in_function_params(content):
    """Fix missing commas in function parameters"""
    # Look for function definitions with missing commas
    lines = content.split('\n')
    in_function_def = False
    function_lines = []
    result_lines = []
    
    for line in lines:
        if re.match(r'\s*(async\s+)?def\s+\w+\s*\(', line):
            in_function_def = True
            function_lines = [line]
        elif in_function_def:
            function_lines.append(line)
            if ')' in line and ':' in line:
                # End of function definition
                in_function_def = False
                # Fix the function definition
                fixed_func = fix_function_definition('\n'.join(function_lines))
                result_lines.extend(fixed_func.split('\n'))
                function_lines = []
        else:
            if not in_function_def:
                result_lines.append(line)
    
    return '\n'.join(result_lines)

def fix_function_definition(func_def):
    """Fix a single function definition"""
    # Simple approach: add commas after parameters that don't have them
    lines = func_def.split('\n')
    fixed_lines = []
    
    for i, line in enumerate(lines):
        # If this line has a parameter and the next line also has a parameter
        # but this line doesn't end with comma, add one
        if (':' in line and 
            i < len(lines) - 1 and 
            not line.strip().endswith(',') and 
            not line.strip().endswith('(') and
            not ')' in line and
            (lines[i+1].strip().startswith(('*', 'self', 'cls')) or ':' in lines[i+1])):
            line = line.rstrip() + ','
        fixed_lines.append(line)
    
    return '\n'.join(fixed_lines)

def fix_file(file_path):
    """Fix syntax errors in a single file"""
    try:
        content = file_path.read_text(encoding='utf-8')
        original_content = content
        
        # Apply fixes
        content = fix_missing_commas_in_dict(content)
        content = fix_missing_commas_in_function_params(content)
        
        # Try to compile to check for basic syntax errors
        try:
            compile(content, str(file_path), 'exec')
            if content != original_content:
                file_path.write_text(content, encoding='utf-8')
                return True
        except SyntaxError as e:
            print(f"Still has syntax error in {file_path}: {e}")
            return False
            
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False
    
    return False

def main():
    """Fix syntax errors in all Python files"""
    project_root = Path('.')
    
    # Focus on the files we know have issues
    problem_files = [
        "packages/hive-async/src/hive_async/advanced_timeout.py",
        "packages/hive-errors/src/hive_errors/recovery.py",
        "apps/ecosystemiser/tests/integration/test_architectural_improvements.py"
    ]
    
    fixed_count = 0
    
    for file_path_str in problem_files:
        file_path = project_root / file_path_str
        if file_path.exists():
            if fix_file(file_path):
                print(f"Fixed: {file_path}")
                fixed_count += 1
        else:
            print(f"Not found: {file_path}")
    
    print(f"\nFixed {fixed_count} files")

if __name__ == "__main__":
    main()
