# AI Agent Quick Reference Guide

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

## 📊 Current Platform Status

- **Syntax Errors**: 0 (fixed!)
- **Ruff Errors**: ~5,289 (down from 8,171)
- **Golden Rules**: 7/20 passing
- **Test Collection**: 184 tests collected
- **Scripts**: 3 essential tools (down from 25+)

## 💡 Pro Tips

1. **Batch Operations**: Run multiple tool calls in parallel for speed
2. **Use --quick flag**: For rapid iteration during development
3. **Archive exists**: If you need an old script, check `scripts/archive/`
4. **Focus on logic**: Let tools handle formatting and syntax
5. **Check git status**: Always know what branch you're on

---

**Remember**: Tools handle syntax, you handle logic. Never waste time on commas again!
