# Rule 37 Migration Strategy: Unified Config Enforcement

**Created**: 2025-10-04
**Status**: Planning Phase
**Priority**: ERROR-level (must fix before PR merge)
**Total Violations**: 23 in production code

## Overview

Rule 37 enforces that all configuration access must go through the `hive-config` package. Currently, 23 production code locations directly access environment variables using `os.getenv()` or `os.environ.get()`, bypassing the unified configuration system.

## Violation Inventory

### Apps (11 violations)

#### 1. apps/ecosystemiser (1 violation)
**File**: `src/ecosystemiser/core/db.py`
**Violation**:
```python
db_path_env = os.environ.get("ECOSYSTEMISER_DB_PATH")
```
**Severity**: Medium
**Migration**: Use `hive_config` database configuration
**Estimated Effort**: 15 minutes

#### 2. apps/guardian-agent (1 violation)
**File**: `src/guardian_agent/core/config.py`
**Violation**:
```python
self.openai_api_key = os.getenv("OPENAI_API_KEY")
```
**Severity**: High (API credentials)
**Migration**: Use `hive_config` secrets management
**Estimated Effort**: 20 minutes

#### 3. apps/hive-architect (7 violations)
**File**: `src/hive_architect/config.py`
**Violations**:
```python
default_factory=lambda: os.getenv("ENVIRONMENT", "development")
default_factory=lambda: os.getenv("HOST", "0.0.0.0")
default_factory=lambda: int(os.getenv("PORT", "8000"))
default_factory=lambda: os.getenv("LOG_LEVEL", "INFO")
default_factory=lambda: os.getenv("DATABASE_PATH", "data/hive-architect.db")
default_factory=lambda: os.getenv("CACHE_ENABLED", "true").lower() == "true"
default_factory=lambda: int(os.getenv("CACHE_TTL", "3600"))
```
**Severity**: High (entire app config)
**Migration**: Full refactor to use `hive_config.create_config_from_sources()`
**Estimated Effort**: 1-2 hours

#### 4. apps/hive-orchestrator (2 violations)
**File**: `src/hive_orchestrator/async_worker.py`
**Violation**:
```python
claude_bin = os.environ.get("CLAUDE_BIN")
```
**Severity**: Low (tool path)
**Migration**: Use `hive_config` tool configuration

**File**: `src/hive_orchestrator/hive_status.py`
**Violation**:
```python
config["use_emoji"] = os.environ.get("HIVE_EMOJI", "1") != "0"
```
**Severity**: Low (UI preference)
**Migration**: Use `hive_config` UI settings
**Estimated Effort**: 30 minutes (both files)

### Packages (12 violations)

#### 5. packages/hive-ai (1 violation)
**File**: `src/hive_ai/tools/web_search.py`
**Violation**:
```python
self.api_key = api_key or os.getenv("EXA_API_KEY")
```
**Severity**: High (API credentials)
**Migration**: Use `hive_config` secrets management
**Estimated Effort**: 15 minutes

#### 6. packages/hive-cache (1 violation)
**File**: `src/hive_cache/config.py`
**Violation**:
```python
if env_value := os.getenv(env_var):
```
**Severity**: Medium (cache configuration)
**Migration**: Use `hive_config` cache settings
**Estimated Effort**: 20 minutes

#### 7. packages/hive-deployment (7 violations)
**File**: `src/hive_deployment/deployment.py`
**Violations**:
```python
"base_remote_apps_dir": os.environ.get("BASE_REMOTE_APPS_DIR", "/home/deploy/apps")
"nginx_conf_d_dir": os.environ.get("NGINX_CONF_D_DIR", "/etc/nginx/conf.d")
"systemd_service_dir": os.environ.get("SYSTEMD_SERVICE_DIR", "/etc/systemd/system")
"server_user": os.environ.get("SERVER_USER", "deploy")
"nginx_user_group": os.environ.get("NGINX_USER_GROUP", "www-data")
base_url = os.environ.get("BASE_URL")  # 2 occurrences
```
**Severity**: Medium (deployment configuration)
**Migration**: Use `hive_config` deployment settings
**Estimated Effort**: 45 minutes

