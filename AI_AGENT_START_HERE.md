# AI Agent Onboarding Guide - Hive Platform

**Read this first**: 5-minute essential guide for AI coding agents working on the Hive platform.

## Platform Overview

**Architecture**: Modular monolith with inherit→extend pattern
**Mission**: Energy system optimization platform with AI-powered analysis
**Languages**: Python 3.11 (primary), Node.js, Rust, Julia, Go (future)
**Environment**: Hybrid Conda + Poetry setup

## Essential Reading (Priority Order)

1. **`.claude/CLAUDE.md`** - Complete development guide with golden rules
2. **`ARCHITECTURE.md`** - Platform architecture and component structure
3. **`README.md`** - Project overview and quick start
4. **`ENVIRONMENT_HARDENING_COMPLETE.md`** - Multi-language setup details
5. **`CONFIGURATION_HARDENING_COMPLETE.md`** - Configuration standards

## Quick Setup Commands

### Environment Setup
```bash
# 1. Create conda environment with all languages
conda env create -f environment.yml
conda activate hive

# 2. Verify environment
bash scripts/validation/validate_environment.sh

# 3. Install Python dependencies
poetry install

# 4. Verify configuration
python packages/hive-tests/src/hive_tests/config_validator.py
```

### Pre-Flight Validation (Before ANY Changes)
```bash
# Check git status and branch
git status && git branch

# Validate golden rules (fast, critical only)
python scripts/validation/validate_golden_rules.py --level CRITICAL

# Syntax check (before commits)
python -m pytest --collect-only
```

## Critical Golden Rules (MUST READ)

### Python Syntax (CRITICAL)
- **ALWAYS** use trailing commas in multi-line function calls/definitions
- **NEVER** use broad regex patterns for code modification (use AST-based tools)
- **ALWAYS** run `python -m py_compile file.py` after multi-line edits

### Environment Isolation (Rules 25-30)
- **Rule 25 (CRITICAL)**: No conda references in production code
- **Rule 26 (ERROR)**: No hardcoded absolute paths (use environment variables)
- **Rule 27 (ERROR)**: All pyproject.toml must use `python = "^3.11"`
- **Rule 30 (WARNING)**: Use environment variables for configuration

### Configuration Consistency (Rules 31-33)
- **Rule 31 (ERROR)**: All pyproject.toml must have [tool.ruff] section
- **Rule 32 (ERROR)**: All pyproject.toml must specify `python = "^3.11"`
- **Rule 33 (WARNING)**: Pytest configuration must use consistent format

### Architecture (CRITICAL)
- **Inherit→Extend Pattern**: packages/ (infrastructure) → apps/ (business logic)
- **Dependency Injection**: Use `create_config_from_sources()`, NOT `get_config()`
- **Import Rules**: Apps import from packages, NEVER cross-app imports
- **Layer Separation**: packages/ NEVER import from apps/

## Configuration Standards

### New Package/App Template
Use `pyproject.base.toml` as reference for all new packages/apps:
```toml
[tool.poetry.dependencies]
python = "^3.11"  # REQUIRED

[tool.ruff]
line-length = 120
target-version = "py311"

[tool.ruff.format]
skip-magic-trailing-comma = true  # CRITICAL: Prevents syntax errors

[tool.ruff.lint.isort]
split-on-trailing-comma = false  # CRITICAL: Prevents syntax errors
```

### Pre-Commit Hook Strategy
- **Pre-commit**: `--level CRITICAL` (~6-7s total)
- **Before PR**: `--level ERROR` (~15s)
- **Sprint cleanup**: `--level WARNING` (~25s)
- **Production**: `--level INFO` (~30s, all rules)

## Golden Workflow: The Boy Scout Rule

**Philosophy**: "Leave the code cleaner than you found it"

### Core Workflow
```bash
# 1. Pay off linting debt FIRST (if inheriting dirty code)
ruff check . --fix
git commit -m "chore(lint): Pay off linting debt"

# 2. Create feature branch
git checkout -b feature/my-feature

# 3. Develop with auto-formatting
# - VSCode auto-formats on save (ruff configured)
# - No manual formatting needed
# - Focus on logic, not style

# 4. Commit WITHOUT --no-verify
git add modified_files.py
git commit -m "feat: description"  # Pre-commit runs automatically
```

### NEVER Do This
```bash
git commit --no-verify  # ❌ FORBIDDEN - Bypasses quality gates
```

### IDE Auto-Formatting Setup
**File**: `.vscode/settings.json` (already configured)
- Ruff formats on save
- Auto-fixes violations during development
- Organizes imports automatically

**Result**: Clean commits by default, zero manual formatting

### When Pre-commit Fails
```bash
# Fix violations automatically
ruff check . --fix

# Re-commit (will pass)
git add .
git commit -m "feat: description"
```

