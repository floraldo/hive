# Hive Codebase Continuation Plan

## Current Session Summary
**Date**: 2025-09-28
**Session Goal**: Fix test failures and import issues in Hive modular monolith architecture

## ✅ Completed Work

### 1. Fixed AI-Planner Syntax Errors
- **File**: `apps/ai-planner/src/ai_planner/agent.py`
- **Issue**: Escaped quotes (`\"`) throughout the file
- **Resolution**: Removed all escape characters, fixed all syntax errors

### 2. Fixed Package Dependencies
Updated `pyproject.toml` files to match actual package directory names:
- `hive-db-utils` → `hive-db`
- `hive-messaging` → `hive-bus`
- `hive-error-handling` → `hive-errors`
- `hive-testing-utils` → `hive-tests`

**Files Updated**:
- `apps/ai-planner/pyproject.toml`
- `apps/ai-reviewer/pyproject.toml`
- `apps/hive-orchestrator/pyproject.toml`

### 3. Fixed Ecosystemiser Tests
- **File**: `apps/legacy/ecosystemiser/tests/test_core.py`
- **Issue**: Enum comparison failing
- **Resolution**: Changed comparisons to use `.value` property

### 4. Successfully Installed Packages
- Installed `hive-orchestrator` as editable package
- Basic tests passing: `test_simple.py` (6/6 ✅)

## ⚠️ Remaining Critical Issues

### 1. Import Name Mismatch (PRIORITY 1)

**Problem**: `hive_orchestrator.core.db` exports `get_connection` but code imports `get_database`

**Files to Fix**:
```python
# apps/hive-orchestrator/src/hive_orchestrator/hive_core.py:20
# CURRENT (WRONG):
from .core.db import get_database, get_pooled_connection

# CHANGE TO:
from .core.db import get_connection, get_pooled_connection

# Also update usage in the same file:
# Replace: get_database()
# With: get_connection()
```

```python
# apps/ai-planner/src/ai_planner/agent.py:95-96
# Check if this file has similar import issues and fix accordingly
```

### 2. Test Import Issues (PRIORITY 2)

**Problem**: Tests importing wrong package names

**Files to Fix**:
```python
# apps/hive-orchestrator/tests/test_golden_rules.py:16
# CURRENT (WRONG):
from hive_tests.architectural_validators import validate_app_contract

# CHANGE TO:
from hive_testing_utils.architectural_validators import validate_app_contract
```

Check all test files for similar import issues:
```bash
grep -r "from hive_tests" apps/*/tests/
grep -r "import hive_tests" apps/*/tests/
```

### 3. Package Installation Issues

Some packages may not be properly installed. Run:
```bash
# Install ai-reviewer dependencies
cd apps/ai-reviewer
poetry install
cd ../..

# Ensure all packages are installed
python -m pip install -e packages/hive-tests
python -m pip install -e packages/hive-db
python -m pip install -e packages/hive-bus
python -m pip install -e packages/hive-errors
```

## 🎯 Execution Steps for Next Session

### Step 1: Fix Import Name Mismatch
```bash
# 1. Fix hive_core.py
cd C:\git\hive
# Edit apps/hive-orchestrator/src/hive_orchestrator/hive_core.py
# Change line 20: get_database → get_connection
# Update all usages of get_database() to get_connection()

# 2. Check ai-planner for similar issues
# Edit apps/ai-planner/src/ai_planner/agent.py if needed
```

### Step 2: Fix Test Imports
```bash
# 1. Fix golden rules test
# Edit apps/hive-orchestrator/tests/test_golden_rules.py
# Change: hive_tests → hive_testing_utils

# 2. Search and fix all test imports
grep -r "from hive_tests" apps/*/tests/ --include="*.py"
# Fix all occurrences
```

### Step 3: Verify Package Structure
```bash
# Check actual package names in packages/ directory
ls -la packages/
# Confirm: hive-db, hive-bus, hive-errors, hive-tests exist

# Check what's exported from each package
python -c "from hive_db import *; print(dir())"
python -c "from hive_bus import *; print(dir())"
```

### Step 4: Run Comprehensive Tests
```bash
# Run tests in order of dependency
python -m pytest apps/hive-orchestrator/tests/test_simple.py -v
python -m pytest apps/hive-orchestrator/tests/test_golden_rules.py -v
python -m pytest apps/ai-planner/tests/ -v
python -m pytest apps/ai-reviewer/tests/ -v
python -m pytest apps/legacy/ecosystemiser/tests/test_core.py -v
```

### Step 5: Document Remaining Issues
After running tests, create a status report:
- Which tests pass
- Which tests fail and why
- Any new import or dependency issues discovered

## 📚 Important Context

### Architecture Pattern
- **"Inherit → Extend" Pattern**: Apps extend generic packages in their `core/` modules
- **Dependency Direction**: Apps → Packages only (never reverse)
- **Core Service Layer**: Each app has `core/` modules for extensions

### Package Name Mapping (Critical!)
```
Directory Name     → Python Package Name
-----------------------------------------
hive-db           → hive_db
hive-errors       → hive_errors (NOT hive_error_handling)
hive-tests        → hive_tests (NOT hive_testing_utils)
hive-bus          → hive_bus (NOT hive_messaging)
```

### Poetry Workspace Notes
- Uses `develop = true` for editable installs
- Changes to packages are immediately available
- No need to update lock files for local changes
- Run `poetry install` in each app directory if imports fail

### Try/Except Removal Guidelines
**Remove if:**
- Catching ImportError for Poetry-managed dependencies
- Just re-raising without adding context
- Creating incorrect fallback patterns

**Keep if:**
- Handling specific expected errors (JSON, network, etc.)
- Providing meaningful fallback behavior
- Adding debugging context or transforming errors

## 🔍 Debugging Commands

```bash
# Check installed packages
pip list | grep hive

# Verify editable installs
pip show -f hive-orchestrator

# Check Poetry dependencies
cd apps/hive-orchestrator && poetry show

# Test specific import
python -c "from hive_orchestrator.core.db import get_connection; print('Success')"

# Find all get_database references
grep -r "get_database" apps/ --include="*.py"
```

## 📝 Success Criteria

The session is complete when:
1. ✅ All import errors are resolved
2. ✅ `test_simple.py` passes (6/6 tests)
3. ✅ `test_golden_rules.py` passes
4. ✅ At least one test from each app runs successfully
5. ✅ No syntax errors remain
6. ✅ Package dependencies are correctly configured

## 🚨 Common Pitfalls to Avoid

1. **Don't confuse directory names with package names** - they often differ
2. **Don't assume package exports** - check what's actually available
3. **Don't skip Poetry install** - some issues are solved by proper installation
4. **Don't ignore core/ pattern** - business logic should import from core/, not packages directly

## Working Directory
```
C:\git\hive
```

## Final Note
After completing fixes, run the comprehensive test suite and create a final status report documenting which components are fully functional and which may need additional attention.