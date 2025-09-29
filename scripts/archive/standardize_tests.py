#!/usr/bin/env python3
"""
Standardize test directory structure across all packages and apps
Creates unit/, integration/, and e2e/ subdirectories and moves tests appropriately
"""

import os
import shutil
from pathlib import Path
from typing import List, Tuple


def get_test_directories() -> List[Path]:
    """Find all test directories in apps and packages"""
    test_dirs = []

    # Check apps
    apps_dir = Path("apps")
    if apps_dir.exists():
        for app in apps_dir.iterdir():
            test_dir = app / "tests"
            if test_dir.exists() and test_dir.is_dir():
                test_dirs.append(test_dir)

    # Check packages
    packages_dir = Path("packages")
    if packages_dir.exists():
        for package in packages_dir.iterdir():
            test_dir = package / "tests"
            if test_dir.exists() and test_dir.is_dir():
                test_dirs.append(test_dir)

    return test_dirs


def classify_test_file(file_path: Path) -> str:
    """
    Classify a test file as unit, integration, or e2e based on its name and content

    Returns: 'unit', 'integration', or 'e2e'
    """
    name = file_path.name.lower()

    # E2E test patterns
    if "e2e" in name or "end_to_end" in name or "end-to-end" in name:
        return "e2e"

    # Integration test patterns
    if "integration" in name or "integr" in name:
        return "integration"

    # Check file content for classification hints
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore").lower()

        # E2E indicators
        if "selenium" in content or "playwright" in content or "browser" in content:
            return "e2e"
        if "end to end" in content or "e2e" in content:
            return "e2e"

        # Integration indicators
        if "database" in content or "api call" in content or "external service" in content:
            return "integration"
        if "integration test" in content:
            return "integration"

        # Check for multiple component imports (likely integration)
        if content.count("from apps.") > 2 or content.count("from packages.") > 2:
            return "integration"

    except Exception:
        pass  # If we can't read the file, default to unit

    # Default to unit test
    return "unit"


def standardize_test_directory(test_dir: Path) -> Tuple[int, int, int]:
    """
    Standardize a single test directory
    Returns: (unit_count, integration_count, e2e_count)
    """
    print(f"\nProcessing: {test_dir}")

    # Create subdirectories
    unit_dir = test_dir / "unit"
    integration_dir = test_dir / "integration"
    e2e_dir = test_dir / "e2e"

    unit_dir.mkdir(exist_ok=True)
    integration_dir.mkdir(exist_ok=True)
    e2e_dir.mkdir(exist_ok=True)

    # Create __init__.py files
    (unit_dir / "__init__.py").touch()
    (integration_dir / "__init__.py").touch()
    (e2e_dir / "__init__.py").touch()

    # Track counts
    unit_count = 0
    integration_count = 0
    e2e_count = 0

    # Process test files
    test_files = [f for f in test_dir.glob("test_*.py") if f.is_file()]
    test_files.extend([f for f in test_dir.glob("*_test.py") if f.is_file()])

    for test_file in test_files:
        # Skip if already in a subdirectory
        if test_file.parent != test_dir:
            continue

        # Classify the test
        category = classify_test_file(test_file)

        # Determine target directory
        if category == "unit":
            target_dir = unit_dir
            unit_count += 1
        elif category == "integration":
            target_dir = integration_dir
            integration_count += 1
        else:  # e2e
            target_dir = e2e_dir
            e2e_count += 1

        # Move the file
        target_path = target_dir / test_file.name
        if not target_path.exists():
            print(f"  Moving {test_file.name} -> {category}/")
            shutil.move(str(test_file), str(target_path))
        else:
            print(f"  Skipping {test_file.name} (already exists in {category}/)")

    # Handle conftest.py specially - copy to all subdirectories if it exists
    conftest = test_dir / "conftest.py"
    if conftest.exists():
        for subdir in [unit_dir, integration_dir, e2e_dir]:
            target = subdir / "conftest.py"
            if not target.exists():
                shutil.copy2(str(conftest), str(target))
                print(f"  Copied conftest.py to {subdir.name}/")

    return unit_count, integration_count, e2e_count


def create_test_readme(test_dir: Path):
    """Create a README explaining the test organization"""
    readme_content = """# Test Organization

This test directory follows a standardized structure:

## Directory Structure

- **`unit/`**: Unit tests that test individual functions/classes in isolation
  - Fast execution (<100ms per test)
  - No external dependencies (database, network, file system)
  - Heavy use of mocks and stubs

- **`integration/`**: Integration tests that test multiple components together
  - May use real databases or services
  - Tests component interactions
  - Slower than unit tests but faster than E2E

- **`e2e/`**: End-to-end tests that test complete user workflows
  - Tests the full stack
  - May use browser automation or API clients
  - Slowest but most comprehensive

## Running Tests

```bash
# Run all tests
pytest

# Run only unit tests
pytest unit/

# Run only integration tests
pytest integration/

# Run only E2E tests
pytest e2e/

# Run with coverage
pytest --cov=. --cov-report=html
```

## Test Naming Convention

- Test files: `test_<module>.py` or `<module>_test.py`
- Test classes: `Test<Feature>`
- Test methods: `test_<what_it_tests>`

## Adding New Tests

1. Determine the appropriate category (unit/integration/e2e)
2. Create your test file in the correct subdirectory
3. Follow existing patterns and conventions
4. Ensure tests are independent and reproducible
"""

    readme_path = test_dir / "README.md"
    if not readme_path.exists():
        readme_path.write_text(readme_content)
        print(f"  Created README.md")


def main():
    """Main execution"""
    print("=" * 60)
    print("TEST DIRECTORY STANDARDIZATION")
    print("=" * 60)

    # Get all test directories
    test_dirs = get_test_directories()
    print(f"\nFound {len(test_dirs)} test directories to process")

    # Track overall statistics
    total_unit = 0
    total_integration = 0
    total_e2e = 0

    # Process each directory
    for test_dir in sorted(test_dirs):
        unit, integ, e2e = standardize_test_directory(test_dir)
        create_test_readme(test_dir)

        total_unit += unit
        total_integration += integ
        total_e2e += e2e

        print(f"  Summary: {unit} unit, {integ} integration, {e2e} e2e tests")

    # Print summary
    print("\n" + "=" * 60)
    print("STANDARDIZATION COMPLETE")
    print("=" * 60)
    print(f"Total test files organized:")
    print(f"  Unit tests:        {total_unit}")
    print(f"  Integration tests: {total_integration}")
    print(f"  E2E tests:         {total_e2e}")
    print(f"  Total:             {total_unit + total_integration + total_e2e}")
    print("\nAll test directories now follow the standard structure!")


if __name__ == "__main__":
    main()
