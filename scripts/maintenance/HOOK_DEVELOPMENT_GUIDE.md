# Git Hook Development Guide

## Critical Lessons Learned

### 1. Cross-Platform Compatibility Requirements

**Problem**: Git hooks must work across multiple environments:
- Git Bash (MINGW64) - UTF-8 encoding
- GitHub Desktop - Windows cp1252 encoding
- Command Prompt - Windows console
- PowerShell - Unicode support varies
- WSL - Linux environment

**Solution**: Use pure Python with ASCII-safe output

### 2. The Unicode Encoding Trap

**What Happened**: Pre-push hook used Unicode symbols (✓ ⚠) that crashed in GitHub Desktop:
```
UnicodeEncodeError: 'charmap' codec can't encode character '\u2713' in position 0
```

**Root Cause**: GitHub Desktop's Python uses Windows cp1252 encoding by default

**Fix**: Replace ALL Unicode symbols with ASCII equivalents:
- ✓ → `[OK]`
- ⚠ → `[WARNING]`
- ❌ → `[ERROR]`

### 3. Hook Implementation Best Practices

#### ✅ DO: Pure Python Hooks
```python
#!/usr/bin/env python
"""Hook description"""
import subprocess
import sys
from pathlib import Path

def main():
    # Hook logic here
    print("[OK] ASCII-safe output")  # No Unicode!
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

#### ❌ DON'T: Bash Hooks with Environment Detection
```bash
#!/usr/bin/env bash
# Fragile - breaks on GitHub Desktop, WSL relay issues
if [[ "$OSTYPE" == "msys" ]]; then
    # Windows-specific logic
fi
```

### 4. Testing Checklist for New Hooks

Before committing a new Git hook:

1. **Test in Git Bash**: `bash .git/hooks/hook-name`
2. **Test with Python**: `python .git/hooks/hook-name`
3. **Test via Git**: `git <operation>` (commit, push, etc.)
4. **Test in GitHub Desktop**: Actually push from GitHub Desktop GUI
5. **Check encoding**: Verify no Unicode symbols in output

### 5. Emergency Recovery

If a hook breaks pushes:

**Option 1: Bypass temporarily**
```bash
git push --no-verify
```

**Option 2: Create lock file** (for RAG hook)
```bash
touch rag_indexing.lock
git push
rm rag_indexing.lock
```

**Option 3: Disable hook** (nuclear option)
```bash
chmod -x .git/hooks/pre-push
git push
chmod +x .git/hooks/pre-push
```

### 6. Common Pitfalls

| Pitfall | Why It Fails | Solution |
|---------|--------------|----------|
| Unicode output | cp1252 encoding in GitHub Desktop | Use ASCII only: `[OK]`, `[ERROR]` |
| Bash shebang `/bin/bash` | WSL relay errors on Windows | Use `#!/usr/bin/env python` |
| `$WINDIR` detection | Not set in Git Bash | Use `sys.platform == "win32"` |
| Hardcoded paths | Different Git installations | Use `git rev-parse --show-toplevel` |
| `python3` command | Doesn't exist on Windows | Use `sys.executable` |

### 7. Current Hook Architecture

**File**: `.git/hooks/pre-push`
- **Language**: Pure Python (not bash)
- **Encoding**: ASCII-safe output only
- **Compatibility**: Works in all Git environments
- **Fallback**: Never blocks push (always exits 0)
- **Emergency off-switch**: `rag_indexing.lock` file

### 8. Hook Maintenance Commands

```bash
# View current hook
cat .git/hooks/pre-push

# Test hook directly
python .git/hooks/pre-push

# Check hook permissions
ls -la .git/hooks/pre-push

# Make hook executable
chmod +x .git/hooks/pre-push

# Reinstall pre-commit hooks (if using pre-commit framework)
pre-commit install
```

### 9. Reference: Working Pre-Push Hook

See `.git/hooks/pre-push` for the production version that:
- ✅ Works in Git Bash, GitHub Desktop, CMD, PowerShell
- ✅ Uses ASCII-safe output (`[OK]`, `[WARNING]`)
- ✅ Pure Python (no bash dependency)
- ✅ Never blocks push (graceful degradation)
- ✅ Has emergency off-switch (lock file)

## Summary

**Golden Rules for Git Hooks**:
1. Pure Python, no bash
2. ASCII output only (no Unicode)
3. Use `sys.executable` not `python3`
4. Test in GitHub Desktop before committing
5. Never block operations (always exit 0)
6. Provide emergency off-switch
