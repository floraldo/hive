"""
Unit tests for Golden Rule 37: Unified Config Enforcement

Tests the AST validation that prevents direct os.getenv() calls and
config file I/O outside of the hive-config package.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from hive_tests.ast_validator import FileContext, GoldenRuleVisitor


@pytest.mark.core
def test_detects_os_getenv():
    """GR37 should catch direct os.getenv() usage"""
    code = '\nimport os\ndb_path = os.getenv("DATABASE_PATH")\n'
    tree = ast.parse(code)
    context = FileContext(path=Path('apps/test-app/src/test_app/main.py'), content=code, ast_tree=tree, lines=code.split('\n'), is_test_file=False, is_cli_file=False, is_init_file=False, package_name=None, app_name='test-app', suppressions={})
    visitor = GoldenRuleVisitor(context, Path('/fake/project'))
    visitor.visit(tree)
    violations = [v for v in visitor.violations if v.rule_id == 'rule-37']
    assert len(violations) == 1
    assert 'os.getenv()' in violations[0].message

@pytest.mark.core
def test_allows_os_getenv_in_hive_config():
    """GR37 should allow os.getenv() in hive-config package"""
    code = '\nimport os\ndb_path = os.getenv("DATABASE_PATH")\n'
    tree = ast.parse(code)
    context = FileContext(path=Path('packages/hive-config/src/hive_config/loader.py'), content=code, ast_tree=tree, lines=code.split('\n'), is_test_file=False, is_cli_file=False, is_init_file=False, package_name='hive-config', app_name=None, suppressions={})
    visitor = GoldenRuleVisitor(context, Path('/fake/project'))
    visitor.visit(tree)
    violations = [v for v in visitor.violations if v.rule_id == 'rule-37']
    assert len(violations) == 0

@pytest.mark.core
def test_allows_os_getenv_in_scripts():
    """GR37 should allow os.getenv() in scripts directory"""
    code = '\nimport os\napi_key = os.getenv("API_KEY")\n'
    tree = ast.parse(code)
    context = FileContext(path=Path('scripts/deploy.py'), content=code, ast_tree=tree, lines=code.split('\n'), is_test_file=False, is_cli_file=False, is_init_file=False, package_name=None, app_name=None, suppressions={})
    visitor = GoldenRuleVisitor(context, Path('/fake/project'))
    visitor.visit(tree)
    violations = [v for v in visitor.violations if v.rule_id == 'rule-37']
    assert len(violations) == 0

@pytest.mark.core
def test_detects_config_file_io():
    """GR37 should catch direct config file reading"""
    code = '\nimport yaml\nwith open("config.yaml") as f:\n    config = yaml.load(f)\n'
    tree = ast.parse(code)
    context = FileContext(path=Path('apps/test-app/src/test_app/main.py'), content=code, ast_tree=tree, lines=code.split('\n'), is_test_file=False, is_cli_file=False, is_init_file=False, package_name=None, app_name='test-app', suppressions={})
    visitor = GoldenRuleVisitor(context, Path('/fake/project'))
    visitor.visit(tree)
    violations = [v for v in visitor.violations if v.rule_id == 'rule-37']
    assert len(violations) == 1
    assert 'config.yaml' in violations[0].message

@pytest.mark.core
def test_allows_config_file_io_in_hive_config():
    """GR37 should allow config file I/O in hive-config package"""
    code = '\nwith open("config.toml", "rb") as f:\n    data = f.read()\n'
    tree = ast.parse(code)
    context = FileContext(path=Path('packages/hive-config/src/hive_config/loader.py'), content=code, ast_tree=tree, lines=code.split('\n'), is_test_file=False, is_cli_file=False, is_init_file=False, package_name='hive-config', app_name=None, suppressions={})
    visitor = GoldenRuleVisitor(context, Path('/fake/project'))
    visitor.visit(tree)
    violations = [v for v in visitor.violations if v.rule_id == 'rule-37']
    assert len(violations) == 0

@pytest.mark.core
def test_allows_non_config_file_io():
    """GR37 should allow opening non-config files"""
    code = '\nwith open("data.csv") as f:\n    data = f.read()\n'
    tree = ast.parse(code)
    context = FileContext(path=Path('apps/test-app/src/test_app/processor.py'), content=code, ast_tree=tree, lines=code.split('\n'), is_test_file=False, is_cli_file=False, is_init_file=False, package_name=None, app_name='test-app', suppressions={})
    visitor = GoldenRuleVisitor(context, Path('/fake/project'))
    visitor.visit(tree)
    violations = [v for v in visitor.violations if v.rule_id == 'rule-37']
    assert len(violations) == 0

@pytest.mark.core
def test_allows_os_getenv_in_test_files():
    """GR37 should allow os.getenv() in test files"""
    code = '\nimport os\ndef test_config():\n    db_path = os.getenv("TEST_DATABASE_PATH")\n'
    tree = ast.parse(code)
    context = FileContext(path=Path('apps/test-app/tests/unit/test_config.py'), content=code, ast_tree=tree, lines=code.split('\n'), is_test_file=True, is_cli_file=False, is_init_file=False, package_name=None, app_name='test-app', suppressions={})
    visitor = GoldenRuleVisitor(context, Path('/fake/project'))
    visitor.visit(tree)
    violations = [v for v in visitor.violations if v.rule_id == 'rule-37']
    assert len(violations) == 0

@pytest.mark.core
def test_detects_env_file_reading():
    """GR37 should catch direct .env file reading"""
    code = '\nwith open(".env") as f:\n    env_vars = f.readlines()\n'
    tree = ast.parse(code)
    context = FileContext(path=Path('apps/test-app/src/test_app/config.py'), content=code, ast_tree=tree, lines=code.split('\n'), is_test_file=False, is_cli_file=False, is_init_file=False, package_name=None, app_name='test-app', suppressions={})
    visitor = GoldenRuleVisitor(context, Path('/fake/project'))
    visitor.visit(tree)
    violations = [v for v in visitor.violations if v.rule_id == 'rule-37']
    assert len(violations) == 1
    assert '.env' in violations[0].message
