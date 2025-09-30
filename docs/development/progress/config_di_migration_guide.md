# Configuration Dependency Injection Migration Guide

**Status**: In Progress
**Created**: 2025-09-30
**Part of**: Project Aegis Stage 6

## Overview

This guide documents the migration from global state configuration (`get_config()`) to dependency injection (DI) pattern.

---

## Why Migrate?

**Problems with Global State:**
- Hard to test (requires global state reset)
- Hidden dependencies (functions use config without declaring it)
- Difficult to reason about (who changed the config?)
- Thread-safety issues
- Makes code harder to understand and maintain

**Benefits of Dependency Injection:**
- Explicit dependencies (clear what each function needs)
- Easy to test (pass mock config to constructor)
- No global state (each instance has its own config)
- Thread-safe by default
- Better separation of concerns

---

## Migration Pattern

### OLD (Deprecated Global State)

```python
from hive_config import load_config, get_config

# Initialize global config
load_config()

class MyService:
    def __init__(self):
        # Hidden dependency on global config
        pass

    def do_something(self):
        # Get config from global state
        config = get_config()
        db_path = config.database.path
        # ... use config
```

### NEW (Dependency Injection)

```python
from hive_config import HiveConfig, create_config_from_sources

class MyService:
    def __init__(self, config: HiveConfig):
        # Explicit dependency
        self.config = config
        self.db_path = config.database.path

    def do_something(self):
        # Use instance config
        path = self.config.database.path
        # ... use config

# Usage
config = create_config_from_sources()
service = MyService(config=config)
service.do_something()
```

---

## Migration Steps

### Step 1: Update Constructor

```python
# BEFORE
class MyClass:
    def __init__(self):
        self.config = get_config()  # Global state

# AFTER
class MyClass:
    def __init__(self, config: HiveConfig | None = None):
        from hive_config import create_config_from_sources
        self.config = config or create_config_from_sources()
```

**Note**: Providing default with `config or create_config_from_sources()` maintains backward compatibility during migration.

### Step 2: Update Callers

```python
# BEFORE
service = MyClass()

# AFTER
from hive_config import create_config_from_sources
config = create_config_from_sources()
service = MyClass(config=config)
```

### Step 3: Remove Global Dependency

Once all callers are updated, make config required:

```python
# FINAL
class MyClass:
    def __init__(self, config: HiveConfig):
        self.config = config
```

---

## Real Examples

### Example 1: EcoSystemiser Config Bridge

**Before** (`apps/ecosystemiser/src/ecosystemiser/config/bridge.py:31`):
```python
from hive_config import get_config

class ConfigBridge:
    def __init__(self, hive_config: HiveConfig | None = None):
        self._hive_config = hive_config or get_config()  # Global state fallback
```

**After**:
```python
from hive_config import HiveConfig, create_config_from_sources

class ConfigBridge:
    def __init__(self, hive_config: HiveConfig | None = None):
        # Create fresh config instead of global state
        self._hive_config = hive_config or create_config_from_sources()
```

**Why**: Using `create_config_from_sources()` creates a new config instance instead of relying on global state. Each ConfigBridge instance can have its own config if needed.

---

### Example 2: Guardian Agent Analyzer

**Before** (`apps/guardian-agent/src/guardian_agent/intelligence/cross_package_analyzer.py:341`):
```python
from hive_config import get_config

config = get_config()  # Module-level global state
```

**After**:
```python
from hive_config import HiveConfig, create_config_from_sources

# Option 1: Pass config to functions
def analyze_packages(config: HiveConfig):
    # Use config parameter
    pass

# Option 2: Store in class instance
class CrossPackageAnalyzer:
    def __init__(self, config: HiveConfig):
        self.config = config
```

---

### Example 3: Test Files

**Before** (Multiple test files):
```python
def test_something():
    from hive_config import get_config
    config = get_config()
    assert config.database.path
```

**After**:
```python
@pytest.fixture
def test_config():
    from hive_config import create_config_from_sources
    return create_config_from_sources()

def test_something(test_config):
    assert test_config.database.path
```

**Or with pytest fixture**:
```python
@pytest.fixture
def mock_config():
    from hive_config import HiveConfig, DatabaseConfig
    return HiveConfig(
        database=DatabaseConfig(path=Path(":memory:"))
    )

def test_something(mock_config):
    service = MyService(config=mock_config)
    # Test with controlled config
```

