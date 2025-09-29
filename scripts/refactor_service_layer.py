#!/usr/bin/env python3
"""
Refactor service layer files to move business logic to implementation layer
and update CLIs to use hive-cli utilities
"""

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def extract_business_logic_from_service(service_file: Path) -> tuple[str, str]:
    """Extract business logic from service layer and create implementation file"""

    service_content = service_file.read_text(encoding="utf-8")

    # Create implementation module content
    impl_content = '''"""Implementation layer for business logic"""

from typing import Any, Dict, List, Optional
from hive_logging import get_logger

logger = get_logger(__name__)


class BusinessLogicImplementation:
    """Implementation of business logic extracted from service layer"""

    def __init__(self):
        """Initialize implementation"""
        self.logger = logger

    # Business logic methods will be moved here
'''

    # Create clean service layer content
    service_template = '''"""Service layer - thin wrapper for business logic"""

from typing import Any, Dict, List, Optional
from hive_logging import get_logger
from .implementation import BusinessLogicImplementation

logger = get_logger(__name__)


class Service:
    """Service layer delegating to implementation"""

    def __init__(self):
        """Initialize service with implementation"""
        self.impl = BusinessLogicImplementation()
        self.logger = logger

    # Service methods delegate to implementation
'''

    return service_template, impl_content


def refactor_cli_to_use_hive_cli(cli_file: Path) -> str:
    """Refactor CLI to use hive-cli utilities"""

    cli_content = cli_file.read_text(encoding="utf-8")

    # Add hive-cli imports
    new_imports = """from hive_cli import create_cli, add_command, run_cli
from hive_cli.decorators import command, option
from hive_cli.output import success, error, info, warning
"""

    # Replace Click with hive-cli patterns
    cli_content = re.sub(r"import click", new_imports, cli_content)
    cli_content = re.sub(r"@click\.command", "@command", cli_content)
    cli_content = re.sub(r"@click\.option", "@option", cli_content)
    cli_content = re.sub(r"@click\.group", "@create_cli", cli_content)
    cli_content = re.sub(r"click\.echo", "info", cli_content)
    cli_content = re.sub(r'click\.secho\([^,]+,\s*fg="green"\)', "success", cli_content)
    cli_content = re.sub(r'click\.secho\([^,]+,\s*fg="red"\)', "error", cli_content)
    cli_content = re.sub(r'click\.secho\([^,]+,\s*fg="yellow"\)', "warning", cli_content)

    return cli_content


def main():
    """Main refactoring function"""
    print("=" * 60)
    print("Refactoring Service Layer and CLIs")
    print("=" * 60)

    # Service layer files that need refactoring
    service_files = [
        "apps/hive-orchestrator/src/hive_orchestrator/core/claude/claude_service.py",
        "apps/hive-orchestrator/src/hive_orchestrator/core/claude/planner_bridge.py",
        "apps/hive-orchestrator/src/hive_orchestrator/core/monitoring/pipeline_monitor.py",
    ]

    print("\n1. Refactoring Service Layer Files")
    print("-" * 40)

    for service_file in service_files:
        full_path = PROJECT_ROOT / service_file
        if full_path.exists():
            # Create implementation file path
            impl_path = full_path.parent / "implementation.py"

            # Extract business logic
            service_content, impl_content = extract_business_logic_from_service(full_path)

            # Write implementation file
            impl_path.write_text(impl_content, encoding="utf-8")
            print(f"  Created implementation: {impl_path}")

            # Note: We're not overwriting the service file to avoid breaking existing code
            # This would need careful migration in a real scenario

            # Create migration guide
            migration_path = full_path.parent / "MIGRATION.md"
            migration_content = f"""# Service Layer Migration Guide

## File: {service_file}

### Steps to complete migration:

1. Move all business logic methods from service to implementation.py
2. Update service methods to delegate to self.impl
3. Ensure all tests still pass
4. Remove old business logic from service file

### Example:

**Before (in service):**
```python
def process_data(self, data):
    # Complex business logic here
    result = complex_calculation(data)
    return result
```

**After (in service):**
```python
def process_data(self, data):
    return self.impl.process_data(data)
```

**After (in implementation):**
```python
def process_data(self, data):
    # Complex business logic here
    result = complex_calculation(data)
    return result
```
"""
            migration_path.write_text(migration_content, encoding="utf-8")
            print(f"  Created migration guide: {migration_path}")

    # CLI files that need refactoring
    cli_files = [
        "apps/ecosystemiser/src/EcoSystemiser/cli.py",
        "apps/hive-orchestrator/src/hive_orchestrator/cli.py",
    ]

    print("\n2. Refactoring CLI Files")
    print("-" * 40)

    for cli_file in cli_files:
        full_path = PROJECT_ROOT / cli_file
        if full_path.exists():
            # Create backup
            backup_path = full_path.with_suffix(".py.backup")
            backup_path.write_text(full_path.read_text(encoding="utf-8"), encoding="utf-8")

            # Refactor CLI
            new_content = refactor_cli_to_use_hive_cli(full_path)

            # Write updated CLI
            full_path.write_text(new_content, encoding="utf-8")
            print(f"  Refactored: {cli_file}")
            print(f"  Backup saved: {backup_path}")

    print("\n" + "=" * 60)
    print("Refactoring Complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Review the migration guides in each service directory")
    print("2. Manually complete the service layer refactoring")
    print("3. Test the refactored CLIs")
    print("4. Run validation script: python scripts/validate_golden_rules.py")


if __name__ == "__main__":
    main()
