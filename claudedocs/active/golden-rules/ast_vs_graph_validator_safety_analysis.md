# AST vs Graph Validator Safety Analysis

**Date**: 2025-10-03
**Status**: COMPREHENSIVE SAFETY ASSESSMENT
**Purpose**: Determine safe deprecation strategy for dependency validation

---

## Executive Summary

**CRITICAL FINDING**: The AST validator is a **multi-purpose validation engine** with 15+ distinct rules. Only 2 of these rules overlap with the graph validator's capabilities.

**SAFE DEPRECATION STRATEGY**: Remove ONLY the 2 dependency-specific methods from AST validator, keep all other validation rules intact.

**RISK LEVEL**: ✅ LOW - Surgical removal of redundant code, preserving all other validations

---

## Complete AST Validator Inventory

### File: `packages/hive-tests/src/hive_tests/ast_validator.py`

**Total Lines**: 1377
**Purpose**: Single-pass AST-based validation system for Golden Rules
**Architecture**: Visitor pattern traversing AST nodes

### Validation Rules Implemented

#### **Category 1: Dependency/Import Rules** (2 rules - OVERLAP with Graph Validator)

| Rule | Method | Lines | Purpose | Graph Validator Equivalent |
|------|--------|-------|---------|---------------------------|
| ✅ **Rule 6** | `_validate_dependency_direction()` | 135-144 | Direct import validation (app → app) | ✅ YES - Rule 2 "No cross-app imports" |
| ✅ **Rule 5/6** | `_validate_dependency_direction_from()` | 146-175 | From import validation (pkg → app, app → app) | ✅ YES - Rule 1 "Packages cannot depend on apps" + Rule 2 |

**Special Handling in AST**:
- Test file exemptions (`is_test_file`, `/tests/` paths)
- Demo file exemptions (`demo_`, `run_` prefixes)
- Legacy hive_orchestrator.core allowances (deprecated)

**Graph Validator Coverage**:
- ✅ Covers packages → apps (Rule 1, transitive)
- ✅ Covers app → app (Rule 2, direct only)
- ❓ Question: Does it handle test/demo file exemptions?

---

#### **Category 2: Code Quality Rules** (13 rules - NO OVERLAP, MUST KEEP)

| Rule | Method | Lines | Purpose | Replaceable? |
|------|--------|-------|---------|--------------|
| Rule 17 | `_validate_no_unsafe_calls()` | 177-221 | No eval/exec/os.system | ❌ NO - AST-only |
| Rule 19 | `_validate_async_sync_mixing()` | 222-255 | No blocking calls in async | ❌ NO - AST-only |
| Rule 9 | `_validate_print_statements()` | 257-280 | No print() in production | ❌ NO - AST-only |
| Rule 7 | `_validate_interface_contracts()` | 282-314 | Type hints required | ❌ NO - AST-only |
| Rule 7 | `_validate_interface_contracts_async()` | 326-337 | Async type hints | ❌ NO - AST-only |
| Rule 8 | `_validate_error_handling_standards()` | 339-384 | Exception inheritance | ❌ NO - AST-only |
| Rule 14 | `_validate_async_naming()` | 386-405 | Async function naming | ❌ NO - AST-only |
| Rule 17 | `_validate_no_unsafe_imports()` | 407-418 | No pickle/marshal | ❌ NO - AST-only |
| Rule 17 | `_validate_no_unsafe_imports_from()` | 420-428 | No unsafe from imports | ❌ NO - AST-only |
| Rule 24 | `_validate_no_deprecated_config_imports()` | 430-453 | No get_config import | ❌ NO - AST-only |
| Rule 24 | `_validate_no_deprecated_config_calls()` | 455-472 | No get_config() calls | ❌ NO - AST-only |

---

#### **Category 3: Structural Rules** (13 rules - NO OVERLAP, MUST KEEP)

These are non-AST rules in `EnhancedValidator` class:

