# Autofix Safety Audit - 2025-10-04

**Auditor**: MCP Agent
**Context**: User requested safety review after MASSIVE prior incidents with regex-based code fixers
**Status**: 🔴 **QUARANTINE REQUIRED** - Dangerous patterns detected

---

## Executive Summary

**Verdict**: `packages/hive-tests/src/hive_tests/autofix.py` contains **DANGEROUS regex-based code modification** that violates safety principles established after two major incidents.

**Risk Level**: 🔴 **HIGH** - Could cause similar catastrophic failures

**Recommendation**: **QUARANTINE immediately** and replace with AST-only approach

---

## Safety Audit Results

### ✅ SAFE Components

#### 1. Async Naming Transformer (Lines 131-201)
```python
# SAFE: Uses AST transformation
from .async_naming_transformer import fix_async_naming_ast
modified_content, fixes = fix_async_naming_ast(content)
```
- **Assessment**: SAFE
- **Reason**: Delegates to AST-based transformer
- **Fallback**: Gracefully fails on AST errors (doesn't fall back to regex)

#### 2. Exception Inheritance Fixer (Lines 314-416)
```python
# SAFE: Parses AST first
tree = ast.parse(content)
for node in ast.walk(tree):
    if isinstance(node, ast.ClassDef):
        # ... context-aware class modification
```
- **Assessment**: SAFE
- **Reason**: Uses AST to find classes before modifying
- **Caveat**: Uses `str.replace()` after AST analysis (borderline, but acceptable)

### 🔴 DANGEROUS Components

#### 1. Print Statement Fixer (Lines 203-312)

**DANGEROUS PATTERN DETECTED**:
```python
# Line 248: Regex to find print statements
print_pattern = r"(?<!\.)\bprint\s*\("

# Line 251: Regex iteration
for match in re.finditer(print_pattern, content):
    # Lines 253-280: Manual parenthesis counting and string slicing
    paren_count = 0
    # ... attempts to extract print() arguments via character iteration

    # Line 279: Direct string replacement
    modified_content = modified_content.replace(old_statement, new_statement)
```

**Why This Is Dangerous**:

1. **No AST Validation**: Operates on raw strings
2. **Parenthesis Counting**: Manual tracking of `()` balance is error-prone
3. **String Matching**: Could match `print` in:
   - String literals: `text = "use print()"`
   - Comments: `# Call print() here`
   - Multiline expressions
4. **Multiple Replacements**: Line 279 uses `str.replace()` which could replace unintended matches

**Risk Examples**:
```python
# BEFORE (valid)
def demo():
    # Use print() for debugging
    result = calculate()
    print(result)

# AFTER (potential corruption)
def demo():
    # Use logger.info() for debugging  ← Comment modified!
    result = calculate()
    logger.info(result)
```

**Similarity to Banned Scripts**:
- Same approach as `emergency_syntax_fix_consolidated.py` (regex + manual parsing)
- No AST validation like `modernize_type_hints.py`
- Could create similar catastrophic failures

#### 2. Import Insertion Logic (Lines 217-241, 369-384)

**BORDERLINE DANGEROUS**:
```python
# Find insertion point via simple line iteration
for i, line in enumerate(lines):
    if line.strip().startswith("import ") or line.strip().startswith("from "):
        insert_index = i + 1
```

**Issues**:
- No AST-based import analysis
- Could insert imports:
  - Inside docstrings (if """ spans multiple lines)
  - Inside function definitions
  - In wrong module scope
- No validation of import syntax

---

## Comparison to Quarantined Scripts

### Similarities (BAD SIGNS)

| Pattern | `autofix.py` | Quarantined Scripts | Risk |
|---------|--------------|---------------------|------|
| Regex-based code modification | ✅ Yes (print fixer) | ✅ Yes | 🔴 HIGH |
| Manual parenthesis counting | ✅ Yes (lines 253-264) | ✅ Yes (emergency_syntax_fix) | 🔴 HIGH |
| String replacement | ✅ Yes (`str.replace`) | ✅ Yes | 🔴 HIGH |
| No AST validation | ✅ Yes (print fixer) | ✅ Yes | 🔴 HIGH |
| Backup creation | ✅ Yes | ❌ No | ✅ GOOD |
| Dry-run mode | ✅ Yes | ❌ No | ✅ GOOD |

### Key Differences (GOOD SIGNS)

| Feature | `autofix.py` | Quarantined Scripts |
|---------|--------------|---------------------|
| Default mode | Dry-run (safe) | Live execution (dangerous) |
| Backups | Enabled by default | Not implemented |
| Limited scope | Only 3 rules | Broad patterns |
| AST for some rules | Yes (async, exceptions) | No |

---

## Incident Risk Assessment

### Could This Cause Another Disaster?

**YES - Here's how:**

#### Scenario 1: Print in String Literals
```python
# BEFORE (valid)
help_text = """
To debug, use print() to log values.
"""
actual_output = get_output()

# AFTER (BROKEN - modified string literal)
help_text = """
To debug, use logger.info() to log values.  ← Changed literal!
"""
actual_output = get_output()
```

#### Scenario 2: Nested Print Calls
```python
# BEFORE (valid)
print(f"Result: {get_data(print_debug=True)}")

# AFTER (BROKEN - mismatched parentheses)
logger.info(f"Result: {get_data(print_debug=True)}")  # Parenthesis counting failed
```

#### Scenario 3: Print in Comments
```python
# BEFORE (valid)
# TODO: Remove print() statements before production
debug_value = calculate()

# AFTER (BROKEN - modified comment)
# TODO: Remove logger.info() statements before production  ← Comment changed!
debug_value = calculate()
```

---

## Recommended Actions

### 1. IMMEDIATE: Quarantine Print Fixer 🔴

**Move to quarantine**:
```bash
mkdir -p scripts/archive/DANGEROUS_FIXERS/autofix_components/
mv packages/hive-tests/src/hive_tests/autofix.py \
   scripts/archive/DANGEROUS_FIXERS/autofix_components/autofix_with_regex_DANGEROUS.py
```

**Update WARNING.md**:
```markdown
### 4. `autofix.py` - Print Statement Fixer (QUARANTINED 2025-10-04)
**Purpose**: Replace print() with logger.info()
**Why Dangerous**:
- Uses regex pattern matching without AST validation
- Manual parenthesis counting via character iteration
- Could modify string literals, comments, multiline expressions
- Similar approach to emergency_syntax_fix_consolidated.py
```

### 2. Create Safe AST-Only Version

**New file**: `packages/hive-tests/src/hive_tests/autofix_safe.py`

```python
"""
AST-Only Autofix - NO REGEX CODE MODIFICATION

Lessons from incidents:
- emergency_syntax_fix_consolidated.py (2025-10-02): Regex comma disaster
- modernize_type_hints.py (2025-10-03): Regex import corruption
- autofix.py print fixer (2025-10-04): Regex print replacement (QUARANTINED)

RULE: ALL code modification MUST use AST. NO EXCEPTIONS.
"""

import ast
import libcst as cst  # Modern AST library with transformation support

class SafePrintReplacer(cst.CSTTransformer):
    """AST-based print() → logger.info() replacement."""

    def leave_Call(self, original_node, updated_node):
        # Only modify actual function calls, not string literals or comments
        if isinstance(updated_node.func, cst.Name):
            if updated_node.func.value == "print":
                # Replace with logger.info()
                return updated_node.with_changes(
                    func=cst.Attribute(
                        value=cst.Name("logger"),
                        attr=cst.Name("info")
                    )
                )
        return updated_node
```

### 3. Extraction Plan for Safe Components

**Keep these components** (already AST-based):
- `_fix_async_naming()` - delegates to AST transformer
- `_fix_exception_inheritance()` - uses AST parsing

**Quarantine these components**:
- `_fix_print_statements()` - DANGEROUS regex approach

---

## Safe Autofix Policy (Updated)

### ✅ ALLOWED Autofix Approaches

1. **AST-based transformations only**
   - Use `ast` module for analysis
   - Use `libcst` for safe transformations
   - Validate syntax before and after

2. **Linter auto-fix**
   - `ruff check --fix` (built-in safe fixes)
   - `black` or `ruff format` (formatters with validation)
   - `isort` (import sorting with AST parsing)

3. **Manual surgical edits**
   - Read tool → understand context
   - Edit tool → make precise change
   - Bash syntax check → validate

### ❌ BANNED Autofix Approaches

1. **Regex-based code modification**
   - ❌ `re.sub()` on code
   - ❌ `re.finditer()` + string manipulation
   - ❌ Manual parenthesis counting
   - ❌ String slicing and replacement

2. **Simple pattern matching**
   - ❌ `str.replace()` on code
   - ❌ Line-by-line regex scanning
   - ❌ No AST validation

3. **Bulk transformations without validation**
   - ❌ Multi-file changes without per-file syntax check
   - ❌ No backup creation
   - ❌ No dry-run mode

---

## Incident Prevention Checklist

Before ANY autofix script is approved:

- [ ] **NO regex patterns** for structural code changes
- [ ] **ALL modifications** go through AST parsing
- [ ] **Syntax validation** before and after (per file)
- [ ] **Dry-run mode** is the default
- [ ] **Backup creation** before modifications
- [ ] **Test on 5 sample files** manually first
- [ ] **Document approach** with examples
- [ ] **Get approval** for multi-file changes
- [ ] **Rollback plan** documented

---

## Conclusion

**Current autofix.py status**: 🔴 **UNSAFE FOR PRODUCTION USE**

**Risk**: Print statement fixer could cause another incident similar to:
- Trailing comma disaster (emergency_syntax_fix)
- Type hint modernizer corruption (modernize_type_hints)

**Action Required**:
1. ✅ Quarantine `autofix.py` immediately
2. ✅ Extract safe components (async naming, exception inheritance)
3. ✅ Create AST-only replacement for print fixing
4. ✅ Update Guardian Agent to use safe version only
5. ✅ Add to pre-commit validation: No regex code modification

**Safe components to preserve**:
- Async naming transformer (AST-based) ✅
- Exception inheritance fixer (AST-based) ✅
- Dry-run mode and backup system ✅

**DO NOT use autofix.py in Phase 2 Guardian Agent until print fixer is replaced with AST-based approach.**

---

**Audit Complete**: 2025-10-04
**Next Review**: Before any Guardian Agent deployment
**Lessons**: Even with good intentions (dry-run, backups), regex code modification is fundamentally unsafe.
