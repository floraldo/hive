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

### Automated Code-Fixing Scripts (CRITICAL)
**Context**: Emergency syntax fixer corrupted codebase (2025-10-03)

**⚠️ BANNED: Regex-Based Code Modification**

NEVER use broad regex patterns for structural code changes:
```python
# ❌ CATASTROPHIC - These patterns DESTROYED the codebase:
pattern = r"([^,\n]+)\n(\s+[^,\n]+)"  # Matches EVERYTHING
pattern = r"(\w+)\n(\s+)(\w+)"         # No context awareness
pattern = r"([a-zA-Z_][a-zA-Z0-9_]*)\n(\s+[a-zA-Z_])"  # Overly broad
```

**✅ REQUIRED: AST-Based Approach**

```python
import ast

def fix_with_ast(filepath: Path) -> bool:
    """Safe code fixing with structure validation."""
    with open(filepath) as f:
        content = f.read()

    # Parse original structure
    try:
        original_tree = ast.parse(content)
    except SyntaxError:
        pass  # OK if already broken

    # Apply fixes using AST visitors (context-aware)
    # ... (specific pattern fixes)

    # Validate result
    try:
        new_tree = ast.parse(fixed_content)
        # Compare structure - fail if unexpected changes
        if original_tree and structure_changed(original_tree, new_tree):
            return False  # ABORT
    except SyntaxError:
        return False  # ABORT - introduced errors

    return True
```

**MANDATORY Pre-Flight Checklist**:
1. Test on 5 sample files manually
2. Validate AST structure preservation
3. Run syntax check on results
4. Create backups before bulk run
5. Fail fast on any unexpected changes

**🚫 BANNED SCRIPTS** (Quarantined in `scripts/archive/DANGEROUS_FIXERS/`):
- `modernize_type_hints.py` - Regex-based type hint conversion (caused ListTuple typo, misplaced imports)
- `emergency_syntax_fix_consolidated.py` - Regex-based comma fixer (added commas everywhere)
- `code_fixers.py` - Regex-based general fixer (unsafe patterns)

**See**:
- `scripts/archive/DANGEROUS_FIXERS/WARNING.md` - Complete danger documentation
- `claudedocs/archive/syntax-fixes/emergency_fixer_root_cause_analysis.md` - Trailing comma incident
- `claudedocs/active/incidents/type_hint_modernizer_incident.md` - Type hint incident

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

### Import Pattern Rules (CRITICAL)
**Pattern**: Three-layer architecture - packages → app.core → app business logic

**✅ ALWAYS ALLOWED**:
```python
# 1. Package imports (infrastructure layer)
from hive_logging import get_logger
from hive_config import create_config_from_sources
from hive_db import get_sqlite_connection
from hive_bus import BaseBus

# 2. Same app imports (within app boundary)
from ecosystemiser.core.bus import get_ecosystemiser_event_bus
from ecosystemiser.services.solver import run_optimization

# 3. App.core extensions (inherit→extend pattern)
from hive_bus import BaseBus  # Inherit from package

class MyAppEventBus(BaseBus):  # Extend in app.core
    """Add app-specific event handling"""
    pass
```

**✅ ORCHESTRATION PACKAGE** (Recommended):
```python
# hive-orchestration provides shared orchestration infrastructure
# All apps may use this package
from hive_orchestration import create_task, get_client, Task, TaskStatus

# Or use client SDK (recommended)
client = get_client()
task_id = client.create_task("My Task", "analysis")

# OLD DEPRECATED: hive_orchestrator.core.db (DO NOT USE)
```

**❌ NEVER ALLOWED**:
```python
# Cross-app business logic imports (FORBIDDEN)
from ecosystemiser.services.solver import optimize  # ❌ FORBIDDEN
from ai_planner.services.planning import create_plan  # ❌ FORBIDDEN
from guardian_agent.core.cost import CostTracker  # ❌ FORBIDDEN (not platform app)
```

**Decision Tree**:
- Need package utility? → ✅ Import from `hive_*` package
- Need app-specific extension? → ✅ Import from `app.core`
- Need same app logic? → ✅ Import from `app.services`
- Need orchestration? → ✅ Import from `hive_orchestration` package
- Need other app logic? → ❌ Use `hive-bus` events or extract to package

