#!/usr/bin/env python3
"""
Windows Subprocess Test Script
Test script to identify the root cause of subprocess.poll() returning None on Windows
"""

import subprocess
import sys
import time
import os

def test_subprocess_behavior():
    """Test Windows subprocess behavior with different configurations"""

    print("=== Windows Subprocess Diagnostic Test ===")
    print(f"Platform: {sys.platform}")
    print(f"Python version: {sys.version}")
    print()

    # Test 1: Simple echo command with pipes
    print("Test 1: Simple echo command with stdout/stderr pipes")
    try:
        process = subprocess.Popen(
            ["echo", "Hello World"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        print(f"Process PID: {process.pid}")
        print(f"Initial poll(): {process.poll()}")

        # Wait and check poll multiple times
        for i in range(5):
            time.sleep(0.5)
            poll_result = process.poll()
            print(f"Poll after {i*0.5}s: {poll_result}")
            if poll_result is not None:
                break

        # Force wait
        final_code = process.wait()
        print(f"Final exit code: {final_code}")
        print()

    except Exception as e:
        print(f"Test 1 failed: {e}")
        print()

    # Test 2: Long-running command (ping)
    print("Test 2: Long-running command (ping -n 3)")
    try:
        process = subprocess.Popen(
            ["ping", "-n", "3", "127.0.0.1"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        print(f"Process PID: {process.pid}")

        # Monitor for 5 seconds
        start_time = time.time()
        while time.time() - start_time < 5:
            poll_result = process.poll()
            elapsed = time.time() - start_time
            print(f"Poll after {elapsed:.1f}s: {poll_result}")

            if poll_result is not None:
                print(f"Process finished with exit code: {poll_result}")
                break
            time.sleep(0.5)

        # Clean up if still running
        if process.poll() is None:
            print("Process still running, terminating...")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

        print()

    except Exception as e:
        print(f"Test 2 failed: {e}")
        print()

    # Test 3: Non-existent command
    print("Test 3: Non-existent command")
    try:
        process = subprocess.Popen(
            ["non-existent-command"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        print(f"Process PID: {process.pid}")
        time.sleep(1)
        poll_result = process.poll()
        print(f"Poll result: {poll_result}")

    except FileNotFoundError as e:
        print(f"Expected FileNotFoundError: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    print()

    # Test 4: Claude-like command structure
    print("Test 4: Simulating Claude command structure")
    claude_cmd = os.path.expanduser("~/.npm-global/claude.CMD")
    if os.path.exists(claude_cmd):
        try:
            # Simulate the exact command structure used by worker
            cmd = [
                claude_cmd,
                "--help"  # Safe command that should exit quickly
            ]

            print(f"Testing command: {' '.join(cmd)}")

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True
            )

            print(f"Process PID: {process.pid}")

            # Monitor like the worker does
            for i in range(10):
                poll_result = process.poll()
                print(f"Poll iteration {i}: {poll_result}")

                if poll_result is not None:
                    print(f"Process finished with exit code: {poll_result}")
                    break

                time.sleep(0.5)

            # If still running, wait with timeout
            if process.poll() is None:
                try:
                    exit_code = process.wait(timeout=10)
                    print(f"Final exit code after wait(): {exit_code}")
                except subprocess.TimeoutExpired:
                    print("Process timed out, killing...")
                    process.kill()

        except Exception as e:
            print(f"Claude test failed: {e}")
    else:
        print(f"Claude command not found at: {claude_cmd}")

    print("\n=== Test Complete ===")

if __name__ == "__main__":
    test_subprocess_behavior()