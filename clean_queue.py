#!/usr/bin/env python3
import json
from pathlib import Path

# Clean the queue
idx = Path('hive/tasks/index.json')
data = json.loads(idx.read_text())
orig = len(data['queue'])
data['queue'] = [t for t in data['queue'] if not t.startswith('fix_')]
clean = len(data['queue'])
idx.write_text(json.dumps(data, indent=2))

# Move fix_* files to trash
tasks_dir = Path('hive/tasks')
trash_dir = tasks_dir / '_trash'
trash_dir.mkdir(exist_ok=True)

moved = 0
for fix_file in tasks_dir.glob('fix_*.json'):
    fix_file.rename(trash_dir / fix_file.name)
    moved += 1

print(f"Queue cleaned: {orig} → {clean} tasks")
print(f"Moved {moved} fix_* files to _trash/")
print("Clean queue ready for second flight!")