| Rule | Method | Lines | Purpose | Replaceable? |
|------|--------|-------|---------|--------------|
| Rule 1 | `_validate_app_contracts()` | 698-716 | hive-app.toml required | ❌ NO - File structure |
| Rule 2 | `_validate_colocated_tests()` | 718-736 | tests/ directory required | ❌ NO - File structure |
| Rule 22 | `_validate_documentation_hygiene()` | 738-756 | README.md required | ❌ NO - File structure |
| Rule 21 | `_validate_models_purity()` | 758-803 | hive-models purity | ❌ NO - AST analysis |
| Rule 14 | `_validate_package_naming_consistency()` | 805-822 | hive-* prefix | ❌ NO - File structure |
| Rule 13 | `_validate_inherit_extend_pattern()` | 824-885 | Inherit→extend pattern | ❌ NO - File content |
| Rule 24 | `_validate_python_version_consistency()` | 887-965 | Python 3.11 requirement | ❌ NO - TOML parsing |
| Rule 4 | `_validate_single_config_source()` | 967-1038 | pyproject.toml only | ❌ NO - File structure |
| Rule 7 | `_validate_service_layer_discipline()` | 1040-1108 | Core layer purity | ❌ NO - AST analysis |
| Rule 23 | `_validate_unified_tool_configuration()` | 1110-1153 | Root tool config | ❌ NO - TOML parsing |
| Rule 22 | `_validate_pyproject_dependency_usage()` | 1155-1233 | Unused dependencies | ❌ NO - AST + TOML |
| Rule 16 | `_validate_cli_pattern_consistency()` | 1235-1272 | CLI framework usage | ❌ NO - AST analysis |
| Rule 18 | `_validate_test_coverage_mapping()` | 1274-1376 | Test-source mapping | ❌ NO - File structure |

---

## Graph Validator Capabilities

### File: `packages/hive-tests/src/hive_tests/dependency_graph_validator.py`

**Total Lines**: 394
**Purpose**: Whole-codebase dependency graph analysis
**Architecture**: Graph traversal with BFS for transitive dependencies

### Validation Rules Implemented

| Rule | Name | Source Pattern | Target Pattern | Transitive | Severity |
|------|------|----------------|----------------|------------|----------|
| Rule 1 | "Packages cannot depend on apps" | `packages/**` | `apps/**` | YES | CRITICAL |
| Rule 2 | "No cross-app imports (app-to-app)" | `apps/**` | `apps/**` | NO (direct only) | CRITICAL |

**Key Capabilities**:
- ✅ Detects transitive violations (A → B → C where A→C forbidden)
- ✅ Uses hive-graph for accurate dependency parsing
- ✅ Caches graph for performance
- ✅ Provides full dependency path in violations

**Limitations**:
- ❌ No special handling for test files (exemptions)
- ❌ No special handling for demo/run scripts
- ❌ No awareness of deprecated patterns (hive_orchestrator.core)
- ❓ Need to verify: Does it catch the same violations as AST?

---

## Capability Comparison Matrix

### Dependency Validation Comparison

| Capability | AST Validator | Graph Validator | Winner |
|------------|---------------|-----------------|---------|
| **Packages → Apps** | ✅ Direct imports only | ✅ Direct + transitive | **Graph** (more powerful) |
| **App → App** | ✅ Direct imports only | ✅ Direct imports | **TIE** (same coverage) |
| **Test file exemptions** | ✅ Built-in | ❌ Not implemented | **AST** (more lenient) |
| **Demo file exemptions** | ✅ Built-in | ❌ Not implemented | **AST** (more lenient) |
| **Transitive detection** | ❌ Cannot detect | ✅ Full path analysis | **Graph** (critical feature) |
| **Performance** | ✅ Fast (single pass) | ⚠️ Slower (graph build) | **AST** (but cached) |
| **Accuracy** | ✅ File-local precision | ✅ Whole-codebase view | **Graph** (architectural) |