**Full Documentation**: `.claude/ARCHITECTURE_PATTERNS.md`

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
- **ERROR** (9 rules): Technical debt, maintainability - Fix before PR
- **WARNING** (7 rules): Quality issues, test coverage - Fix at sprint boundaries
- **INFO** (3 rules): Best practices - Fix at major releases

**Total**: 24 Golden Rules actively enforced (all currently passing)

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

## 🧹 Boy Scout Rule: Incremental Technical Debt Reduction

**Philosophy**: "Always leave the code cleaner than you found it"

**The Rule**: When editing ANY file, fix its linting violations before committing.

**Enforcement**: `packages/hive-tests/tests/unit/test_boy_scout_rule.py`
- Tracks total violation count (baseline: 1733 as of 2025-10-04)
- **Test fails if violations increase** ❌
- Test celebrates when violations decrease ✅

**Workflow**:
```bash
# Auto-fix on save (via .vscode/settings.json)
# OR manually: ruff check <file> --fix
git commit  # Pre-commit hooks validate
```

**Progress**: ~1,700 violations → 0 (achieved incrementally via natural development)

## 🏆 Golden Rules (27 Architectural Validators)

**Status**: All 27 rules PASSING (100% compliance at INFO level)
**Enforcement**: AST-based validation via `packages/hive-tests/src/hive_tests/architectural_validators.py`

### CRITICAL Rules (5 rules - Always Enforced)
1. **No sys.path Manipulation** - Use proper package imports
2. **Single Config Source** - No setup.py/pyproject.toml conflicts
3. **No Hardcoded Env Values** - Use configuration management
4. **Package vs. App Discipline** - Maintain layer separation
5. **App Contracts** - Respect inter-app boundaries

### ERROR Rules (9 rules - Fix Before PR)
6. **Dependency Direction** - packages/ cannot import from apps/
7. **Graph-Based Dependency Analysis** - Use hive-graph for dependency tracking
8. **Error Handling Standards** - Proper try/catch blocks with hive_errors
9. **Logging Standards** - Use `hive_logging` instead of print()
10. **No Global State Access** - Avoid shared mutable state
11. **Async Pattern Consistency** - Use `hive_async` for concurrent operations
12. **Interface Contracts** - Cross-component imports via interfaces
13. **Communication Patterns** - Use hive-bus for inter-component messaging
14. **Service Layer Discipline** - Maintain clean service boundaries

### WARNING Rules (8 rules - Fix at Sprint Boundaries)
15. **Test Coverage Mapping** - Track test coverage for all modules
16. **Test File Quality** - Tests follow platform conventions
17. **Inherit-Extend Pattern** - Follow inherit from packages, extend in apps
18. **Package Naming Consistency** - Use hive-* naming for all packages
19. **Development Tools Consistency** - Consistent tooling across components
20. **CLI Pattern Consistency** - Uniform CLI patterns for all apps
21. **Pyproject Dependency Usage** - Use Poetry for dependency management

### INFO Rules (5 rules - Fix at Major Releases)
22. **Unified Tool Configuration** - Centralized tool config in pyproject.toml
23. **Python Version Consistency** - All components use Python ^3.11
24. **Colocated Tests** - Tests live near the code they test

**Validation Commands**:
```bash
# CRITICAL only (rapid development)
python scripts/validation/validate_golden_rules.py --level CRITICAL

# CRITICAL + ERROR (before PR - default)
python scripts/validation/validate_golden_rules.py --level ERROR

# Include WARNING (sprint cleanup)
python scripts/validation/validate_golden_rules.py --level WARNING

# All rules (release validation)
python scripts/validation/validate_golden_rules.py --level INFO
```

### Future Validators (PLANNED - Not Yet Implemented)
The following validators are documented but NOT in the active registry:

**Environment Isolation Validators** (see `environment_validator.py`):
- No conda references in production code
- No hardcoded absolute paths
- Poetry lockfile validation
- Multi-language toolchain checks

**Config Consistency Validators** (see `config_validator.py`):
- Ruff configuration in all pyproject.toml
- Pytest configuration format consistency

