# Emergency Syntax Error Recovery Instructions

**Date**: 2025-10-03
**Problem**: emergency_syntax_fix_consolidated.py introduced syntax errors
**Solution**: Selective file revert + script quarantine

---

## Quick Recovery (5 minutes)

### Step 1: Find Affected Files

```bash
# Option A: Use the provided script
python scripts/find_syntax_errors.py > corrupted_files.txt

# Option B: Manual check (if you already know which files)
# List files you know are broken in corrupted_files.txt
```

### Step 2: Revert Only Broken Files

```bash
# Revert specific files to previous commit
# Replace with your actual broken files:
git checkout HEAD~1 -- \
  "apps/ecosystemiser/src/ecosystemiser/services/database_metadata_service.py" \
  "packages/hive-cache/src/hive_cache/health.py" \
  # ... add all other broken files
```

**OR** if you have many files in `corrupted_files.txt`:

```bash
# Read from file and revert each
while IFS= read -r filepath; do
    echo "Reverting: $filepath"
    git checkout HEAD~1 -- "$filepath"
done < corrupted_files.txt
```

###Step 3: Verify Recovery

```bash
# Check all Python files compile
python -m compileall apps packages 2>&1 | grep -i "syntaxerror"

# Should return nothing if all fixed
```

### Step 4: Commit the Revert

```bash
git add -u
git commit -m "fix: revert files corrupted by emergency_syntax_fix_consolidated.py

Reverted syntax-corrupted files to HEAD~1.

Root cause: emergency_syntax_fix_consolidated.py contained catastrophically
broad regex patterns that added commas indiscriminately.

Bugs fixed:
- Line 224: fix_multiline_expressions() - matched ANY two consecutive lines
- Line 213: fix_enum_commas() - matched any word pairs
- Line 197: fix_list_commas() - overly broad identifier matching

Script quarantined to: scripts/archive/BROKEN_emergency_syntax_fix_consolidated.py.BAK

See: claudedocs/emergency_fixer_root_cause_analysis.md for full details
"
```

---

## Detailed Recovery (if quick method fails)

### Find ALL Broken Files Manually

```bash
# Create a Python script to check each file
cat > check_all_syntax.py << 'EOF'
import ast
from pathlib import Path

for filepath in Path("apps").rglob("*.py"):
    try:
        with open(filepath) as f:
            ast.parse(f.read())
    except SyntaxError as e:
        print(f"{filepath}:{e.lineno}")

for filepath in Path("packages").rglob("*.py"):
    try:
        with open(filepath) as f:
            ast.parse(f.read())
    except SyntaxError as e:
        print(f"{filepath}:{e.lineno}")
EOF

python check_all_syntax.py > broken_files_detailed.txt
```

### Extract Just Filenames

```bash
# Get unique file paths (remove line numbers)
cut -d: -f1 broken_files_detailed.txt | sort | uniq > files_to_revert.txt
```

### Batch Revert

```bash
# Revert all broken files
git checkout HEAD~1 -- $(cat files_to_revert.txt)
```

---

## Prevention - Update CI/CD

Add syntax validation to prevent future corruption:

```yaml
# .github/workflows/syntax-validation.yml
name: Python Syntax Validation
on: [push, pull_request]
jobs:
  validate-syntax:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Check Python syntax
        run: |
          python -m compileall apps packages scripts
          if [ $? -ne 0 ]; then
            echo "❌ Syntax errors detected in Python files!"
            exit 1
          fi
          echo "✅ All Python files have valid syntax"
```

---

## Files Quarantined

1. **Broken Script**: `scripts/archive/BROKEN_emergency_syntax_fix_consolidated.py.BAK`
2. **Warning File**: `scripts/maintenance/fixers/DO_NOT_USE_EMERGENCY_FIXER.md`
3. **Root Cause Analysis**: `claudedocs/emergency_fixer_root_cause_analysis.md`

---

## Safe Alternative (Future)

When you need comma fixing, use AST-based approach:

```python
# scripts/maintenance/fixers/ast_safe_comma_fixer.py (to be created)
import ast

def fix_specific_pattern(filepath):
    """Fix ONLY specific known patterns using AST."""
    with open(filepath) as f:
        tree = ast.parse(f.read())

    # Example: Fix dict unpacking without comma
    # Use AST visitors to find and fix specific patterns
    # Regenerate code
    # Validate

    # NEVER use broad regex patterns!
```

---

## Contact

- Root Cause Analysis: `claudedocs/emergency_fixer_root_cause_analysis.md`
- Script Bugs: Lines 197, 213, 224 in emergency_syntax_fix_consolidated.py
- Recovery Status: Check `git status` after running steps above
