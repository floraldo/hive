#!/usr/bin/env python3
"""Final comprehensive fix for agent.py - adds ALL missing commas"""
import re
from pathlib import Path

def fix_all_commas():
    file_path = Path(__file__).parent.parent / 'apps/ai-planner/src/ai_planner/agent.py'

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Fix pattern: line ends with value/call/bracket but next line starts with keyword arg or dict key
    # Without comma and without being inside a comment or string

    lines = content.split('\n')
    fixed_lines = []
    fixes = 0

    for i, line in enumerate(lines):
        fixed_line = line

        # Skip if we're at the last line
        if i >= len(lines) - 1:
            fixed_lines.append(fixed_line)
            continue

        next_line = lines[i + 1]

        # Skip if line is a comment or empty
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            fixed_lines.append(fixed_line)
            continue

        # Check if we need a comma
        needs_comma = False

        # Pattern 1: line ends with ] or ) or " or value, next line starts with keyword=
        if (not line.rstrip().endswith(',') and
            not line.rstrip().endswith('(') and
            not line.rstrip().endswith('{') and
            not line.rstrip().endswith('[') and
            (line.rstrip().endswith(']') or
             line.rstrip().endswith(')') or
             line.rstrip().endswith('"') or
             line.rstrip().endswith("'") or
             re.search(r'\w+$', line.rstrip())) and
            re.match(r'\s+\w+=', next_line)):
            needs_comma = True

        # Pattern 2: line has "key": value, next line starts with "key":
        if (not line.rstrip().endswith(',') and
            '":' in line and
            not line.rstrip().endswith('{') and
            re.match(r'\s+"[\w_]+":', next_line)):
            needs_comma = True

        # Pattern 3: line ends with task["something"], next line starts with keyword=
        if (not line.rstrip().endswith(',') and
            re.search(r'\w+\["[\w_]+"\]$', line.rstrip()) and
            re.match(r'\s+\w+=', next_line)):
            needs_comma = True

        # Pattern 4: line ends with sub_task["something"], next line has another dict key or }
        if (not line.rstrip().endswith(',') and
            re.search(r'sub_task\["[\w_]+"\]$', line.rstrip()) and
            (re.match(r'\s+"[\w_]+":', next_line) or re.match(r'\s+}', next_line))):
            needs_comma = True

        if needs_comma:
            fixed_line = line.rstrip() + ','
            fixes += 1

        fixed_lines.append(fixed_line)

    # Write back
    new_content = '\n'.join(fixed_lines)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"Fixed {fixes} missing commas")
    return fixes

if __name__ == '__main__':
    fix_all_commas()