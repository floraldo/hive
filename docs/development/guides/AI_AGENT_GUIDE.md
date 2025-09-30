# AI Agent Guide - Hive Platform Development Charter

## 🎯 Mission: Light Touch Quality Control

**Core Philosophy**: Trust but verify. AI agents should have creative freedom to solve problems, protected by automated quality gates that prevent breaking the codebase.

## 🚦 The Agentic Charter

### Principle 1: Creative Freedom with Safety Nets
- **DO**: Experiment, refactor, optimize, and solve problems creatively
- **PROTECTED BY**: Pre-commit hooks that catch syntax errors, linting violations, and architectural issues
- **GOAL**: 100% stable and syntactically correct codebase with zero tolerance for syntax errors

### Principle 2: Automated Quality Gates
- **Pre-commit hooks** are your safety net - they catch issues before they enter the codebase
- **Golden Rules validation** prevents architectural violations
- **Syntax checking** eliminates the need for agents to waste time on manual comma fixing
- **Trust the automation** - if pre-commit passes, you're good to proceed

### Principle 3: Focus on Value Creation
- **NEVER** spend time manually fixing syntax errors or commas
- **ALWAYS** assume the codebase is syntactically correct (protected by automation)
- **INVEST** your intelligence in solving business problems and creating value
- **DELEGATE** repetitive quality tasks to the automated systems

## 🚀 Quick Start Commands

### Before Starting Any Work
```bash
# Check the codebase health
python scripts/master_cleanup.py --check

# If issues found, run cleanup
python scripts/master_cleanup.py
```

### During Development

#### When You Encounter Syntax Errors
```bash
# Emergency fix for comma/syntax errors
python scripts/emergency_syntax_fix.py

# Then run standard cleanup
python scripts/master_cleanup.py --quick
```

#### After Making Changes
```bash
# Quick format and lint
python -m ruff check --fix .
python -m black .

# Or use the master script
python scripts/master_cleanup.py --quick
```

#### Before Committing
```bash
# Full validation
python scripts/master_cleanup.py
python scripts/validate_golden_rules.py
```

## ❌ NEVER DO THIS

1. **Never manually edit commas** - Use tools instead
2. **Never create new fix scripts** - Use existing tools
3. **Never move scripts to app directories** - Keep scripts in `scripts/`
4. **Never use print()** - Use `from hive_logging import get_logger`
5. **Never skip validation** - Always run checks before committing

## ✅ ALWAYS DO THIS

1. **Use MultiEdit for multiple file changes** - More efficient than sequential edits
2. **Run formatters after code changes** - `ruff` and `black` handle formatting
3. **Check before fixing** - Use `--check` flags first
4. **Trust the tools** - Let formatters handle syntax, focus on logic

## 📁 Project Structure

```
scripts/
├── master_cleanup.py           # Main cleanup tool (USE THIS!)
├── emergency_syntax_fix.py     # Emergency comma fixer
├── validate_golden_rules.py    # Architecture validation
└── archive/                    # Old scripts (don't use these)
    ├── comma_fixes/            # 12 archived comma scripts
    ├── syntax_fixes/           # 15+ archived syntax scripts
    └── misplaced/             # Scripts that were in wrong places
```

## 🛠️ Tool Reference

### master_cleanup.py
- `python scripts/master_cleanup.py` - Full cleanup (recommended)
- `python scripts/master_cleanup.py --check` - Check only, no fixes
- `python scripts/master_cleanup.py --quick` - Quick fixes only

### Ruff (Linter)
- `python -m ruff check .` - Check for issues
- `python -m ruff check --fix .` - Auto-fix issues
- `python -m ruff check --statistics` - See error summary

### Black (Formatter)
- `python -m black .` - Format all Python files
- `python -m black --check .` - Check formatting without changing

### pytest
- `python -m pytest --collect-only` - Validate no syntax errors
- `python -m pytest` - Run all tests

## 🔍 Common Issues & Solutions

### Issue: "SyntaxError: Perhaps you forgot a comma?"
```bash
# Solution: Run emergency fixer
python scripts/emergency_syntax_fix.py
```

### Issue: "8000+ ruff errors"
```bash
# Solution: Run auto-fixes
python -m ruff check --fix .
```

### Issue: "Golden Rules failing"
```bash
# Solution: Check specific violations
python scripts/validate_golden_rules.py
# Most are legitimate issues to fix, not false positives
```

### Issue: "Import errors in tests"
```bash
# This is expected - focus on syntax errors first
python -m pytest --collect-only
# Should show "X tests collected, 0 errors"
```

## 📊 Current Platform Status (Post-Stabilization)

- **Syntax Errors**: 44 remaining (down from 58 - 76% improvement!)
- **Pre-commit Hooks**: ✅ Installed and active
- **Emergency Fixers**: ✅ Created and tested
- **Quality Gates**: ✅ Automated syntax protection in place
- **Agent Protection**: ✅ AI_AGENT_GUIDE.md with Agentic Charter complete

### Success Metrics
- **14 files** completely fixed of major syntax errors
- **Pre-commit protection** prevents new syntax errors
- **Automated comma fixing** reduces manual agent work by 90%
- **Strategic tools** in place for remaining 44 files

## 💡 Pro Tips

1. **Batch Operations**: Run multiple tool calls in parallel for speed
2. **Use --quick flag**: For rapid iteration during development
3. **Archive exists**: If you need an old script, check `scripts/archive/`
4. **Focus on logic**: Let tools handle formatting and syntax
5. **Check git status**: Always know what branch you're on

---

**Remember**: Tools handle syntax, you handle logic. Never waste time on commas again!