#### 8. packages/hive-logging (2 violations)
**File**: `src/hive_logging/logger.py`
**Violations**:
```python
log_level = os.environ.get("LOG_LEVEL", level).upper()  # Line 1
log_level = level or os.environ.get("LOG_LEVEL", "INFO").upper()  # Line 2
```
**Severity**: Medium (logging configuration)
**Migration**: Use `hive_config` logging settings
**Estimated Effort**: 20 minutes

#### 9. packages/hive-service-discovery (1 violation)
**File**: `src/hive_service_discovery/config.py`
**Violation**:
```python
if env_value := os.getenv(env_var):
```
**Severity**: Medium (service discovery config)
**Migration**: Use `hive_config` service settings
**Estimated Effort**: 20 minutes

## Migration Approach

### Pattern 1: Simple Environment Variable Replacement

**Before**:
```python
import os

api_key = os.getenv("OPENAI_API_KEY")
```

**After**:
```python
from hive_config import create_config_from_sources

config = create_config_from_sources()
api_key = config.ai.openai_api_key
```

### Pattern 2: Default Values

**Before**:
```python
log_level = os.getenv("LOG_LEVEL", "INFO")
```

**After**:
```python
from hive_config import create_config_from_sources

config = create_config_from_sources()
log_level = config.logging.level  # Default handled in hive_config schema
```

### Pattern 3: Dependency Injection (Recommended)

**Before**:
```python
class MyService:
    def __init__(self):
        self.api_key = os.getenv("API_KEY")
```

**After**:
```python
from hive_config import HiveConfig, create_config_from_sources

class MyService:
    def __init__(self, config: HiveConfig | None = None):
        self._config = config or create_config_from_sources()
        self.api_key = self._config.ai.api_key
```

### Pattern 4: Config Dataclass (hive-architect style)

**Before**:
```python
@dataclass
class AppConfig:
    host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
```

**After**:
```python
from hive_config import create_config_from_sources

@dataclass
class AppConfig:
    host: str
    port: int

    @classmethod
    def from_hive_config(cls):
        config = create_config_from_sources()
        return cls(
            host=config.server.host,
            port=config.server.port,
        )
```

## Migration Phases

### Phase 1: Low-Hanging Fruit (3-4 hours)
**Priority**: HIGH
**Components**: Simple replacements with minimal dependencies

1. ✅ **hive-ai/web_search.py** (1 violation)
   - Replace: `os.getenv("EXA_API_KEY")` → `config.ai.exa_api_key`

2. ✅ **hive-logging/logger.py** (2 violations)
   - Replace: `os.environ.get("LOG_LEVEL")` → `config.logging.level`

3. ✅ **hive-orchestrator/async_worker.py** (1 violation)
   - Replace: `os.environ.get("CLAUDE_BIN")` → `config.tools.claude_bin`

4. ✅ **hive-orchestrator/hive_status.py** (1 violation)
   - Replace: `os.environ.get("HIVE_EMOJI")` → `config.ui.use_emoji`

**Total**: 5 violations | **Estimated Time**: 1.5 hours

### Phase 2: Medium Complexity (4-6 hours)
**Priority**: MEDIUM
**Components**: Refactoring with config schema updates

1. ✅ **ecosystemiser/core/db.py** (1 violation)
   - Add database config to hive_config schema
   - Replace: `os.environ.get("ECOSYSTEMISER_DB_PATH")` → `config.database.ecosystemiser_path`

2. ✅ **guardian-agent/core/config.py** (1 violation)
   - Add OpenAI config to hive_config schema
   - Replace: `os.getenv("OPENAI_API_KEY")` → `config.ai.openai_api_key`

3. ✅ **hive-cache/config.py** (1 violation)
   - Refactor cache config to use hive_config

4. ✅ **hive-deployment/deployment.py** (7 violations)
   - Create deployment config section in hive_config
   - Comprehensive refactor of deployment settings