---

## Files to Migrate

**Total `get_config()` Usages**: 13 across platform
**Audit Status**: ✅ Complete (see `claudedocs/config_system_audit.md`)

### Gold Standard Reference

**EcoSystemiser** already demonstrates the ideal pattern in `apps/ecosystemiser/src/ecosystemiser/config/bridge.py`:

```python
class EcoSystemiserConfig:
    def __init__(self, hive_config: HiveConfig | None = None):
        # Gold standard: DI with factory fallback
        self._hive_config = hive_config or create_config_from_sources()
        self._eco_config = EcoSystemiserSettings()
```

This is the template all apps should follow!

### Active Files (Non-Test)

1. **apps/guardian-agent/src/guardian_agent/intelligence/cross_package_analyzer.py:332**
   - **Pattern**: Pattern library example showing `get_config()` usage
   - **Risk**: Medium (developers copy these examples)
   - **Migration**: Update integration pattern to show DI instead
   - **Priority**: HIGH (affects developer adoption)
   - **File**: Example code in `IntegrationPattern` (lines 332-344)
   - **Action**: Replace example with DI pattern showing constructor injection

2. **packages/hive-tests/src/hive_tests/architectural_validators.py:1442-1443**
   - **Pattern**: Testing for forbidden global calls
   - **Risk**: None (validation code)
   - **Action**: Keep as-is (this validates against anti-patterns)
   - **Priority**: N/A

### Test Files (Lower Priority)

3. **apps/hive-orchestrator/tests/integration/test_comprehensive.py:218**
   - **Pattern**: `config = get_config()` in test function
   - **Risk**: Low (test only)
   - **Migration**: Use pytest fixture with `create_config_from_sources()`
   - **Priority**: MEDIUM

4. **apps/hive-orchestrator/tests/integration/test_minimal_cert.py:usage detected**
   - **Pattern**: Global config in test
   - **Risk**: Low (test only)
   - **Migration**: Pytest fixture
   - **Priority**: MEDIUM

5. **apps/hive-orchestrator/tests/integration/test_v3_certification.py:4 usages**
   - **Pattern**: Multiple `get_config()` calls in test
   - **Risk**: Low (test only)
   - **Migration**: Create fixture, reuse across tests
   - **Priority**: MEDIUM

### Self-References (Documentation Only)

6. **packages/hive-config/src/hive_config/unified_config.py:3 usages**
   - **Pattern**: Internal references, example code, deprecation warnings
   - **Risk**: None (self-contained)
   - **Action**: Update documentation examples to show DI
   - **Priority**: LOW

## Migration Summary by Category

| Category | Count | Risk | Priority | Status |
|----------|-------|------|----------|--------|
| Pattern Library Examples | 1 | Medium | HIGH | Pending |
| Test Files | 5 | Low | MEDIUM | Pending |
| Validation Code | 1 | None | N/A | Keep As-Is |
| Self-References | 3 | None | LOW | Update Docs |
| **TOTAL** | **13** | **Low** | **Mixed** | **In Progress** |

## Migration Patterns by Usage Type

### Type 1: Pattern Library Example (1 file)
**Example**: guardian-agent/cross_package_analyzer.py

**Current**:
```python
IntegrationPattern(
    required_import="from hive_config import get_config",
    replacement_code="""
from hive_config import get_config
config = get_config()
API_KEY = config.api_key
""",
)
```

**Target**:
```python
IntegrationPattern(
    required_import="from hive_config import HiveConfig, create_config_from_sources",
    replacement_code="""
class MyService:
    def __init__(self, config: HiveConfig | None = None):
        self._config = config or create_config_from_sources()
        self.api_key = self._config.api_key
""",
)
```

### Type 2: Test Usage (5 files)
**Example**: hive-orchestrator tests

**Current**:
```python
def test_something():
    from hive_config import get_config
    config = get_config()
    assert config.database.path
```

**Target**:
```python
@pytest.fixture
def hive_config():
    from hive_config import create_config_from_sources
    return create_config_from_sources()

def test_something(hive_config):
    assert hive_config.database.path
```

---

## Testing Strategy

