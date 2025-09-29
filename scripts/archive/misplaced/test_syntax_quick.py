#!/usr/bin/env python3
"""Quick syntax test - just try to run pytest --collect-only to see remaining syntax errors"""

import subprocess
import sys
import os


def main():
    os.chdir("C:/git/hive/apps/ecosystemiser")

    try:
        # Run pytest in collection mode only to find syntax errors
        result = subprocess.run(
            ["python", "-m", "pytest", "--collect-only", "-q", "tests/"], capture_output=True, text=True, timeout=30
        )

        print("STDOUT:")
        print(result.stdout)
        print("\nSTDERR:")
        print(result.stderr)
        print(f"\nReturn code: {result.returncode}")

        if result.returncode == 0:
            print("\n✅ All syntax errors fixed - pytest collection successful!")
        else:
            print("\n❌ Syntax errors remain - pytest collection failed")

    except subprocess.TimeoutExpired:
        print("⏰ Pytest collection timed out")
    except Exception as e:
        print(f"❌ Error running pytest: {e}")


if __name__ == "__main__":
    main()
