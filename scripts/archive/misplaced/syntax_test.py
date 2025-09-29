#!/usr/bin/env python3
"""Quick syntax test script to verify critical syntax errors are fixed."""

import sys


def test_import(module_name, file_path):
    """Test importing a module and report any syntax errors."""
    try:
        # Try to compile the file first
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        compile(content, file_path, "exec")
        print(f"✓ {module_name}: Syntax OK")
        return True
    except SyntaxError as e:
        print(f"✗ {module_name}: SyntaxError at line {e.lineno}: {e.msg}")
        print(f"  {e.text.strip() if e.text else 'No text available'}")
        return False
    except Exception as e:
        print(f"? {module_name}: Other error: {e}")
        return False


def main():
    """Test syntax of key files."""
    test_files = [
        ("plot_factory.py", "src/ecosystemiser/datavis/plot_factory.py"),
        ("test_architectural_improvements.py", "tests/integration/test_architectural_improvements.py"),
        ("algorithms/base.py", "src/ecosystemiser/discovery/algorithms/base.py"),
        ("core/bus.py", "src/ecosystemiser/core/bus.py"),
        ("heat_buffer.py", "src/ecosystemiser/system_model/components/energy/heat_buffer.py"),
    ]

    all_passed = True
    for name, file_path in test_files:
        full_path = f"C:/git/hive/apps/ecosystemiser/{file_path}"
        success = test_import(name, full_path)
        all_passed = all_passed and success

    if all_passed:
        print("\n🎉 All syntax checks passed!")
        sys.exit(0)
    else:
        print("\n💥 Some syntax errors remain")
        sys.exit(1)


if __name__ == "__main__":
    main()
