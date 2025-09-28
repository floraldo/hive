#!/usr/bin/env python
"""
Simple CLI Test Suite for EcoSystemiser
Tests basic CLI functionality
"""

import subprocess
import sys
import shutil
from pathlib import Path
import json

# Configuration
PROJECT_ROOT = Path(__file__).parent
OUTPUT_DIR = PROJECT_ROOT / "cli_test_output"
SRC_DIR = PROJECT_ROOT / "src"

def run_cli_command(args: list[str], description: str = "") -> bool:
    """Run a CLI command and return success status."""
    if description:
        print(f"\n{description}")
    
    cmd = [sys.executable, "-m", "EcoSystemiser.cli"] + args
    
    print(f"Running: {' '.join(args)}")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=SRC_DIR,
            timeout=60
        )
        
        if result.returncode == 0:
            print(f"  [PASS] Success")
            return True
        else:
            print(f"  [FAIL] Failed with code {result.returncode}")
            if result.stderr:
                print(f"  Error: {result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"  [ERROR] Exception: {e}")
        return False

def main():
    """Run CLI tests."""
    print("=" * 50)
    print("EcoSystemiser CLI Test Suite")
    print("=" * 50)
    
    # Setup
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir()
    
    tests = [
        {
            "description": "Test 1: Basic NASA POWER request",
            "args": ["climate", "get", 
                    "--loc", "40.7,-74.0", 
                    "--year", "2023",
                    "--vars", "temp_air",
                    "--source", "nasa_power",
                    "--out", f"../{OUTPUT_DIR.name}/test1.parquet"]
        },
        {
            "description": "Test 2: Request with date range",
            "args": ["climate", "get",
                    "--loc", "51.5,-0.1",
                    "--start", "2023-06-01",
                    "--end", "2023-06-07", 
                    "--source", "nasa_power",
                    "--out", f"../{OUTPUT_DIR.name}/test2.parquet"]
        },
        {
            "description": "Test 3: JSON output",
            "args": ["climate", "get",
                    "--loc", "34.0,-118.2",
                    "--year", "2022",
                    "--source", "nasa_power",
                    "--json-out", f"../{OUTPUT_DIR.name}/test3.json"]
        },
        {
            "description": "Test 4: Statistics",
            "args": ["climate", "get",
                    "--loc", "48.8,2.3",
                    "--year", "2023",
                    "--source", "nasa_power",
                    "--stats",
                    "--out", f"../{OUTPUT_DIR.name}/test4.parquet"]
        }
    ]
    
    results = []
    for test in tests:
        success = run_cli_command(test["args"], test["description"])
        results.append(success)
    
    # Summary
    print("\n" + "=" * 50)
    print("Test Summary")
    print("=" * 50)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    # Check output files
    output_files = list(OUTPUT_DIR.glob("*"))
    if output_files:
        print(f"\nGenerated {len(output_files)} files:")
        for f in output_files:
            size = f.stat().st_size
            print(f"  - {f.name}: {size:,} bytes")
    
    # Cleanup if all passed
    if passed == total:
        print("\nAll tests passed!")
        cleanup = input("Delete test outputs? (y/N): ")
        if cleanup.lower() == 'y':
            shutil.rmtree(OUTPUT_DIR)
            print("Cleaned up test outputs.")
        return 0
    else:
        print(f"\n{total - passed} tests failed. Check output in {OUTPUT_DIR}")
        return 1

if __name__ == "__main__":
    sys.exit(main())