**See**: `.claude/CLAUDE.md` → "Golden Workflow" for complete guide

## Architecture Patterns

### Three-Layer Architecture
```
packages/           # Infrastructure (inherit layer)
├── hive-logging/   # Use: from hive_logging import get_logger
├── hive-config/    # Use: create_config_from_sources()
├── hive-db/        # Use: from hive_db import get_sqlite_connection
└── ...

apps/               # Business logic (extend layer)
├── ecosystemiser/  # Energy optimization
├── hive-orchestrator/  # Multi-service coordination
├── ai-planner/     # AI planning and forecasting
└── ...
```

### Dependency Flow Rules
✅ **ALLOWED**:
- Apps → packages (infrastructure utilities)
- Apps → same app (internal imports)
- Apps → hive_orchestration package (shared orchestration)

❌ **FORBIDDEN**:
- Packages → apps (violates inherit→extend)
- App → other app (use hive-bus events instead)
- Cross-app business logic imports

## Common Operations

### Running Tests
```bash
# Collect tests (syntax validation)
python -m pytest --collect-only

# Run specific package tests
cd packages/hive-config && poetry run pytest

# Run app tests
cd apps/ecosystemiser && poetry run pytest
```

### Code Quality Checks
```bash
# Linting (fast)
python -m ruff check .

# Formatting
python -m black .

# Type checking
python -m mypy packages/hive-config/src/hive_config/
```

### Golden Rules Validation
```bash
# Fast validation (pre-commit)
python scripts/validation/validate_golden_rules.py --level CRITICAL

# Before PR (critical + errors)
python scripts/validation/validate_golden_rules.py --level ERROR

# Full validation (all rules)
python scripts/validation/validate_golden_rules.py --level INFO
```

## Troubleshooting

### Environment Issues
```bash
# Check conda environment
conda env list
conda activate hive
python --version  # Should be 3.11.13

# Rebuild environment
conda env remove -n hive
conda env create -f environment.yml
```

### Configuration Issues
```bash
# Validate config consistency
python packages/hive-tests/src/hive_tests/config_validator.py

# Add missing ruff config
python scripts/maintenance/add_ruff_config.py --target packages/my-package
```

### Syntax Errors
```bash
# Check single file
python -m py_compile path/to/file.py

# Check all files (pytest collection)
python -m pytest --collect-only

# Auto-fix with ruff
python -m ruff check --fix .
```

### Import Errors
```bash
# Install package in development mode
cd packages/hive-config
poetry install

# Verify package installation
python -c "import hive_config; print(hive_config.__version__)"
```

## File Organization Rules

### Documentation
- **AI-specific docs**: `claudedocs/` directory
- **Project docs**: Root directory (README.md, ARCHITECTURE.md)
- **Session docs**: Archive in `docs/archive/session-docs/`

### Tests
- **Package tests**: `packages/my-package/tests/`
- **App tests**: `apps/my-app/tests/`
- **NEVER** place tests next to source files

### Scripts
- **Setup scripts**: `scripts/setup/`
- **Launch scripts**: `scripts/launch/`
- **Validation scripts**: `scripts/validation/`
- **Maintenance scripts**: `scripts/maintenance/`

## Quick Reference Commands

```bash
# Environment validation
bash scripts/validation/validate_environment.sh

# Config validation
python packages/hive-tests/src/hive_tests/config_validator.py

# Golden rules (critical only)
python scripts/validation/validate_golden_rules.py --level CRITICAL

# Golden rules (before PR)
python scripts/validation/validate_golden_rules.py --level ERROR

# Syntax validation
python -m pytest --collect-only

# Linting
python -m ruff check .

# Git status
git status && git branch
```

## Getting Help

**Documentation Index**: See `claudedocs/INDEX.md` (coming soon)
**Detailed Architecture**: `ARCHITECTURE.md`
**Configuration Guide**: `CONFIGURATION_HARDENING_COMPLETE.md`
**Environment Guide**: `ENVIRONMENT_HARDENING_COMPLETE.md`
**Development Guide**: `.claude/CLAUDE.md`

## Remember

1. **Read before write**: Always check existing patterns
2. **Validate before commit**: Run syntax and golden rules checks
3. **Follow DI pattern**: Use `create_config_from_sources()`, not `get_config()`
4. **Respect layer separation**: packages/ never imports from apps/
5. **Use trailing commas**: In multi-line Python structures
6. **Environment-agnostic code**: No hardcoded paths, no conda references
7. **Configuration consistency**: All pyproject.toml files must follow base template

---

**Status**: ✅ Multi-language environment ready | ✅ Configuration hardened | ✅ 25 packages/apps standardized

**Last Updated**: 2025-10-03 (Configuration Hardening Complete)
