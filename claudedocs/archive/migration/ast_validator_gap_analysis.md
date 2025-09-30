# AST Validator Implementation Gap Analysis

## Date: 2025-09-30

## Summary

Comparison of rules between the rglob-based validators and the AST-based EnhancedValidator to identify implementation gaps.

## Rule Coverage Matrix

### Implemented in AST Validator (14 rules)

| Rule ID | Rule Name | Implementation Method | Status |
|---------|-----------|----------------------|--------|
| 1 | App Contracts | `_validate_app_contracts()` | Complete |
| 2 | Colocated Tests | `_validate_colocated_tests()` | Complete |
| 3 | No sys.path Hacks | `_validate_no_unsafe_imports()` | Complete |
| 6 | Dependency Direction | `_validate_dependency_direction()` | Complete |
| 8 | Communication Patterns | `_validate_async_sync_mixing()` | Partial |
| 9 | Interface Contracts | `_validate_interface_contracts()` | Complete |
| 10 | Error Handling Standards | `_validate_error_handling_standards()` | Complete |
| 11 | No Hardcoded Env Values | String pattern checking | Complete |
| 12 | Logging Standards | `_validate_print_statements()` | Complete |
| 15 | Async Pattern Consistency | `_validate_async_naming()` | Complete |
| 17 | No Global State Access | `_validate_no_unsafe_calls()` | Partial |
| 19 | Documentation Hygiene | `_validate_documentation_hygiene()` | Complete |
| 20 | Models Purity | `_validate_models_purity()` | Complete |
| 21 | Test File Quality | Part of test validation | Partial |

### Missing from AST Validator (9 rules)

| Rule ID | Rule Name | Complexity | Reason Not in AST |
|---------|-----------|-----------|-------------------|
| 4 | Single Config Source | Medium | Multi-file analysis (detect duplicate configs) |
| 5 | Package-App Discipline | Low | File path analysis (package imports app) |
| 7 | Service Layer Discipline | Medium | Architecture pattern detection |
| 13 | Inherit-Extend Pattern | Low | Directory structure validation |
| 14 | Package Naming Consistency | Low | File naming pattern checking |
| 15b | Development Tools Consistency | Low | pyproject.toml cross-package comparison |
| 16 | CLI Pattern Consistency | Medium | CLI command pattern validation |
| 18 | Test Coverage Mapping | High | Cross-reference tests with source files |
| 22 | Pyproject Dependency Usage | Medium | Dependency declaration vs usage analysis |
| 23 | Unified Tool Configuration | Medium | Multi-file config comparison |
| 24 | Python Version Consistency | Low | pyproject.toml version checking |

## Gap Analysis Details

### Easy to Implement (Low Complexity) - 4 rules

#### Rule 5: Package-App Discipline
**Current**: rglob-based file path checking
**AST Implementation**: Add to `_validate_dependency_direction()`
```python
def _check_package_app_discipline(self, node: ast.ImportFrom) -> None:
    # Check if file is in packages/ and importing from apps/
    if "/packages/" in str(self.context.path) and node.module:
        if node.module.startswith("apps."):
            self.add_violation(
                "rule-5",
                "Package-App Discipline",
                node.lineno,
                f"Package cannot import from app: {node.module}"
            )
```
**Effort**: 30 minutes

#### Rule 13: Inherit-Extend Pattern
**Current**: Directory structure validation (packages/ vs apps/)
**AST Implementation**: Can be checked during file context creation
```python
def _validate_inherit_extend(self) -> None:
    # Check if packages/ files use inheritance patterns
    # Check if apps/ files extend package functionality
    if "/packages/" in str(self.context.path):
        # Validate that packages provide base implementations
        pass
```
**Effort**: 1 hour

#### Rule 14: Package Naming Consistency
**Current**: String pattern matching for hive-* naming
**AST Implementation**: File path pattern validation
```python
def _validate_package_naming(self) -> None:
    if "/packages/" in str(self.context.path):
        package_dir = self.context.path.parts[self.context.path.parts.index("packages") + 1]
        if not package_dir.startswith("hive-"):
            self.add_violation(
                "rule-14",
                "Package Naming",
                1,
                f"Package directory must start with 'hive-': {package_dir}"
            )
```
**Effort**: 30 minutes

#### Rule 24: Python Version Consistency
**Current**: Parse pyproject.toml across packages
**AST Implementation**: TOML parsing during project-level validation
```python
def _validate_python_version(self) -> None:
    # Read pyproject.toml files and compare python versions
    # This is project-level, not file-level validation
    pass
```
**Effort**: 1 hour

### Medium Complexity - 5 rules

#### Rule 4: Single Config Source
**Current**: Detect duplicate config patterns across files
**Challenge**: Requires cross-file state tracking
**AST Implementation**: Track config definitions globally
```python
class EnhancedValidator:
    def __init__(self):
        self.config_sources = {}  # Track config definitions

    def _check_config_source(self, node: ast.Assign) -> None:
        # Track config variable assignments
        # Flag duplicates across files
        pass
```
**Effort**: 2-3 hours