### Non-Dependency Validation Comparison

| Capability | AST Validator | Graph Validator | Winner |
|------------|---------------|-----------------|---------|
| **Type hints** | ✅ Full support | ❌ Not applicable | **AST** (ONLY option) |
| **Print statements** | ✅ Full support | ❌ Not applicable | **AST** (ONLY option) |
| **Unsafe calls** | ✅ Full support | ❌ Not applicable | **AST** (ONLY option) |
| **Async patterns** | ✅ Full support | ❌ Not applicable | **AST** (ONLY option) |
| **Exception standards** | ✅ Full support | ❌ Not applicable | **AST** (ONLY option) |
| **Config patterns** | ✅ Full support | ❌ Not applicable | **AST** (ONLY option) |
| **File structure** | ✅ Full support | ❌ Not applicable | **AST** (ONLY option) |

---

## Gap Analysis

### Gap 1: Test File Exemptions

**AST Validator Logic** (lines 148-154):
```python
# Allow test files to import from their own app more freely
if self.context.is_test_file or "/tests/" in str(self.context.path):
    return  # Test files can import from their parent app

# Allow demo/run files to import from their own app
if self.context.path.name.startswith(("demo_", "run_")):
    return  # Demo and run files can import from their app
```

**Graph Validator**: No equivalent logic

**Impact**: Graph validator may report violations in test files that AST exempts

**Resolution Options**:
1. Add exemption logic to graph validator
2. Accept stricter enforcement (test files should also follow rules)
3. Use file filtering in validation runner

**Recommendation**: Option 3 - Filter test files at runner level (cleaner)

---

### Gap 2: Deprecated Pattern Awareness

**AST Validator Logic** (lines 479-487):
```python
"""
DEPRECATED PATTERN: hive-orchestrator.core imports are deprecated.
Use hive-orchestration package instead.

Platform app exception (DEPRECATED - use hive-orchestration package):
- hive_orchestrator.core.db → hive_orchestration (task/worker operations)
- hive_orchestrator.core.bus → hive_orchestration (event bus integration)
"""
```

**Graph Validator**: No equivalent deprecation awareness

**Impact**: None - these were already exemptions, not violations

**Resolution**: No action needed (exemptions being removed anyway)

---

### Gap 3: Same-App Import Allowance

**AST Validator Logic** (lines 496-501):
```python
# Skip if importing from current app (more lenient matching)
if self.context.app_name:
    app_name_normalized = self.context.app_name.replace("-", "_")
    if module_name.startswith(app_name_normalized):
        return False  # Allow same-app imports
```

**Graph Validator**: Rule 2 forbids ALL app→app, including same-app

**Impact**: **CRITICAL DIFFERENCE** - Graph validator is stricter!

**Example**:
- `apps/ecosystemiser/core/config.py` imports from `apps/ecosystemiser/services/solver.py`
- AST: ✅ Allowed (same app)
- Graph: ❌ Forbidden (app→app pattern match)

**Resolution**: **MUST FIX** - Graph validator Rule 2 needs same-app exemption logic

---

## Safety Assessment

### Safe to Deprecate: ✅ Partially (with fixes)

**What CAN be deprecated**:
- ✅ `_validate_dependency_direction()` method (lines 135-144)
- ✅ `_validate_dependency_direction_from()` method (lines 146-175)
- ✅ `_is_invalid_app_import()` helper method (lines 475-509)

**What MUST be kept**:
- ⚠️ ALL other AST validation methods (13+ rules)
- ⚠️ Visitor pattern infrastructure (`visit_Import`, `visit_Call`, etc.)
- ⚠️ EnhancedValidator structural rules

**What MUST be fixed first**:
1. **CRITICAL**: Add same-app exemption to Graph Rule 2
2. **IMPORTANT**: Add test/demo file filtering at runner level
3. **OPTIONAL**: Document deprecated pattern migration

---

## Migration Plan

### Phase 1: Fix Graph Validator (REQUIRED)

