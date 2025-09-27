#!/usr/bin/env python
"""
Test runner for EcoSystemiser package.

This script sets up the correct path for running tests with the src layout.
"""

import sys
import os
from pathlib import Path

# Add src directory to path so EcoSystemiser package can be imported
src_path = Path(__file__).parent / "src"
# Now run pytest
import pytest

if __name__ == "__main__":
    # Run pytest with arguments passed to this script
    # Default to verbose mode and show all output
    args = sys.argv[1:] if len(sys.argv) > 1 else ["tests", "-v", "--tb=short"]
    
    print(f"Running tests from: {Path.cwd()}")
    print(f"Python path includes: {src_path}")
    print(f"Running: pytest {' '.join(args)}")
    print("-" * 60)
    
    exit_code = pytest.main(args)
    sys.exit(exit_code)