#### Rule 7: Service Layer Discipline
**Current**: Pattern matching for service layer usage
**Challenge**: Architecture pattern detection
**AST Implementation**: Track service layer patterns
```python
def _validate_service_layer(self, node: ast.ClassDef) -> None:
    # Check for proper service layer patterns
    # Validate dependency injection usage
    pass
```
**Effort**: 2-3 hours

#### Rule 16: CLI Pattern Consistency
**Current**: Validate CLI command patterns
**Challenge**: Command pattern detection
**AST Implementation**: Detect CLI frameworks and validate patterns
```python
def _validate_cli_patterns(self, node: ast.FunctionDef) -> None:
    # Detect click/typer decorators
    # Validate command structure
    pass
```
**Effort**: 2-3 hours

#### Rule 22: Pyproject Dependency Usage
**Current**: Cross-reference declared vs used dependencies
**Challenge**: Requires import tracking and TOML parsing
**AST Implementation**: Track all imports, compare with pyproject.toml
```python
class EnhancedValidator:
    def __init__(self):
        self.imports_used = set()  # Track all imports

    def _validate_dependency_usage(self) -> None:
        # Compare self.imports_used with pyproject.toml dependencies
        pass
```
**Effort**: 3-4 hours

#### Rule 23: Unified Tool Configuration
**Current**: Compare tool configs across packages
**Challenge**: Multi-file TOML comparison
**AST Implementation**: Project-level validation
```python
def _validate_unified_tools(self) -> None:
    # Read all pyproject.toml files
    # Compare [tool.*] sections
    pass
```
**Effort**: 2-3 hours

### High Complexity - 1 rule

#### Rule 18: Test Coverage Mapping
**Current**: Cross-reference test files with source files
**Challenge**: Requires understanding test-source relationships
**AST Implementation**: Build test coverage map
```python
class EnhancedValidator:
    def __init__(self):
        self.source_files = set()
        self.test_files = set()

    def _validate_test_coverage_mapping(self) -> None:
        # Map test files to source files
        # Detect missing test files
        pass
```
**Effort**: 4-6 hours

## Implementation Priority

### Phase 1: Low-Hanging Fruit (3-4 hours)
1. Rule 5: Package-App Discipline (30 min)
2. Rule 14: Package Naming Consistency (30 min)
3. Rule 13: Inherit-Extend Pattern (1 hour)
4. Rule 24: Python Version Consistency (1 hour)

### Phase 2: Medium Complexity (10-15 hours)
5. Rule 4: Single Config Source (2-3 hours)
6. Rule 7: Service Layer Discipline (2-3 hours)
7. Rule 16: CLI Pattern Consistency (2-3 hours)
8. Rule 22: Pyproject Dependency Usage (3-4 hours)
9. Rule 23: Unified Tool Configuration (2-3 hours)

### Phase 3: High Complexity (4-6 hours)
10. Rule 18: Test Coverage Mapping (4-6 hours)

## Architectural Considerations

### Cross-File State Tracking
Many rules require tracking state across multiple files:
- Config source tracking (Rule 4)
- Import dependency mapping (Rule 22)
- Tool configuration comparison (Rule 23)
- Test coverage mapping (Rule 18)

**Solution**: Add project-level validation phase
```python
class EnhancedValidator:
    def validate_project(self, project_root: Path) -> ValidationResult:
        # Phase 1: Per-file AST validation
        for file in all_files:
            self.validate_file(file)

        # Phase 2: Cross-file project validation
        self._validate_cross_file_rules()

        return self.results
```

### TOML Configuration Parsing
Multiple rules require pyproject.toml parsing:
- Python version consistency (Rule 24)
- Dependency usage (Rule 22)
- Unified tool configuration (Rule 23)

**Solution**: Add TOML parsing utility
```python
from toml import load

class ProjectConfigValidator:
    def __init__(self, project_root: Path):
        self.configs = self._load_all_pyproject_tomls(project_root)

    def validate_python_versions(self) -> list[Violation]:
        # Compare python versions across all pyproject.toml files
        pass
```

## Performance Impact

### Current Performance
- Single-pass AST: ~10-15s for full codebase (638 files)
- Rglob-based: ~30-60s for full codebase

### With All Rules Implemented
- **Phase 1 (file-level)**: ~10-15s (no change, simple AST checks)
- **Phase 2 (project-level)**: +5-10s (cross-file analysis, TOML parsing)
- **Total Estimated**: ~15-25s (still 2-3x faster than current system)

### Optimization Strategies
1. **Lazy TOML Loading**: Only parse pyproject.toml when needed
2. **Parallel File Validation**: Process files concurrently
3. **Smart Caching**: Cache project-level analysis results
4. **Incremental Validation**: Skip project-level checks for single-file changes

## Recommendation

**Start with Phase 1**: Implement the 4 low-hanging fruit rules to build momentum and validate the AST validator architecture. This provides ~40% rule coverage increase for minimal effort.

**Then Phase 2**: Tackle medium-complexity rules one at a time, building up the cross-file validation infrastructure incrementally.

**Finally Phase 3**: Implement test coverage mapping once the architecture is proven stable.