**Change 1: Update Rule 2 to exempt same-app imports**

```python
DependencyRule(
    name="No cross-app imports (app-to-app)",
    source_pattern="apps/**",
    target_pattern="apps/**",
    rule_type=RuleType.CANNOT_DEPEND_ON,
    severity="CRITICAL",
    check_transitive=False,
    # NEW: Add exemption checker
    exemption_logic="same_app_allowed"
)
```

Implement `same_app_allowed` logic:
- Extract app name from source and target paths
- If `source_app == target_app`, return `exempt=True`
- Otherwise, check violation

**Change 2: Add file filtering in validate_dependency_graph()**

```python
def validate_dependency_graph(...):
    # Filter out test files, demo files, run files
    exempt_patterns = ["/tests/", "demo_", "run_", "/archive/"]

    filtered_violations = [
        v for v in violations
        if not any(pattern in str(v.file_path) for pattern in exempt_patterns)
    ]
```

### Phase 2: Deprecate AST Dependency Methods (SAFE)

**Remove from `ast_validator.py`**:
1. Delete `_validate_dependency_direction()` (lines 135-144)
2. Delete `_validate_dependency_direction_from()` (lines 146-175)
3. Delete `_is_invalid_app_import()` (lines 475-509)
4. Remove calls from `visit_Import()` and `visit_ImportFrom()`

**Update visitor methods**:
```python
def visit_Import(self, node: ast.Import) -> None:
    """Validate import statements"""
    # self._validate_dependency_direction(node)  # REMOVE THIS
    self._validate_no_unsafe_imports(node)
    self.generic_visit(node)

def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
    """Validate from imports"""
    # self._validate_dependency_direction_from(node)  # REMOVE THIS
    self._validate_no_unsafe_imports_from(node)
    self._validate_no_deprecated_config_imports(node)
    self.generic_visit(node)
```

### Phase 3: Validation Testing (VERIFY)

**Test 1: Same violations detected**
```bash
# Before deprecation
python scripts/validation/validate_golden_rules.py --level ERROR > before.txt

# After deprecation
python scripts/validation/validate_golden_rules.py --level ERROR > after.txt

# Compare
diff before.txt after.txt
# Expected: Only formatting differences, same violation count
```

**Test 2: Same-app imports allowed**
```bash
# Test ecosystemiser internal imports
cd apps/ecosystemiser
# Should pass (same-app imports allowed)
```

**Test 3: Test file exemptions work**
```bash
# Test files should not trigger violations
# Demo files should not trigger violations
```

---

## Recommendation

### ✅ SAFE TO PROCEED (with required fixes)

**Prerequisites**:
1. ✅ Fix Graph Validator Rule 2 (same-app exemption)
2. ✅ Add test/demo file filtering
3. ✅ Run parallel validation test

**Deprecation Strategy**:
- Remove ONLY the 2 dependency methods from AST validator
- Keep ALL other validation rules intact
- Graph validator becomes sole authority on dependency architecture
- AST validator remains for all code quality rules

**Risk Level**: ✅ **LOW**
- Surgical removal of redundant code
- All other validations preserved
- Graph validator is strictly more powerful (with fixes)
- Parallel testing ensures no regressions

**Timeline**:
1. Fix graph validator (1-2 hours)
2. Test in parallel (30 minutes)
3. Deprecate AST methods (15 minutes)
4. Final validation (15 minutes)

**Total Effort**: 2-3 hours for complete, safe migration

---

## Conclusion

The AST validator is a **critical multi-purpose validation engine** that cannot be fully deprecated. However, the 2 dependency-specific methods are safely replaceable by the superior graph-based approach.

**Action**: Proceed with surgical deprecation after fixing graph validator Rule 2.

---

**Prepared by**: Claude Code (pkg agent)
**Reviewed for**: User safety and architectural integrity
**Status**: Ready for implementation (pending Graph Rule 2 fix)
