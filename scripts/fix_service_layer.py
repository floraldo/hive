#!/usr/bin/env python3
"""Fix service layer discipline - Golden Rule 10."""

import ast
import re
from pathlib import Path
from typing import List, Tuple


def identify_business_logic(content: str) -> List[str]:
    """Identify business logic patterns in service files."""
    violations = []

    # Business logic patterns to detect
    business_patterns = [
        r'if\s+.*\s+(and|or)\s+.*:.*\n.*\s+(return|raise)',  # Complex conditionals
        r'calculate_.*\(',  # Calculation methods
        r'validate_.*\(',   # Validation logic
        r'process_.*\(',    # Processing logic
        r'transform_.*\(',  # Transformation logic
        r'for\s+.*\s+in\s+.*:.*\n.*\s+if\s+',  # Complex iterations with conditions
        r'while\s+.*:.*\n.*\s+if\s+',  # While loops with conditions
    ]

    for pattern in business_patterns:
        if re.search(pattern, content, re.MULTILINE):
            violations.append(pattern)

    return violations


def extract_business_logic(service_file: Path) -> Tuple[str, str]:
    """Extract business logic into separate domain module."""
    content = service_file.read_text()

    # Parse the AST to identify methods with business logic
    try:
        tree = ast.parse(content)
    except:
        return content, ""

    business_methods = []
    service_methods = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for method in node.body:
                if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_source = ast.get_source_segment(content, method)

                    # Check if method contains business logic
                    if any(kw in method.name for kw in ['calculate', 'validate', 'process', 'transform', 'determine']):
                        business_methods.append(method_source)
                    else:
                        service_methods.append(method)

    if not business_methods:
        return content, ""

    # Create domain module content
    domain_content = '''"""Domain logic extracted from service layer."""
from typing import Any, Dict, Optional


class DomainLogic:
    """Business logic and domain rules."""

'''

    for method in business_methods:
        domain_content += f"    {method}\n\n"

    # Update service to use domain module
    service_name = service_file.stem.replace('_service', '')

    updated_service = f'''"""Service layer - thin orchestration only."""
from typing import Any, Dict, Optional
from .{service_name}_domain import DomainLogic


class {service_name.title()}Service:
    """Service orchestrator for {service_name}."""

    def __init__(self):
        """Initialize with domain logic."""
        self.domain = DomainLogic()
'''

    # Add delegation methods
    for method in business_methods:
        method_name = re.search(r'def\s+(\w+)', method)
        if method_name:
            name = method_name.group(1)
            updated_service += f'''
    async def {name}(self, *args, **kwargs):
        """Delegate to domain logic."""
        return await self.domain.{name}(*args, **kwargs)
'''

    return updated_service, domain_content


def fix_service_file(file_path: Path) -> bool:
    """Fix service layer violations in a file."""
    try:
        content = file_path.read_text()

        # Check if file has business logic violations
        violations = identify_business_logic(content)
        if not violations:
            return False

        # Extract business logic to domain module
        updated_service, domain_logic = extract_business_logic(file_path)

        if domain_logic:
            # Create domain module file
            domain_file = file_path.parent / f"{file_path.stem.replace('_service', '')}_domain.py"
            domain_file.write_text(domain_logic)

            # Update service file
            file_path.write_text(updated_service)

            print(f"Refactored service layer: {file_path}")
            print(f"Created domain module: {domain_file}")
            return True

        return False

    except Exception as e:
        print(f"Error fixing {file_path}: {e}")
        return False


def main():
    """Fix service layer violations."""
    # Service files with violations from the report
    service_files = [
        'apps/hive-orchestrator/src/hive_orchestrator/core/claude/claude_service.py',
        'apps/hive-orchestrator/src/hive_orchestrator/core/claude/implementation.py',
        'apps/hive-orchestrator/src/hive_orchestrator/core/claude/planner_bridge.py',
        'apps/hive-orchestrator/src/hive_orchestrator/core/monitoring/implementation.py',
        'apps/hive-orchestrator/src/hive_orchestrator/core/monitoring/pipeline_monitor.py',
    ]

    fixed_count = 0

    print("Service Layer Refactoring")
    print("=" * 50)
    print("\nNote: This script identifies service layer violations.")
    print("Manual refactoring is recommended for complex business logic.\n")

    for file_path in service_files:
        path = Path(file_path)
        if path.exists():
            content = path.read_text()
            violations = identify_business_logic(content)

            if violations:
                print(f"\n{file_path}:")
                print(f"  Found {len(violations)} business logic patterns")
                print("  Recommendation: Extract to domain module")

                # Create a simple refactoring suggestion
                service_name = path.stem.replace('_service', '').replace('implementation', 'logic')
                domain_name = f"{service_name}_domain.py"

                print(f"  Suggested structure:")
                print(f"    - {path.name} (thin orchestration)")
                print(f"    - {domain_name} (business logic)")

                fixed_count += 1
        else:
            print(f"File not found: {file_path}")

    print(f"\n{'-' * 50}")
    print(f"Identified {fixed_count} services needing refactoring")
    print("\nTo fix manually:")
    print("1. Create domain modules for business logic")
    print("2. Move calculations, validations, and processing to domain")
    print("3. Keep services as thin orchestration layers")
    print("4. Use dependency injection for domain modules")


if __name__ == "__main__":
    main()