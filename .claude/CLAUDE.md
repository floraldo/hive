# Hive Platform - Claude Development Guide

**Architecture**: Modular monolith with inherit→extend pattern
**Mission**: Energy system optimization platform with AI-powered analysis
**Key Files**: See `.claude/rules.md`, `.claude/project.yaml`, `.claude/ignore`

## 🏗️ Core Architecture

### Modular Monolith Pattern
- **packages/** = Infrastructure (inherit layer) - shared utilities, logging, caching, DB
- **apps/** = Business logic (extend layer) - ecosystemiser, hive-orchestrator, ai-planner
- **Dependency flow**: apps → packages, apps → app.core (never package → app)

### Platform Components
- **EcoSystemiser**: Energy system modeling and optimization engine
- **AI-Planner**: Intelligent planning and forecasting
- **AI-Reviewer**: Code review and quality assurance
- **Hive-Orchestrator**: Multi-service coordination and workflow management
- **QR-Service**: Quick response and notification system

## 🚫 Critical Rules - CODE RED COMPLIANCE

### Python Syntax Error Prevention (CRITICAL)
**Context**: After Code Red Stabilization Sprint fixing 200+ comma syntax errors

**MANDATORY COMMA CHECKS**:
```python
# CORRECT - Multi-line function definitions
def __init__(
    self,
    message: str,
    component: str = "default",  # COMMA REQUIRED
    operation: str | None = None  # COMMA ALLOWED
):

# CORRECT - Multi-line function calls
return cls(
    event_type="started",
    payload={"key": "value"},  # COMMA REQUIRED
    **kwargs
)

# CORRECT - Multi-line dictionaries/lists
data = {
    "key1": "value1",  # COMMA REQUIRED
    "key2": "value2"   # COMMA OPTIONAL ON LAST ITEM
}
```

**VALIDATION REQUIREMENTS**:
- **Before any commit**: `python -m py_compile file.py`
- **Before PR**: `python -m pytest --collect-only` (must succeed)
- **Automated check**: `python -m ruff check` (zero syntax errors)
- **Agent validation**: Always run syntax check after multi-line edits

### Unicode in Code (CRITICAL)
- **NO Unicode symbols in code**: Use `# OK` not ✅, `# FAIL` not ❌
- **Exception**: Documentation files (.md) can use Unicode

### File Management Rules
- **Edit existing files** first, don't create new ones unless required
- **Use hive-* packages**: `from hive_logging import get_logger` not `print()`
- **Golden Rules validation**: `python scripts/validation/validate_golden_rules.py`

### Documentation Anti-Sprawl (CRITICAL)
**Problem**: Multi-agent sessions create doc sprawl (79 files before cleanup)

**RULES - Update, Don't Create**:
1. **Session summaries**: Update `claudedocs/platform_status_2025_09_30.md`, don't create new dated files
2. **Progress tracking**: Update existing progress docs, don't create `phase_X_status.md` files
3. **Agent coordination**: Use agent memory/context, not coordination log files
4. **Architecture decisions**: Update `claudedocs/architectural_fix_summary.md` or component READMEs
5. **Migration guides**: Update comprehensive guides, don't create dated snapshots

**ALLOWED New Docs** (rare):
- New architectural patterns (e.g., new golden rule implementation)
- New component certification (when component is brand new)
- Major project milestones (PROJECT_NAME_COMPLETE.md)

**README Hierarchy** (Holy - Never Skip):
- `README.md` at package/app root - REQUIRED for LLM context
- All 16 packages have READMEs - validate before creating new packages
- All apps have READMEs - validate before creating new apps
- Update package README when adding features, not separate docs

**Validation**:
```bash
# Before creating new .md in claudedocs/
ls claudedocs/*.md | grep -i "$(echo filename)" || echo "OK to create"

# Check package has README
ls packages/my-package/README.md || echo "REQUIRED - create README first"
```

### Configuration Management (CRITICAL)
**Pattern**: Dependency Injection (DI) - NO global state

**DO: Use DI Pattern** (Gold Standard from EcoSystemiser):
```python
from hive_config import HiveConfig, create_config_from_sources

class MyService:
    def __init__(self, config: HiveConfig | None = None):
        # Dependency injection with sensible default
        self._config = config or create_config_from_sources()
        self.db_path = self._config.database.path
```

**DON'T: Use Global State** (DEPRECATED):
```python
from hive_config import get_config

class MyService:
    def __init__(self):
        self.config = get_config()  # DEPRECATED - Hidden dependency!
```

**Why DI Pattern**:
- ✅ Explicit dependencies (clear in constructor signature)
- ✅ Testable (inject mock configs in tests)
- ✅ Thread-safe (no shared global state)
- ✅ Parallel-friendly (each instance isolated)

**Resources**:
- Gold Standard: `apps/ecosystemiser/src/ecosystemiser/config/bridge.py`
- API Docs: `packages/hive-config/README.md`
- Migration Guide: `claudedocs/config_migration_guide_comprehensive.md`

## 🛠️ Standard Tools & Quality Gates

### Development Tools
```toml
pytest = "^8.3.2"          # Testing framework
black = "^24.8.0"           # Code formatting
mypy = "^1.8.0"             # Static type checking
ruff = "^0.1.15"            # Fast linting and formatting
isort = "^5.13.0"           # Import sorting
```

### Quality Gates (MUST PASS)
1. **Syntax validation**: `python -m py_compile` on all modified files
2. **Test collection**: `python -m pytest --collect-only` (zero syntax errors)
3. **Linting**: `python -m ruff check` (zero violations)
4. **Golden Rules**: `python scripts/validation/validate_golden_rules.py` (severity level depends on phase)
5. **Type checking**: `python -m mypy` (on typed modules)
6. **Configuration Pattern**: Use DI (`create_config_from_sources()`), not global state (`get_config()`)

## 🎚️ Tiered Compliance System

### Development Phase Strategy
**Philosophy**: "Fast in development, tight at milestones"

#### Severity Levels
- **CRITICAL** (5 rules): System breaks, security, deployment - Always enforced
- **ERROR** (13 rules): Technical debt, maintainability - Fix before PR
- **WARNING** (20 rules): Quality issues, test coverage - Fix at sprint boundaries
- **INFO** (24 rules): Best practices - Fix at major releases

#### Usage
```bash
# Rapid development - only critical rules (~5s)
python scripts/validation/validate_golden_rules.py --level CRITICAL

# Before PR merge - critical and error rules (~15s)
python scripts/validation/validate_golden_rules.py --level ERROR

# Sprint cleanup - include warnings (~25s)
python scripts/validation/validate_golden_rules.py --level WARNING

# Production release - all rules (~30s)
python scripts/validation/validate_golden_rules.py --level INFO
```

#### Key Benefits
- **5x faster validation** during rapid prototyping (CRITICAL only)
- **Test rules at WARNING level** - tests optional during active development
- **Clear progression path** from prototype to production
- **Context-appropriate enforcement** based on development phase

See `claudedocs/golden_rules_tiered_compliance_system.md` for complete guide.

## 🏆 Golden Rules (24 Architectural Validators)

Critical platform constraints enforced by `packages/hive-tests/src/hive_tests/ast_validator.py` (AST-based validation, 100% coverage):

### Import and Dependency Rules
1. **No sys.path manipulation** - Use proper package imports
2. **No print() statements** - Use `hive_logging` instead
3. **Hive packages required** - Import from `hive_*` packages, not standard logging
4. **No direct database imports** - Use `hive_db` abstractions

### Code Quality Rules
5. **No hardcoded paths** - Use configuration management
6. **Exception handling required** - Proper try/catch blocks
7. **Type hints enforced** - Function signatures must have types
8. **Docstring compliance** - Public functions need documentation

### Architecture Rules
9. **Layer separation** - packages/ cannot import from apps/
10. **Component isolation** - Cross-component imports via interfaces
11. **Configuration centralized** - Use `hive_config` for settings
12. **Async patterns** - Use `hive_async` for concurrent operations

### Performance Rules
13. **Cache utilization** - Use `hive_cache` for expensive operations
14. **Performance monitoring** - Use `hive_performance` for metrics
15. **Resource cleanup** - Proper context managers and cleanup

### Configuration Pattern Enforcement (NEW)
24. **No deprecated configuration patterns** - Use DI (`create_config_from_sources()`), not global state (`get_config()`)
    - Severity: WARNING (transitional enforcement)
    - Migration guide: `claudedocs/config_migration_guide_comprehensive.md`
    - Gold standard: EcoSystemiser config bridge pattern

**Validation**: Run `python scripts/validation/validate_golden_rules.py` before any commit.

## 📂 Platform Architecture Deep Dive

### Package Structure
```
packages/                   # Infrastructure Layer
├── hive-ai/               # AI model integration
├── hive-async/            # Async utilities and patterns
├── hive-bus/              # Event bus and messaging
├── hive-cache/            # Caching layer (Redis, memory)
├── hive-config/           # Configuration management
├── hive-db/               # Database abstractions
├── hive-deployment/       # Deployment utilities
├── hive-errors/           # Error handling and reporting
├── hive-logging/          # Structured logging
├── hive-performance/      # Performance monitoring
├── hive-service-discovery/# Service registry and discovery
└── hive-tests/            # Testing utilities and golden rules

apps/                      # Business Logic Layer
├── ecosystemiser/         # Energy optimization engine
├── hive-orchestrator/     # Multi-service coordination
├── ai-planner/           # AI planning and forecasting
├── ai-reviewer/          # Code quality and review
└── qr-service/           # Quick response system
```

### Data Flow Architecture
1. **Request → hive-orchestrator → specific app**
2. **Apps communicate via hive-bus events**
3. **Shared data via hive-cache and hive-db**
4. **Monitoring via hive-performance and hive-logging**

## ⚡ Fleet Command System

Multi-agent coordination in tmux panes:
- **Queen (Pane 0)**: Mission orchestrator and task distribution
- **Workers (Panes 1-3)**: Specialized agents (Frontend, Backend, Infrastructure)

**Commands**:
```bash
# Direct task assignment
./scripts/fleet_send.sh send backend "[T101] Database optimization"
./scripts/hive-send --to frontend --topic task --message "UI component update"

# Fleet status and coordination
./scripts/hive-send --status
./scripts/fleet_send.sh broadcast "System maintenance in 10 minutes"
```

## 🚀 Development Workflow

### Pre-Commit Checklist
1. **Syntax check**: `python -m py_compile modified_file.py`
2. **Test collection**: `python -m pytest --collect-only`
3. **Linting**: `python -m ruff check .`
4. **Golden rules**: `python scripts/validation/validate_golden_rules.py`
5. **Type check**: `python -m mypy modified_file.py`

### Emergency Procedures
- **Code Red**: Syntax errors preventing pytest collection
  - Run systematic comma fixing scripts in `scripts/`
  - Validate with `python -m pytest --collect-only`
- **Golden Rule violations**: Use architectural validators for guidance
- **Performance degradation**: Check `hive-performance` metrics

**Remember**: Build on what exists. Follow inherit→extend. Keep it simple.

## 🤖 AI Agent Quality Guidelines

### Light Touch Quality Control
**Philosophy**: Trust tooling, not manual checks. Focus on logic, not formatting.

**Automated Quality**:
- **Pre-commit hooks**: Run `pre-commit install` once to enable auto-checking
- **Formatters**: Let ruff and black handle all formatting automatically
- **Emergency fix**: `python scripts/emergency_syntax_fix.py` for bulk comma fixes
- **No manual editing**: Never manually edit commas - use tools instead

**When Writing Multi-line Code**:
- Trust formatters to add trailing commas
- Use IDE/editor auto-formatting features
- If syntax error occurs, run `ruff --fix` to auto-repair
- Focus on implementation logic, not syntax details

**Quality Without Friction**:
- Ruff checks on save (if configured)
- Black formats on commit (via pre-commit)
- Syntax validation in CI/CD pipeline
- Emergency fixes available but rarely needed
