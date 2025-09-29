#!/usr/bin/env python3
"""Fix missing commas in ai-planner agent.py"""

import re

file_path = "apps/ai-planner/src/ai_planner/agent.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Pattern 1: Fix lines ending with ] or ) or } or " followed by a line starting with identifier=
# This catches function call arguments and dict entries
pattern1 = r'(\]|\)|")\n(\s+)([a-zA-Z_][a-zA-Z0-9_]*=)'
replacement1 = r"\1,\n\2\3"

# Pattern 2: Fix task["id"] followed by newline and then identifier=
pattern2 = r'(task\["id"\])\n(\s+)([a-zA-Z_][a-zA-Z0-9_]*=)'
replacement2 = r"\1,\n\2\3"

# Pattern 3: Fix lines with "key": value without comma before next "key":
pattern3 = r'("[\w_]+": [^\n,]+)\n(\s+)("[\w_]+")'
replacement3 = r"\1,\n\2\3"

# Apply fixes
content = re.sub(pattern1, replacement1, content)
content = re.sub(pattern2, replacement2, content)
content = re.sub(pattern3, replacement3, content)

# Write back
with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print(f"Fixed commas in {file_path}")
