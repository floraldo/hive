
def validate_test_coverage_mapping(project_root: Path) -> Tuple[bool, List[str]]:
    """
    Golden Rule 17: Test-to-Source File Mapping

    Enforces 1:1 mapping between source files and unit test files to ensure
    comprehensive test coverage and maintainability.

    Rules:
    1. Every .py file in src/ should have a corresponding test file
    2. Test files should follow naming convention: test_<module_name>.py
    3. Test files should be in tests/unit/ directory relative to package
    4. Core modules must have unit tests (integration tests are separate)

    Args:
        project_root: Root directory of the project

    Returns:
        Tuple of (all_passed, violations_list)
    """
    violations = []

    # Find all packages with source code
    packages_dir = project_root / "packages"
    if not packages_dir.exists():
        return True, []  # No packages to validate

    for package_dir in packages_dir.iterdir():
        if not package_dir.is_dir() or package_dir.name.startswith('.'):
            continue

        # Find src directory
        src_dir = package_dir / "src"
        if not src_dir.exists():
            continue

        # Find tests directory
        tests_dir = package_dir / "tests"
        unit_tests_dir = tests_dir / "unit" if tests_dir.exists() else None

        # Collect all Python source files
        source_files = []
        for py_file in src_dir.rglob("*.py"):
            # Skip __init__.py files and __pycache__
            if py_file.name == "__init__.py" or "__pycache__" in str(py_file):
                continue

            # Get relative path from src directory
            rel_path = py_file.relative_to(src_dir)
            source_files.append(rel_path)

        # Check for corresponding test files
        for src_file in source_files:
            package_name = package_dir.name

            # Convert source file path to expected test file path
            # e.g., hive_config/loader.py -> test_loader.py
            module_parts = src_file.with_suffix('').parts
            if len(module_parts) > 1:
                # Skip package namespace files for now (complex mapping)
                test_file_name = f"test_{'_'.join(module_parts[1:])}.py"
            else:
                test_file_name = f"test_{module_parts[0]}.py"

            # Check if test file exists
            test_file_found = False

            if unit_tests_dir and unit_tests_dir.exists():
                expected_test_path = unit_tests_dir / test_file_name
                if expected_test_path.exists():
                    test_file_found = True

            # Also check in tests directory directly (fallback)
            if not test_file_found and tests_dir and tests_dir.exists():
                fallback_test_path = tests_dir / test_file_name
                if fallback_test_path.exists():
                    test_file_found = True

            if not test_file_found:
                violations.append(
                    f"Missing test file for {package_name}:{src_file} - "
                    f"expected {test_file_name} in tests/unit/ or tests/"
                )

    # Also check apps for core modules (optional but recommended)
    apps_dir = project_root / "apps"
    if apps_dir.exists():
        for app_dir in apps_dir.iterdir():
            if not app_dir.is_dir() or app_dir.name.startswith('.'):
                continue

            # Look for core modules that should have tests
            core_dir = app_dir / "src" / app_dir.name / "core"
            if core_dir.exists():
                tests_dir = app_dir / "tests"

                for py_file in core_dir.rglob("*.py"):
                    if py_file.name == "__init__.py" or "__pycache__" in str(py_file):
                        continue

                    # Core modules should have tests (business logic)
                    rel_path = py_file.relative_to(core_dir)
                    test_file_name = f"test_{rel_path.stem}.py"

                    test_exists = False
                    if tests_dir.exists():
                        for test_file in tests_dir.rglob(test_file_name):
                            test_exists = True
                            break

                    if not test_exists:
                        violations.append(
                            f"Missing test for core module {app_dir.name}:core/{rel_path} - "
                            f"core business logic should have unit tests"
                        )

    return len(violations) == 0, violations


def validate_test_file_quality(project_root: Path) -> Tuple[bool, List[str]]:
    """
    Golden Rule 18: Test File Quality Standards

    Ensures test files follow quality standards and actually test the code.

    Rules:
    1. Test files should contain actual test functions (not just imports)
    2. Test classes should follow naming convention TestClassName
    3. Test functions should follow naming convention test_function_name
    4. Test files should import the modules they test

    Args:
        project_root: Root directory of the project

    Returns:
        Tuple of (all_passed, violations_list)
    """
    violations = []

    # Find all test files
    test_files = []
    for test_dir in ["tests", "test"]:
        for root in [project_root / "packages", project_root / "apps"]:
            if root.exists():
                for test_file in root.rglob(f"{test_dir}/**/*.py"):
                    if test_file.name.startswith("test_") and test_file.name.endswith(".py"):
                        test_files.append(test_file)

    for test_file in test_files:
        try:
            with open(test_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Check if file has actual test functions
            has_test_functions = False
            has_test_classes = False

            lines = content.split('\n')
            for line in lines:
                stripped = line.strip()

                # Check for test functions
                if stripped.startswith("def test_"):
                    has_test_functions = True

                # Check for test classes
                if stripped.startswith("class Test") and ":" in stripped:
                    has_test_classes = True

            # Test file should have either test functions or test classes
            if not has_test_functions and not has_test_classes:
                violations.append(
                    f"Test file {test_file.relative_to(project_root)} "
                    f"contains no test functions or test classes"
                )

            # Check for imports (test files should import something)
            if "import " not in content and "from " not in content:
                violations.append(
                    f"Test file {test_file.relative_to(project_root)} "
                    f"contains no import statements"
                )

        except Exception as e:
            violations.append(
                f"Failed to analyze test file {test_file.relative_to(project_root)}: {e}"
            )

    return len(violations) == 0, violations