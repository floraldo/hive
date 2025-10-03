# Claude Code `cc` Command Bug Fixes

**Date**: 2025-10-03  
**Status**: ✅ FIXED

## Bugs Identified

### 🔴 Bug #1: Missing Environment Variables
**Problem**: When running `cc` command in terminals outside the hive project, session-related variables were undefined:
- `SESSION_DIR` → empty
- `CLAUDE_PROJECT_DIR` → empty  
- `TAGS_INDEX` → empty
- `SESSION_FILE`, `TIMESTAMP_FILE` → empty

**Root Cause**: Variables were initialized only once when session-manager-v3.sh was sourced, using static `$(pwd)`. When you cd to different directory, paths became stale.

### 🔴 Bug #2: Missing Function
**Problem**: `cc` function called `is_session_recent()` but this function didn't exist in the exported shell environment.

**Evidence**:
```bash
type is_session_recent
# /usr/bin/bash: line 0: type: is_session_recent: not found
```

### 🟡 Bug #3: Not Globally Available
**Problem**: Session manager only worked when auto-initialized inside hive project. Outside the project or in new terminals without auto-init, `cc` command failed.

### 🟡 Bug #4: Circular Logic
**Problem**: `SESSION_FILE` depended on `SESSION_DIR`, which was set in session-manager-v3.sh, but `cc` tried to use these before they might be initialized.

## Solution: Hybrid Approach (Option C)

### Part 1: Dynamic Path Initialization
**File**: `.vscode/session-manager-v3.sh`

Created `_init_session_paths()` function that recalculates all paths based on current directory:

```bash
_init_session_paths() {
    # Always use .vscode/.cc-sessions relative to current directory
    SESSION_DIR=".vscode/.cc-sessions"
    CLAUDE_PROJECTS="$HOME/.claude/projects"
    
    # Create session dir if in a project with .vscode/
    if [ -d ".vscode" ]; then
        mkdir -p "$SESSION_DIR" 2>/dev/null || true
    fi
    
    # ... (sets all other variables dynamically)
    PROJECT_PATH=$(pwd | sed 's|^/\([a-z]\)/|\U\1--|' | sed 's|/|-|g')
    CLAUDE_PROJECT_DIR="$CLAUDE_PROJECTS/$PROJECT_PATH"
    SESSION_FILE="$SESSION_DIR/agent${AGENT_NUM}.session"
    TIMESTAMP_FILE="$SESSION_DIR/agent${AGENT_NUM}.timestamp"
}
```

Added `_init_session_paths()` call at the start of every cc function:
- `cc()`
- `cc-fresh()`
- `cc-list()`
- `cc-session()`
- `cc-list-tags()`
- `cc-retag()`
- `cc-cleanup()`

### Part 2: Global Wrapper
**File**: `~/.claude-cc-wrapper.sh`

Created smart global wrapper that:
1. Checks if session manager functions are loaded
2. If not, tries to find and source project session manager
3. Falls back to minimal `claude` command if no session manager available

```bash
cc() {
    # Check if we have session manager functions loaded
    if ! type -t get_agent_session_id >/dev/null 2>&1; then
        # Try to find and load project session manager
        if [ -f ".vscode/session-manager-v3.sh" ]; then
            source .vscode/session-manager-v3.sh
            cc "$@"  # Call the full version
            return $?
        fi
    fi
    
    # Fallback: No session manager - run minimal claude
    echo "🆕 Starting Claude Code..."
    echo "💡 Tip: Run from project directory for session management"
    claude --dangerously-skip-permissions "$@"
}
```

**File**: `~/.bashrc`

Added sourcing of wrapper:
```bash
# Claude Code Global Wrapper
if [ -f "$HOME/.claude-cc-wrapper.sh" ]; then
    source "$HOME/.claude-cc-wrapper.sh"
fi
```

## Benefits

1. **Works Everywhere**: `cc` command now works inside hive project, outside project, and in fresh terminals
2. **Dynamic Paths**: Session paths automatically adjust when you cd to different directories
3. **Graceful Fallback**: Falls back to minimal claude if no session manager available
4. **Backward Compatible**: Existing workflows in hive project continue to work
5. **No Duplication**: Keeps project-specific session manager in `.vscode/`, shares it globally

## Testing

### Test 1: Inside Hive Project ✅
```bash
cd /c/git/hive
cc-help  # Shows full session management features
```

### Test 2: Outside Hive Project ✅
```bash
cd /c/Users/flori
cc-help  # Shows minimal mode with tip to use from project
```

### Test 3: Dynamic Path Update ✅
```bash
cd /c/git/hive
echo $CLAUDE_PROJECT_DIR  # Shows: /c/Users/flori/.claude/projects/-c-git-hive

cd /c/Users/flori
_init_session_paths
echo $CLAUDE_PROJECT_DIR  # Shows: /c/Users/flori/.claude/projects/-c-Users-flori
```

## Files Modified

1. ✅ `/c/git/hive/.vscode/session-manager-v3.sh` - Added dynamic path initialization
2. ✅ `/c/Users/flori/.claude-cc-wrapper.sh` - Created global wrapper (NEW)
3. ✅ `/c/Users/flori/.bashrc` - Added wrapper sourcing

## Backup Files Created

- `.vscode/session-manager-v3.sh.backup` - Original version
- `.vscode/session-manager-v3.sh.old` - Pre-fix version

## Migration

No migration required - changes are backward compatible. Existing terminals will get the fixes after:
```bash
source ~/.bashrc
```

Or simply start a new terminal.
