# ⚠️ DANGEROUS FIXERS - DO NOT USE

**Status**: QUARANTINED
**Date**: 2025-10-03
**Reason**: These scripts caused catastrophic syntax errors using regex-based code modification

---

## Why These Scripts Are Dangerous

### Root Cause: Regex-Based Code Modification
These scripts use **regular expressions** to modify Python code structure. This is fundamentally unsafe because:

1. **No Context Awareness**: Regex cannot understand code structure (classes, functions, indentation)
2. **Catastrophic Matches**: Broad patterns match unintended code
3. **No Validation**: No AST parsing to verify changes are valid Python

### Incidents Caused

#### Incident 1: Trailing Comma Disaster (2025-10-02)
- **Script**: `emergency_syntax_fix_consolidated.py`
- **Pattern**: `r"([^,\n]+)\n(\s+[^,\n]+)"` (matches ANY two consecutive lines)
- **Damage**: Added trailing commas indiscriminately, creating tuple syntax errors
- **Files Affected**: Hundreds across the codebase
- **Documentation**: `claudedocs/archive/syntax-fixes/emergency_fixer_root_cause_analysis.md`

#### Incident 2: Type Hint Modernizer Disaster (2025-10-03)
- **Script**: `modernize_type_hints.py`
- **Pattern**: Regex-based type hint replacement (Union/Optional → | syntax)
- **Damage**:
  - Import typo: `List, Optional, Tuple` → `ListTuple` (all imports combined!)
  - Misplaced imports: `from __future__ import annotations` inside class definitions
  - Removed dictionary commas
- **Files Affected**: 224 files modified in commit `ad9fba9`
- **Documentation**: `claudedocs/active/incidents/type_hint_modernizer_incident.md`

#### Incident 3: Autofix Print Replacement Risk (2025-10-04)
- **Script**: `packages/hive-tests/src/hive_tests/autofix.py` (print fixer component)
- **Pattern**: Regex-based print() → logger.info() replacement with manual parenthesis counting
- **Risk**: Could modify string literals, comments, multiline expressions
- **Status**: QUARANTINED before deployment (proactive safety measure)
- **Documentation**: `claudedocs/autofix_safety_audit_2025_10_04.md`

---

## Quarantined Scripts

### 1. `modernize_type_hints.py`
**Purpose**: Convert old-style type hints (Union/Optional) to modern | syntax
**Why Dangerous**:
- Uses regex to modify import statements (creates `ListTuple` typo)
- Uses regex to insert `from __future__` (placed inside classes!)
- No AST validation

**Catastrophic Patterns**:
```python
# Pattern that creates ListTuple typo
(r"Optional\[([^\[\]]+)\]", r"\1 | None")
# Matches inside "from typing import List, Optional, Tuple"
# Results in: "from typing import ListTuple"
```

### 2. `emergency_syntax_fix_consolidated.py`
**Purpose**: Fix trailing commas and syntax errors
**Why Dangerous**:
- Uses regex: `r"([^,\n]+)\n(\s+[^,\n]+)"` (matches EVERYTHING)
- Adds commas to ANY two consecutive lines
- No understanding of Python syntax

**Catastrophic Patterns**:
```python
# Pattern that destroyed the codebase
pattern = r"([^,\n]+)\n(\s+[^,\n]+)"
content = re.sub(pattern, r"\1,\n\2", content)  # Adds comma to EVERYTHING
```

**Example Damage**:
```python
# BEFORE (valid)
reporter = get_error_reporter()
error_id = reporter.report_error(sim_error)

# AFTER (broken)
reporter = get_error_reporter(),  # ← TUPLE created by trailing comma!
error_id = reporter.report_error(sim_error)
```

### 3. `code_fixers.py`
**Purpose**: Consolidated code fixing (type hints, logging, global state)
**Why Dangerous**:
- Uses simple regex patterns without context
- No AST validation
- Potential for similar issues as above

