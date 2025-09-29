# Hive Platform - Claude Development Guide

**Architecture**: Modular monolith with inherit→extend pattern
**Key Files**: See `.claude/rules.md`, `.claude/project.yaml`, `.claude/ignore`

## 🏗️ Core Pattern

- **packages/** = Infrastructure (inherit layer)
- **apps/** = Business logic (extend layer)
- **Dependency flow**: apps → packages, apps → app.core (never package → app)

## 🚫 Critical Rules

- **NO Unicode in code**: Use `# OK` not ✅, `# FAIL` not ❌
- **Edit existing files**, don't create new ones unless required
- **Use hive-* packages**: `from hive_logging import get_logger` not `print()`
- **Golden Rules validation**: `python scripts/validate_golden_rules.py`
- **SYNTAX ERROR PREVENTION**:
  - **ALWAYS check commas** in multi-line Python constructs
  - Function definitions: `def func(cls,` not `def func(cls`
  - Function calls: `func(arg1,` not `func(arg1`
  - Dict/list literals: Must be properly comma-separated
  - **Test syntax before commit**: `python -m py_compile file.py`

## 🛠️ Standard Tools

```toml
pytest = "^8.3.2"
black = "^24.8.0"
mypy = "^1.8.0"
ruff = "^0.1.15"
isort = "^5.13.0"
```

## 📂 Quick Navigation

- **Full rules**: `.claude/rules.md`
- **Project config**: `.claude/project.yaml`
- **Ignore patterns**: `.claude/ignore`
- **Golden Rules**: 15 rules in `packages/hive-tests/src/hive_tests/architectural_validators.py`

## ⚡ Fleet Command (Existing)

Multi-agent system in tmux panes:
- **Queen (Pane 0)**: Mission orchestrator
- **Workers (Panes 1-3)**: Frontend, Backend, Infra specialists

**Commands**:
```bash
./scripts/fleet_send.sh send backend "[T101] Task description"
./scripts/hive-send --to frontend --topic task --message "Task"
```

**Remember**: Build on what exists. Follow inherit→extend. Keep it simple.
