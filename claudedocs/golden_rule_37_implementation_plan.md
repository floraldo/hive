# Golden Rule 37: Enforce Unified Configuration Loading

**Status**: Ready for Implementation
**Priority**: CRITICAL - The Immune System
**Severity**: ERROR (blocks PRs)

## Purpose

Prevent architectural regression by enforcing that ALL configuration loading goes through the unified config system. This transforms Project Unify V2 from a "nice to have" into an unbreakable law.

## Rule Definition

**Golden Rule 37**: "Enforce Unified Configuration Loading"

**What it detects**:
1. Direct calls to `os.getenv()` or `os.environ.get()` outside hive-config
2. Direct file I/O on config files (`.toml`, `.yaml`, `.json`, `.env`) outside hive-config
3. Imports of deprecated config patterns (`get_config()` singleton)

**Exceptions** (allowed):
- `packages/hive-config/**` - The config system itself
- `scripts/**` - Build and deployment scripts
- `tests/**` - Test fixtures may need direct env access
- Files with `# golden-rule-37: disable` comment

## Implementation Location

**File**: `packages/hive-tests/src/hive_tests/ast_validator.py`

**Method to add**: `_validate_unified_config_enforcement(self, node: ast.Call) -> None`

**Integration point**: Add to `visit_Call()` method (line ~108)

## Implementation Code

```python
def _validate_unified_config_enforcement(self, node: ast.Call) -> None:
    """
    Golden Rule 37: Enforce Unified Configuration Loading

    Prevents direct os.getenv() calls and config file I/O outside hive-config.
    Forces all configuration to go through the unified system.
    """
    # Skip if in exempt location
    if self._is_exempt_from_config_enforcement():
        return

    # Detect os.getenv() and os.environ.get()
    if isinstance(node.func, ast.Attribute):
        if isinstance(node.func.value, ast.Name):
            if node.func.value.id == "os" and node.func.attr in ("getenv", "environ"):
                self.add_violation(
                    rule_id="GR37",
                    rule_name="Unified Config Enforcement",
                    line_num=node.lineno,
                    message=(
                        f"Direct os.{node.func.attr} usage detected. "
                        f"Use unified config: from hive_config import load_config_for_app; "
                        f"config = load_config_for_app('my-app')"
                    ),
                    severity="error"
                )

    # Detect config file I/O (open('config.yaml'), etc.)
    if isinstance(node.func, ast.Name) and node.func.id == "open":
        if node.args:
            # Check if opening a config file
            if isinstance(node.args[0], ast.Constant):
                filename = str(node.args[0].value)
                if any(filename.endswith(ext) for ext in ['.toml', '.yaml', '.yml', '.json', '.env']):
                    # Check if it's a config file (contains 'config' in name or path)
                    if 'config' in filename.lower() or '.env' in filename:
                        self.add_violation(
                            rule_id="GR37",
                            rule_name="Unified Config Enforcement",
                            line_num=node.lineno,
                            message=(
                                f"Direct config file I/O detected: {filename}. "
                                f"Use unified config loader instead of reading config files directly."
                            ),
                            severity="error"
                        )

def _is_exempt_from_config_enforcement(self) -> bool:
    """Check if current file is exempt from Golden Rule 37"""
    file_str = str(self.context.path)

    # Exempt locations
    exempt_patterns = [
        'packages/hive-config/',  # The config system itself
        'scripts/',                # Build/deployment scripts
        '/tests/',                 # Test files
        'test_',                   # Test files
        'conftest.py',            # Pytest config
        'setup.py',               # Setup scripts
    ]

    return any(pattern in file_str for pattern in exempt_patterns)
```

## Integration into visit_Call()

Update the `visit_Call()` method to include the new validation:

```python
def visit_Call(self, node: ast.Call) -> None:
    """Validate function calls"""
    self._validate_no_unsafe_calls(node)
    self._validate_async_sync_mixing(node)
    self._validate_print_statements(node)
    self._validate_no_deprecated_config_calls(node)
    self._validate_unified_config_enforcement(node)  # NEW: Golden Rule 37
    self.generic_visit(node)
```

## Testing

**Test file**: `packages/hive-tests/tests/unit/test_golden_rule_37.py`

```python
def test_detects_os_getenv():
    """GR37 should catch direct os.getenv() usage"""
    code = '''
import os
db_path = os.getenv("DATABASE_PATH")
    '''
    violations = validate_code(code)
    assert any(v.rule_id == "GR37" for v in violations)

def test_allows_os_getenv_in_hive_config():
    """GR37 should allow os.getenv() in hive-config package"""
    # Set context to hive-config package
    violations = validate_code_in_package(code, "hive-config")
    assert not any(v.rule_id == "GR37" for v in violations)

def test_detects_config_file_io():
    """GR37 should catch direct config file reading"""
    code = '''
with open("config.yaml") as f:
    config = yaml.load(f)
    '''
    violations = validate_code(code)
    assert any(v.rule_id == "GR37" for v in violations)
```

## Expected Impact

**Before Golden Rule 37**:
- Developers might use `os.getenv()` out of habit
- Config files could be read directly, bypassing the hierarchy
- Technical debt accumulates silently

**After Golden Rule 37**:
- CI/CD blocks any PR with direct config access
- Unified config becomes the **only** way to get configuration
- Architecture cannot regress

## Rollout Strategy

1. **Implement the rule** (this PR)
2. **Set severity to WARNING initially** - Allow existing violations
3. **Fix all existing violations** - Systematic cleanup
4. **Upgrade severity to ERROR** - Lock it down permanently

## Success Metrics

- Zero new `os.getenv()` calls outside hive-config
- All apps using `load_config_for_app()` within 2 weeks
- Pre-commit hooks catching violations before CI/CD

## Next Steps

1. Implement Golden Rule 37 in ast_validator.py
2. Add unit tests
3. Run validation across codebase (expect ~50 violations)
4. Begin systematic migration (Action 2)
5. Once clean, set severity to ERROR permanently
