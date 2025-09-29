"""
Automated Migration to ResilientHttpClient

Scans codebase for legacy requests.get/post/etc calls and automatically
refactors them to use the new ResilientHttpClient with circuit breaker protection.

Part of PROJECT VANGUARD - Autonomous Platform Intelligence
"""

import ast
import sys
from pathlib import Path

from hive_logging import get_logger

logger = get_logger(__name__)


class HttpCallMigrator(ast.NodeTransformer):
    """AST transformer to migrate requests calls to ResilientHttpClient."""

    def __init__(self):
        self.changes_made = False
        self.needs_import = False
        self.needs_error_handling = False

    def visit_Import(self, node):
        """Track if requests is imported."""
        for alias in node.names:
            if alias.name == "requests":
                # Keep the import for now (might be used elsewhere)
                pass
        return node

    def visit_Call(self, node):
        """Transform requests.get/post/etc calls."""
        self.generic_visit(node)

        # Check if this is a requests.METHOD() call
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                if node.func.value.id == "requests" and node.func.attr in ["get", "post", "put", "delete", "patch"]:
                    # This is a requests call - mark for transformation
                    self.changes_made = True
                    self.needs_import = True
                    self.needs_error_handling = True

                    # Transform: requests.get(...) → client.get(...)
                    new_call = ast.Call(
                        func=ast.Attribute(
                            value=ast.Name(id="http_client", ctx=ast.Load()), attr=node.func.attr, ctx=ast.Load(),
                        ),
                        args=node.args,
                        keywords=node.keywords,
                    )

                    return ast.copy_location(new_call, node)

        return node


def analyze_file(file_path: Path) -> tuple[bool, int]:
    """
    Analyze a file for requests usage.

    Returns:
        (has_requests_calls, call_count)
    """
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content)

        call_count = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name):
                        if node.func.value.id == "requests" and node.func.attr in [
                            "get",
                            "post",
                            "put",
                            "delete",
                            "patch",
                        ]:
                            call_count += 1

        return call_count > 0, call_count

    except Exception as e:
        logger.warning(f"Could not analyze {file_path}: {e}")
        return False, 0


def migrate_file(file_path: Path, dry_run: bool = True) -> bool:
    """
    Migrate a single file to use ResilientHttpClient.

    Args:
        file_path: Path to file to migrate
        dry_run: If True, only show what would be changed

    Returns:
        True if changes were made
    """
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content)

        # Apply transformations
        migrator = HttpCallMigrator()
        new_tree = migrator.visit(tree)

        if not migrator.changes_made:
            return False

        if dry_run:
            logger.info(f"Would migrate: {file_path}")
            return True

        # Generate new code
        new_code = ast.unparse(new_tree)

        # Add necessary imports at the top
        imports_to_add = []
        if migrator.needs_import:
            imports_to_add.append("from hive_async import get_resilient_http_client")
        if migrator.needs_error_handling:
            imports_to_add.append("from hive_errors import CircuitBreakerOpenError")

        # Add client initialization
        client_init = "\n# Initialize resilient HTTP client\nhttp_client = get_resilient_http_client()\n"

        # Find insertion point (after imports)
        lines = new_code.split("\n")
        import_end = 0
        for i, line in enumerate(lines):
            if line.startswith("import ") or line.startswith("from "):
                import_end = i + 1

        # Insert new imports
        for imp in reversed(imports_to_add):
            lines.insert(import_end, imp)

        # Insert client initialization (after imports, before first function)
        first_func = import_end
        for i in range(import_end, len(lines)):
            if lines[i].startswith("def ") or lines[i].startswith("class "):
                first_func = i
                break

        lines.insert(first_func, client_init)

        new_code = "\n".join(lines)

        # Write back
        file_path.write_text(new_code, encoding="utf-8")
        logger.info(f"✅ Migrated: {file_path}")
        return True

    except Exception as e:
        logger.error(f"Error migrating {file_path}: {e}")
        return False