### Before Migration
```python
# Old way - requires global state management
from hive_config import load_config, reset_config

def test_something():
    load_config()  # Setup global state
    # ... test code
    reset_config()  # Cleanup global state
```

### After Migration
```python
# New way - isolated, no global state
def test_something():
    from hive_config import HiveConfig, DatabaseConfig

    # Create test-specific config
    config = HiveConfig(
        database=DatabaseConfig(path=Path(":memory:"))
    )

    # Pass to service
    service = MyService(config=config)

    # Test - no cleanup needed
```

---

## Migration Status

**Audit Phase**: ✅ COMPLETE (2025-09-30)
- Total usages identified: 13
- Risk assessment: LOW
- Gold standard pattern documented: EcoSystemiser
- Migration plan created: 5 phases

**Deprecation Warnings Added**: ✅
- `load_config()` - Added deprecation warning
- `get_config()` - Added deprecation warning

**Phase 1: Documentation Update** (IN PROGRESS - 2025-09-30)
- [x] packages/hive-config/README.md - Enhanced with gold standard pattern
- [x] config_di_migration_guide.md - Updated with audit findings
- [ ] claudedocs/config_migration_guide_comprehensive.md - Comprehensive developer guide
- [ ] .claude/CLAUDE.md - AI agent reference updated

**Phase 2: Pattern Library Update** (PENDING)
- [ ] guardian-agent/cross_package_analyzer.py - Update integration pattern examples
- Estimated: 1 hour
- Priority: HIGH (affects developer adoption)

**Phase 3: Test Fixtures** (PENDING)
- [ ] apps/hive-orchestrator/tests/conftest.py - Create fixtures
- [ ] test_comprehensive.py - Use fixtures
- [ ] test_v3_certification.py - Use fixtures
- Estimated: 1 hour
- Priority: MEDIUM

**Phase 4: Deprecation Enforcement** (PENDING)
- [ ] Add golden rule to detect get_config() usage
- [ ] Increase warning verbosity
- Estimated: 30 minutes
- Priority: MEDIUM

**Phase 5: Global State Removal** (FUTURE - Week 8-10)
- [ ] Remove `_global_config` variable
- [ ] Remove `get_config()` function
- [ ] Remove `load_config()` function
- Priority: LOW (wait for adoption)

**Active Files Migrated**:
- [x] apps/ecosystemiser/src/ecosystemiser/config/bridge.py (GOLD STANDARD)
- [x] apps/hive-orchestrator/src/hive_orchestrator/core/claude/claude_service.py (unused import removed)

**Test Files to Migrate**: 5 files
- [ ] apps/hive-orchestrator/tests/integration/test_comprehensive.py
- [ ] apps/hive-orchestrator/tests/integration/test_minimal_cert.py
- [ ] apps/hive-orchestrator/tests/integration/test_v3_certification.py (4 usages)

**Timeline**:
- Phase 1-3: Week 1 (3.5 hours total)
- Phase 4: Week 2 (30 minutes)
- Phase 5: Weeks 8-10 (after adoption period)

**Success Metrics**:
- `get_config()` usage: 13 → 0 (target)
- DI pattern adoption: 1 app (EcoSystemiser) → all apps
- Test isolation: Global state → Independent fixtures
- Developer satisfaction: TBD (post-migration survey)

---

## Rollback Plan

If migration causes issues:

1. **Deprecation warnings can be suppressed**:
   ```python
   import warnings
   warnings.filterwarnings('ignore', category=DeprecationWarning)
   ```

2. **Global state still works** - No breaking changes yet

3. **Gradual migration** - Migrate one file at a time, test thoroughly

---

## Future Work

After all files migrated:

1. Remove `_global_config` variable
2. Remove `load_config()` function
3. Remove `get_config()` function
4. Remove `reset_config()` function
5. Archive `unified_config.py` or simplify to only `create_config_from_sources()`

---

## Questions?

**Q: Can I mix old and new patterns?**
A: Yes, during migration both patterns work. Deprecation warnings remind you to migrate.

**Q: Will this break existing code?**
A: No. Old pattern still works, just emits deprecation warnings.

**Q: When will global state be removed?**
A: After all files are migrated and tested (tracked separately).

**Q: What about performance?**
A: `create_config_from_sources()` is lightweight. Create once and reuse the instance.