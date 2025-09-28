#!/usr/bin/env python3
"""
Audit dependencies across all pyproject.toml files
Identifies potentially unused dependencies by checking imports
"""

import ast
import re
from pathlib import Path
from typing import Dict, Set, List, Tuple
import toml


def get_all_python_files(directory: Path) -> List[Path]:
    """Get all Python files in a directory recursively"""
    return list(directory.rglob("*.py"))


def extract_imports(file_path: Path) -> Set[str]:
    """Extract all import statements from a Python file"""
    imports = set()

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split('.')[0])
    except:
        # If we can't parse the file, try regex fallback
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            # Match import statements
            import_pattern = r'^\s*(?:from\s+(\S+)|import\s+(\S+))'
            for match in re.finditer(import_pattern, content, re.MULTILINE):
                module = match.group(1) or match.group(2)
                if module:
                    imports.add(module.split('.')[0])
        except:
            pass

    return imports


def normalize_package_name(name: str) -> str:
    """Normalize package names for comparison"""
    # Common mappings
    mappings = {
        'flask_cors': 'flask-cors',
        'flask_login': 'flask-login',
        'anthropic': 'anthropic',
        'dotenv': 'python-dotenv',
        'PIL': 'pillow',
        'cv2': 'opencv-python',
        'sklearn': 'scikit-learn',
        'yaml': 'pyyaml',
        'dateutil': 'python-dateutil',
    }

    # Check if it's a known mapping
    if name in mappings:
        return mappings[name]

    # Convert underscores to hyphens
    return name.replace('_', '-').lower()


def analyze_package_usage(package_dir: Path) -> Tuple[Set[str], Set[str], Dict[str, List[str]]]:
    """
    Analyze a package or app directory for dependency usage

    Returns:
        - declared_deps: Dependencies declared in pyproject.toml
        - used_deps: Dependencies actually imported
        - unused_deps: Dependencies that appear unused
    """
    pyproject_path = package_dir / "pyproject.toml"
    if not pyproject_path.exists():
        return set(), set(), {}

    # Load declared dependencies
    pyproject = toml.load(pyproject_path)
    dependencies = pyproject.get('tool', {}).get('poetry', {}).get('dependencies', {})

    # Filter out Python itself and local packages
    declared_deps = set()
    for dep, version in dependencies.items():
        if dep == 'python':
            continue
        if isinstance(version, dict) and 'path' in version:
            continue  # Skip local packages
        declared_deps.add(dep.lower())

    # Get all Python files
    src_dir = package_dir / "src"
    if not src_dir.exists():
        src_dir = package_dir

    python_files = get_all_python_files(src_dir)

    # Extract all imports
    all_imports = set()
    for py_file in python_files:
        imports = extract_imports(py_file)
        all_imports.update(imports)

    # Normalize import names to package names
    used_deps = set()
    for imp in all_imports:
        normalized = normalize_package_name(imp)
        used_deps.add(normalized)

    # Find potentially unused dependencies
    unused = {}
    for dep in declared_deps:
        # Check if the dependency or any variant is used
        dep_variants = {dep, dep.replace('-', '_'), dep.replace('-', '')}
        if not any(variant in all_imports for variant in dep_variants):
            # Special cases - some packages are used indirectly
            indirect_packages = {
                'pytest-cov', 'pytest-asyncio', 'pytest-flask', 'pytest-mock',
                'black', 'mypy', 'ruff', 'isort',  # Development tools
                'poetry-core',  # Build system
            }
            if dep not in indirect_packages:
                unused[dep] = list(dep_variants)

    return declared_deps, used_deps, unused


def main():
    """Main execution"""
    print("=" * 80)
    print("DEPENDENCY AUDIT REPORT")
    print("=" * 80)

    # Find all packages and apps
    all_dirs = []
    if Path("apps").exists():
        all_dirs.extend([d for d in Path("apps").iterdir() if d.is_dir()])
    if Path("packages").exists():
        all_dirs.extend([d for d in Path("packages").iterdir() if d.is_dir()])

    # Track global statistics
    total_declared = 0
    total_unused = 0
    removal_commands = []

    # Analyze each directory
    for directory in sorted(all_dirs):
        declared, used, unused = analyze_package_usage(directory)

        if declared:
            print(f"\n[Package] {directory.name}")
            print(f"   Declared dependencies: {len(declared)}")

            if unused:
                print(f"   [WARNING] Potentially unused: {len(unused)}")
                for dep in sorted(unused.keys()):
                    print(f"      - {dep}")
                    removal_commands.append(f"cd {directory} && poetry remove {dep}")
                total_unused += len(unused)
            else:
                print(f"   [OK] All dependencies appear to be used")

            total_declared += len(declared)

    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total declared dependencies: {total_declared}")
    print(f"Potentially unused: {total_unused}")
    print(f"Usage efficiency: {((total_declared - total_unused) / total_declared * 100):.1f}%")

    if removal_commands:
        print("\n" + "=" * 80)
        print("SUGGESTED REMOVAL COMMANDS")
        print("=" * 80)
        print("\n# Review these carefully before executing:")
        for cmd in removal_commands:
            print(cmd)

        print("\n# Or remove all at once (REVIEW FIRST!):")
        print("# " + " && ".join(removal_commands))

    print("\n[NOTE] Some dependencies may be used indirectly (e.g., plugins, optional features)")
    print("Review each suggestion carefully before removing!")


if __name__ == "__main__":
    main()