def scan_codebase(root_dir: Path, exclude_patterns: list[str] = None) -> list[Path]:
    """
    Scan codebase for files needing migration.

    Args:
        root_dir: Root directory to scan
        exclude_patterns: Patterns to exclude (e.g., 'tests/', 'archive/')

    Returns:
        List of file paths needing migration
    """
    exclude_patterns = exclude_patterns or ["tests/", "archive/", "docs/", ".venv/", "venv/"]

    files_to_migrate = []

    for py_file in root_dir.rglob("*.py"):
        # Check exclusions
        if any(pattern in str(py_file) for pattern in exclude_patterns):
            continue

        has_requests, call_count = analyze_file(py_file)
        if has_requests:
            files_to_migrate.append((py_file, call_count))
            logger.info(f"Found {call_count} requests calls in: {py_file}")

    return files_to_migrate


def generate_migration_report(files: list[tuple[Path, int]]) -> str:
    """Generate detailed migration report."""
    total_files = len(files)
    total_calls = sum(count for _, count in files)

    lines = [
        "=== ResilientHttpClient Migration Report ===",
        f"Total Files: {total_files}",
        f"Total HTTP Calls: {total_calls}",
        "",
        "Files to Migrate:",
    ]

    for file_path, call_count in sorted(files, key=lambda x: x[1], reverse=True):
        lines.append(f"  • {file_path.name} ({call_count} calls) - {file_path}")

    lines.extend(
        [
            "",
            "Migration Benefits:",
            "  ✅ Circuit breaker protection per domain",
            "  ✅ Automatic retry with exponential backoff",
            "  ✅ Request/failure statistics",
            "  ✅ Graceful degradation on service failures",
            "",
            "Next Steps:",
            "  1. Review migration candidates",
            "  2. Run with --execute to perform migration",
            "  3. Test each migrated service",
            "  4. Monitor circuit breaker statistics",
        ],
    )

    return "\n".join(lines)


def main():
    """Main migration script."""
    import argparse

    parser = argparse.ArgumentParser(description="Migrate requests calls to ResilientHttpClient")
    parser.add_argument(
        "--root", type=Path, default=Path.cwd(), help="Root directory to scan (default: current directory)",
    )
    parser.add_argument(
        "--exclude", nargs="*", default=["tests/", "archive/", "docs/"], help="Patterns to exclude from migration",
    )
    parser.add_argument("--execute", action="store_true", help="Execute migration (default is dry-run)")
    parser.add_argument("--file", type=Path, help="Migrate specific file")
    parser.add_argument("--report", type=Path, help="Save migration report to file")

    args = parser.parse_args()

    if args.file:
        # Migrate single file
        if args.execute:
            success = migrate_file(args.file, dry_run=False)
            if success:
                print(f"✅ Successfully migrated: {args.file}")
            else:
                print(f"❌ No changes needed or migration failed: {args.file}")
        else:
            has_requests, call_count = analyze_file(args.file)
            if has_requests:
                print(f"Found {call_count} requests calls in: {args.file}")
                print("Run with --execute to perform migration")
            else:
                print(f"No requests calls found in: {args.file}")
    else:
        # Scan entire codebase
        print(f"Scanning {args.root} for requests usage...")
        files_to_migrate = scan_codebase(args.root, args.exclude)

        if not files_to_migrate:
            print("✅ No files found needing migration")
            return 0

        # Generate report
        report = generate_migration_report(files_to_migrate)
        print("\n" + report)

        if args.report:
            args.report.write_text(report)
            print(f"\n📄 Report saved to: {args.report}")

        if args.execute:
            print("\n🚀 Executing migration...")
            migrated_count = 0
            for file_path, _ in files_to_migrate:
                if migrate_file(file_path, dry_run=False):
                    migrated_count += 1

            print(f"\n✅ Migrated {migrated_count}/{len(files_to_migrate)} files")

            if migrated_count < len(files_to_migrate):
                print("⚠️  Some files could not be migrated - review logs for details")
                return 1
        else:
            print("\n⚠️  DRY RUN - No files were modified")
            print("   Run with --execute to perform actual migration")

    return 0


if __name__ == "__main__":
    sys.exit(main())
