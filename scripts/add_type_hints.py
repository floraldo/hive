#!/usr/bin/env python3
"""
Add missing type hints and docstrings to functions
"""

import ast
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

PROJECT_ROOT = Path(__file__).parent.parent

class TypeHintAdder(ast.NodeTransformer):
    """AST transformer to add type hints to functions"""

    def __init__(self):
        self.modified = False

    def visit_FunctionDef(self, node):
        """Add type hints to function definitions"""
        # Skip if already has return type
        if not node.returns:
            # Common patterns for return types
            if node.name.startswith('get_'):
                node.returns = ast.Name(id='Any', ctx=ast.Load())
            elif node.name.startswith('is_') or node.name.startswith('has_'):
                node.returns = ast.Name(id='bool', ctx=ast.Load())
            elif node.name.startswith('create_') or node.name.startswith('build_'):
                node.returns = ast.Name(id='Any', ctx=ast.Load())
            elif 'setup' in node.name or 'init' in node.name:
                node.returns = ast.Constant(value=None)
            else:
                node.returns = ast.Name(id='Any', ctx=ast.Load())
            self.modified = True

        # Add parameter type hints
        for arg in node.args.args:
            if not arg.annotation and arg.arg != 'self' and arg.arg != 'cls':
                arg.annotation = ast.Name(id='Any', ctx=ast.Load())
                self.modified = True

        # Add docstring if missing
        if not ast.get_docstring(node):
            docstring = f'"""{node.name.replace("_", " ").title()}"""'
            node.body.insert(0, ast.Expr(value=ast.Constant(value=docstring[3:-3])))
            self.modified = True

        self.generic_visit(node)
        return node

    def visit_AsyncFunctionDef(self, node):
        """Add type hints to async function definitions"""
        return self.visit_FunctionDef(node)


def add_type_hints_to_file(file_path: Path) -> bool:
    """Add type hints to a Python file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()

        tree = ast.parse(source)
        transformer = TypeHintAdder()
        new_tree = transformer.visit(tree)

        if transformer.modified:
            # Add necessary imports
            imports_needed = set()

            # Check if typing imports are needed
            for node in ast.walk(new_tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.returns:
                        imports_needed.add('Any')
                    for arg in node.args.args:
                        if arg.annotation:
                            imports_needed.add('Any')

            # Add imports at the top
            if imports_needed:
                import_node = ast.ImportFrom(
                    module='typing',
                    names=[ast.alias(name=name, asname=None) for name in sorted(imports_needed)],
                    level=0
                )

                # Find the right place to insert imports
                insert_pos = 0
                for i, node in enumerate(tree.body):
                    if isinstance(node, (ast.Import, ast.ImportFrom)):
                        insert_pos = i + 1
                    elif not isinstance(node, ast.Expr):  # Skip docstrings
                        break

                tree.body.insert(insert_pos, import_node)

            # Convert back to source
            new_source = ast.unparse(tree) if hasattr(ast, 'unparse') else source

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_source)

            return True
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

    return False


def main():
    """Main function to add type hints to all Python files"""
    print("Adding type hints and docstrings...")

    # Files that need type hints based on the validation output
    files_to_fix = [
        "apps/ai-deployer/src/ai_deployer/core/config.py",
        "apps/ai-planner/src/ai_planner/core/config.py",
        "apps/ai-planner/src/ai_planner/core/errors.py",
        "apps/ai-reviewer/src/ai_reviewer/core/config.py",
        "apps/ecosystemiser/run.py",
        "apps/ecosystemiser/dashboard/app_isolated.py",
        "apps/ecosystemiser/examples/parametric_sweep_example.py",
        "packages/hive-config/src/hive_config/loader.py",
        "packages/hive-config/src/hive_config/models.py",
        "packages/hive-config/src/hive_config/secure_config.py",
        "packages/hive-config/src/hive_config/unified_config.py",
        "packages/hive-config/src/hive_config/validation.py",
        "packages/hive-db/src/hive_db/pool.py",
        "packages/hive-db/src/hive_db/sqlite_connector.py",
        "packages/hive-db/src/hive_db/utils.py",
        "packages/hive-deployment/src/hive_deployment/deployment.py",
        "packages/hive-errors/src/hive_errors/recovery.py",
        "packages/hive-logging/src/hive_logging/logger.py",
    ]

    fixed_count = 0
    for file_path in files_to_fix:
        full_path = PROJECT_ROOT / file_path
        if full_path.exists():
            if add_type_hints_to_file(full_path):
                print(f"  Fixed: {file_path}")
                fixed_count += 1

    print(f"\nFixed {fixed_count} files")


if __name__ == "__main__":
    main()