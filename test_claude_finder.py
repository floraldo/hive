#!/usr/bin/env python3
from cc_worker import CCWorker
import shutil
import os

print("Testing claude command discovery...")
w = CCWorker('test')
claude_path = w.find_claude_command()
print(f"Found claude at: {claude_path}")

print("\nTesting Windows-specific search...")
if os.name == "nt":
    for name in ("claude.cmd", "claude.bat", "claude.exe", "claude.ps1"):
        path = shutil.which(name)
        if path:
            print(f"Found {name}: {path}")