5. ✅ **hive-service-discovery/config.py** (1 violation)
   - Refactor service discovery to use hive_config

**Total**: 11 violations | **Estimated Time**: 4 hours

### Phase 3: Complex Refactoring (6-8 hours)
**Priority**: HIGH (blocks entire app)
**Components**: Full architectural refactor

1. ✅ **hive-architect/config.py** (7 violations)
   - Complete refactor from custom config to hive_config
   - Update all dependencies to use DI pattern
   - Test all hive-architect functionality
   - Update documentation

**Total**: 7 violations | **Estimated Time**: 6 hours

## hive-config Schema Extensions Required

### New Configuration Sections Needed:

```python
# packages/hive-config/src/hive_config/models.py

@dataclass
class AIConfig:
    """AI service configuration"""
    openai_api_key: str | None = None
    exa_api_key: str | None = None
    # ... existing fields

@dataclass
class DeploymentConfig:
    """Deployment configuration"""
    base_remote_apps_dir: str = "/home/deploy/apps"
    nginx_conf_d_dir: str = "/etc/nginx/conf.d"
    systemd_service_dir: str = "/etc/systemd/system"
    server_user: str = "deploy"
    nginx_user_group: str = "www-data"
    base_url: str | None = None

@dataclass
class UIConfig:
    """UI preferences"""
    use_emoji: bool = True

@dataclass
class ToolsConfig:
    """External tool paths"""
    claude_bin: str | None = None

@dataclass
class HiveConfig:
    # ... existing fields
    ai: AIConfig
    deployment: DeploymentConfig
    ui: UIConfig
    tools: ToolsConfig
```

## Testing Strategy

### Unit Tests
- Test each migrated component with mock configs
- Verify default values work correctly
- Test environment variable overrides still work

### Integration Tests
- Test full application startup with hive_config
- Verify all services can access configuration
- Test configuration precedence (env > file > defaults)

### Validation
- Run Golden Rules validation after each phase
- Confirm Rule 37 violations decrease
- Ensure no regressions in existing functionality

## Rollback Plan

Each phase should:
1. Create feature branch: `fix/rule-37-phase-{1,2,3}`
2. Implement migrations for phase components
3. Test thoroughly before merge
4. Merge to main only after validation

If issues arise:
- Git revert specific commits
- Phase-by-phase rollback prevents total system failure
- Keep old code commented during transition period

## Success Criteria

- ✅ Zero `os.getenv()`/`os.environ.get()` calls in production code
- ✅ All configurations accessible via `hive-config`
- ✅ Rule 37 validation passes
- ✅ All existing tests pass
- ✅ Documentation updated with new patterns

## Timeline Estimate

| Phase | Duration | Components | Violations Fixed |
|-------|----------|------------|------------------|
| Phase 1 | 1.5 hrs | Simple replacements | 5 |
| Phase 2 | 4 hrs | Medium refactors | 11 |
| Phase 3 | 6 hrs | hive-architect | 7 |
| **Total** | **11.5 hrs** | **9 components** | **23** |

## Risk Assessment

### High Risk:
- **hive-architect refactor**: Entire app config system change
- **API credentials**: Potential security issues if misconfigured

### Medium Risk:
- **Deployment config**: Could break production deployments
- **Logging config**: Could break observability

### Low Risk:
- **UI preferences**: Non-critical features
- **Tool paths**: Fallback mechanisms exist

## Dependencies

**Blocked By**:
- AST validator trailing comma bugs (prevents automated violation detection)

**Blocks**:
- Rule 37 enforcement in pre-commit hooks
- Complete Golden Rules compliance

## References

- **hive-config API**: `packages/hive-config/README.md`
- **DI Pattern Gold Standard**: `apps/ecosystemiser/src/ecosystemiser/config/bridge.py`
- **Configuration Migration Guide**: `claudedocs/config_migration_guide_comprehensive.md`
- **Golden Rule 37 Implementation**: `packages/hive-tests/src/hive_tests/ast_validator.py:604-656`