**Example Unsafe Patterns**:
```python
# Simple pattern matching - no context awareness
patterns = [
    (r"def (\w+)\(self\):", r"def \1(self) -> None:"),
    (r"def (\w+)\(\):", r"def \1() -> None:")
]
```

### 4. `autofix_components/autofix_with_regex_DANGEROUS.py`
**Purpose**: Golden Rules autofix - print() → logger.info() replacement
**Why Dangerous**:
- Uses regex to find print statements: `r"(?<!\.)\bprint\s*\("`
- Manual parenthesis counting via character iteration (lines 253-264)
- Direct string replacement without AST validation
- Could modify string literals, comments, docstrings

**Catastrophic Patterns**:
```python
# Pattern that could corrupt code
print_pattern = r"(?<!\.)\bprint\s*\("
for match in re.finditer(print_pattern, content):
    # Manual parenthesis counting - error prone!
    paren_count = 0
    # ... character-by-character parsing
    modified_content = modified_content.replace(old_statement, new_statement)
```

**Risk Examples**:
```python
# BEFORE (valid)
help_text = "Use print() for debug"
# AFTER (BROKEN)
help_text = "Use logger.info() for debug"  # Modified string literal!
```

**Safe Components** (can be extracted):
- `_fix_async_naming()` - delegates to AST transformer
- `_fix_exception_inheritance()` - uses AST parsing
- Dry-run mode and backup system

**Status**: Print fixer quarantined, safe components can be used

---

## Safe Alternatives

### ✅ AST-Based Approach (REQUIRED)
Use Python's `ast` module for any code modification:

```python
import ast

def safe_code_modification(filepath: Path) -> bool:
    """Safe code modification using AST validation."""
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

### ✅ Pre-Flight Checklist for Any Code Fixer
1. **Test on 5 sample files** manually
2. **Validate AST structure preservation**
3. **Run syntax check** on results: `python -m py_compile`
4. **Create backups** before bulk run
5. **Fail fast** on any unexpected changes

### ✅ Manual Fixes for Small Scope
If < 20 files need fixing, do it manually with:
- Read tool (understand code)
- Edit tool (make surgical changes)
- Bash syntax validation: `python -m py_compile file.py`

---

## Policy: BANNED From Use

**These scripts are BANNED from:**
- ❌ Manual execution
- ❌ Pre-commit hooks
- ❌ CI/CD pipelines
- ❌ Agent automation
- ❌ Future "quick fix" attempts

**Violation Consequences:**
- Immediate rollback of changes
- Incident report required
- Root cause analysis mandatory

---

## If You Need to Fix Code at Scale

**Step 1**: Read the incident documentation first
- `claudedocs/archive/syntax-fixes/emergency_fixer_root_cause_analysis.md`
- `claudedocs/active/incidents/type_hint_modernizer_incident.md`

**Step 2**: Use approved tools only
- ✅ `ruff check --fix` (auto-fixes safe linting issues)
- ✅ `black` or `ruff format` (formatters with validation)
- ✅ Manual Edit tool (surgical, verified changes)
- ✅ AST-based custom scripts (with validation)

**Step 3**: Follow the Pre-Flight Checklist
- Test on samples
- Validate syntax
- Create backups
- Fail fast

**Step 4**: Document your approach
- Create plan document
- Get approval for large-scale changes
- Create rollback plan

---

## Questions?

See `.claude/CLAUDE.md` - Section: "Automated Code-Fixing Scripts (CRITICAL)"

**Remember**: Fast and wrong is worse than slow and right. Take the time to do it safely.

---

**Last Updated**: 2025-10-04
**Incident Count**: 2 (+ 1 prevented)
**Files Damaged Total**: 300+ (from 2 incidents)
**Files Protected**: Entire codebase (autofix quarantined before deployment)
**Lessons**: NEVER use regex for structural code changes. ALWAYS use AST. Proactive safety audits prevent disasters.