**Unified Config Enforcement** (Golden Rule 37 - see `claudedocs/golden_rule_37_implementation_plan.md`):
- Enforce all config loading through hive-config
- Detect os.getenv() outside config package
- Prevent config file I/O bypassing unified system

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

### 🎯 Master Agent Git Workflow (CRITICAL)

**Rule**: Master Agent (orchestrator/lead engineer) **ALWAYS commits directly to `main`**

**Rationale**:
- Master Agent coordinates quality infrastructure and strategic work
- Creates checkpoints for parallel agents to build upon
- Maintains platform stability through controlled, validated commits
- Feature branches used only for testing CI/CD workflows (like Golden Gates validation)

**Standard Pattern**:
```bash
# Master Agent standard workflow (ON MAIN BRANCH)
git checkout main
git pull origin main

# Make changes (infrastructure, quality gates, coordination)
# ...

# Commit directly to main
git add <files>
git commit -m "feat(ci): description"  # Pre-commit validates
git push origin main  # Triggers CI/CD for validation
```

**When to Use Branches** (Master Agent):
- **Testing CI/CD workflows only**: `git checkout -b test-ci-pipeline`
- **NOT for regular development work**

---

### ✨ Golden Workflow: The Boy Scout Rule

**Philosophy**: "Leave the code cleaner than you found it"

#### Core Principles
1. **Fix Before Feature**: Clean up linting violations before adding new code
2. **No Bypass**: NEVER use `--no-verify` to skip pre-commit hooks (except infrastructure commits)
3. **Format on Save**: IDE auto-fixes violations during development
4. **Commit Clean**: All commits pass pre-commit hooks without manual intervention

#### Standard Workflow
```bash
# 1. Start work (ensure clean baseline)
git status && git checkout -b feature/my-feature

# 2. Develop (with auto-formatting)
# - VSCode auto-formats on save
# - Ruff fixes violations automatically
# - Focus on logic, not formatting

# 3. Stage your changes
git add modified_files.py

# 4. Apply Boy Scout Rule (INTENTIONAL auto-fix)
bash scripts/maintenance/fix-staged-files.sh
# This runs ruff --fix ONLY on staged files
# Makes cleanup visible and intentional

# 5. Review the fixes (optional but recommended)
git diff --cached

# 6. Commit (Golden Workflow - NO --no-verify)
git commit -m "feat: description"  # Pre-commit runs automatically

# Result: Commit passes cleanly, codebase improved incrementally
```

#### Why This Workflow Works
- **Pre-commit runs on staged files only** - Fast and targeted
- **fix-staged-files.sh makes auto-fix intentional** - No surprises
- **Incremental cleanup** - Each commit leaves code cleaner
- **--no-verify is unnecessary** - Workflow handles all cases

#### Linting Debt Management
When inheriting code with violations:
```bash
# Pay off debt FIRST (separate commit)
ruff check . --fix
git commit -m "chore(lint): Pay off linting debt - 185 violations fixed"

# THEN add new features (clean slate)
git checkout -b feature/my-feature
# Work with clean baseline
```

#### Pre-commit Hook Configuration
**File**: `.pre-commit-config.yaml`
```yaml
repos:
  - repo: local
    hooks:
      - id: ruff-check
        name: Ruff linting
        entry: ruff check --fix
        language: system
        types: [python]

      - id: golden-rules-check
        name: Validate Golden Rules compliance
        entry: python scripts/validation/validate_golden_rules.py --level CRITICAL
        language: system
        pass_filenames: false
```

**Setup**:
```bash
pip install pre-commit
pre-commit install  # One-time setup
```

#### IDE Configuration (VSCode)
**File**: `.vscode/settings.json`
```json
{
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.fixAll": "explicit",
      "source.organizeImports": "explicit"
    }
  },
  "ruff.lint.run": "onSave"
}
```

**Result**: Violations fixed during development, not at commit time

#### Quality Without Friction
- **Development**: Ruff auto-fixes on save → zero manual formatting
- **Commit**: Pre-commit validates → catches edge cases
- **CI/CD**: Final gate → ensures nothing slipped through

**Remember**: Format early, format often. Never bypass quality gates.

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
