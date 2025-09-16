#!/usr/bin/env python3
"""
Test script to isolate the worker/Claude CLI issue
"""

import subprocess
import sys
import os
from pathlib import Path
import json
import time

def test_direct_worker():
    """Test worker directly (should work)"""
    print("=== TESTING DIRECT WORKER EXECUTION ===")

    # Run worker directly
    cmd = [
        sys.executable,
        "worker.py",
        "backend",
        "--local",
        "--task-id", "simple-hello",
        "--phase", "apply",
        "--mode", "fresh"
    ]

    print(f"Command: {' '.join(cmd)}")
    print(f"CWD: {os.getcwd()}")

    try:
        result = subprocess.run(
            cmd,
            cwd=str(Path(__file__).parent),
            capture_output=True,
            text=True,
            timeout=120
        )

        print(f"Exit code: {result.returncode}")
        print(f"STDOUT:\n{result.stdout}")
        print(f"STDERR:\n{result.stderr}")

        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("TIMEOUT: Worker took longer than 2 minutes")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def test_queen_spawned_worker():
    """Test worker via Queen subprocess (mimics the issue)"""
    print("\n=== TESTING QUEEN-SPAWNED WORKER ===")

    # Spawn worker as subprocess like Queen does
    cmd = [
        sys.executable,
        str(Path(__file__).parent / "worker.py"),
        "backend",
        "--one-shot",
        "--task-id", "simple-hello",
        "--run-id", "test-queen-spawn",
        "--phase", "apply",
        "--mode", "fresh"
    ]

    print(f"Command: {' '.join(cmd)}")

    # Mimic Queen's environment setup
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    try:
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env
        )

        print(f"Spawned process PID: {process.pid}")

        # Monitor the process
        output_lines = []
        start_time = time.time()

        while True:
            line = process.stdout.readline()
            if not line:
                poll_result = process.poll()
                if poll_result is not None:
                    print(f"Process exited with code: {poll_result}")
                    break
                # No output but still running
                if time.time() - start_time > 120:  # 2 minute timeout
                    print("TIMEOUT: Killing process")
                    process.kill()
                    return False
                time.sleep(0.1)
                continue

            output_lines.append(line.rstrip())
            print(f"OUTPUT: {line.rstrip()}")

        print(f"Total output lines: {len(output_lines)}")
        print(f"Final exit code: {process.returncode}")

        return process.returncode == 0

    except Exception as e:
        print(f"ERROR: {e}")
        return False

def test_claude_cli_direct():
    """Test Claude CLI directly to verify it works"""
    print("\n=== TESTING CLAUDE CLI DIRECTLY ===")

    # Find Claude command like worker does
    claude_cmd = None
    possible_paths = [
        Path.home() / ".npm-global" / "claude.CMD",
        Path.home() / ".npm-global" / "bin" / "claude",
        Path("claude.CMD"),
        Path("claude")
    ]

    for path in possible_paths:
        if path.exists():
            claude_cmd = str(path)
            break

    if not claude_cmd:
        print("Claude command not found")
        return False

    print(f"Using Claude: {claude_cmd}")

    # Create test workspace
    workspace = Path(__file__).parent / ".test_workspace"
    workspace.mkdir(exist_ok=True)

    cmd = [
        claude_cmd,
        "--output-format", "stream-json",
        "--verbose",
        "--add-dir", str(workspace),
        "--dangerously-skip-permissions",
        "-p", "Create a file called test.txt with content 'Hello from Claude CLI test'"
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=60
        )

        print(f"Exit code: {result.returncode}")
        print(f"STDOUT length: {len(result.stdout)} chars")
        print(f"STDERR: {result.stderr}")

        # Check if file was created
        test_file = workspace / "test.txt"
        if test_file.exists():
            print(f"SUCCESS: File created with content: {test_file.read_text()}")
            return True
        else:
            print("FAILURE: File not created")
            return False

    except subprocess.TimeoutExpired:
        print("TIMEOUT: Claude CLI took longer than 1 minute")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def main():
    """Run all tests to isolate the issue"""
    print("Starting comprehensive worker/Claude CLI testing...")
    print(f"Python: {sys.executable}")
    print(f"Working directory: {os.getcwd()}")
    print(f"Platform: {sys.platform}")

    results = {}

    # Test 1: Claude CLI directly
    results["claude_direct"] = test_claude_cli_direct()

    # Test 2: Worker directly
    results["worker_direct"] = test_direct_worker()

    # Test 3: Worker via subprocess (Queen simulation)
    results["worker_subprocess"] = test_queen_spawned_worker()

    print("\n=== TEST RESULTS ===")
    for test_name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"{test_name}: {status}")

    # Analysis
    if results["claude_direct"] and results["worker_direct"] and not results["worker_subprocess"]:
        print("\n=== ROOT CAUSE IDENTIFIED ===")
        print("Claude CLI works directly")
        print("Worker works when run directly")
        print("Worker FAILS when spawned as subprocess")
        print("This confirms the issue is in the subprocess spawning chain")

    return all(results.values())

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)