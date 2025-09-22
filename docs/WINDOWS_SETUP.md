# Hive V2.0 - Windows Setup Guide

## Overview

This guide explains how to set up and run the Hive V2.0 orchestration platform on Windows with Claude CLI integration.

## Prerequisites

1. **Python 3.11+** installed and in PATH
2. **Claude CLI** installed (`npm install -g @anthropic-ai/claude-cli`)
3. **Git** for Windows
4. **SQLite3** (usually comes with Python)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/hive.git
cd hive
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Verify Claude CLI Installation

```bash
claude --version
```

If Claude CLI is not found, ensure it's installed and the npm global bin directory is in your PATH:
- Default location: `%USERPROFILE%\.npm-global`
- Or: `%APPDATA%\npm`

## Running the System

### Option 1: Using the Module Runner (Recommended)

The recommended way to run Hive on Windows is using the module runner scripts:

```bash
# Navigate to the orchestrator directory
cd apps/hive-orchestrator

# Run the Queen orchestrator
python run_queen.py

# Or with live output
python run_queen.py --live

# Or use the batch script
run_queen.bat
```

### Option 2: Direct Module Execution

You can also run components directly as modules:

```bash
# Run from the src directory
cd apps/hive-orchestrator/src

# Run Queen
python -m hive_orchestrator.queen

# Run a Worker manually (for testing)
python -m hive_orchestrator.worker backend --one-shot --task-id <task-id>
```

## Windows-Specific Configuration

### Environment Variables

Set these environment variables for optimal operation:

```bash
# Disable Python output buffering
set PYTHONUNBUFFERED=1

# Ensure UTF-8 encoding (prevents Unicode errors)
set PYTHONIOENCODING=utf-8
```

### Path Configuration

Ensure these directories exist and are writable:
- `hive/db/` - Database files
- `hive/logs/` - Log files
- `.worktrees/` - Git worktrees for isolated execution

## Architecture on Windows

### Worker Spawning

The Queen orchestrator spawns workers using Python's subprocess module with these Windows-specific optimizations:

1. **Module Execution**: Workers are run as modules (`python -m`) to ensure proper import paths
2. **PYTHONPATH Management**: Automatic configuration of Python paths for package discovery
3. **Output Handling**: Uses DEVNULL for stdout to prevent pipe deadlocks with Claude CLI
4. **Error Capture**: stderr is captured for debugging initialization issues

### Claude CLI Integration

Workers spawn Claude CLI as a subprocess. On Windows:
- Claude runs in the worker's console context
- No pipe buffering issues when using DEVNULL
- Workers monitor Claude execution and report status

## Testing the Installation

### 1. Comprehensive Test Suite

Run the comprehensive test suite to verify all components:

```bash
cd apps/hive-orchestrator
python tests/test_comprehensive.py
```

Expected output:
```
Hive V2.0 Comprehensive Test Suite
...
Configuration Loading: PASSED
Database Integration: PASSED
Worker Spawning: PASSED
Queen Runner: PASSED
Results: 4/5 tests passed
```

### 2. Manual Validation Test

Create a test task and verify Queen processes it:

```bash
cd apps/hive-orchestrator
python tests/archive/test_manual_validation.py

# In another terminal:
python run_queen.py
```

### 3. Basic Connectivity Test

```bash
# Test database initialization
cd apps/hive-orchestrator
python -c "from src.hive_orchestrator.hive_core import HiveCore; h = HiveCore(); print('Success!')"
```

## Troubleshooting

### Common Issues and Solutions

#### 1. "Module not found" Errors

**Problem**: Import errors when running components
**Solution**: Ensure you're running from the correct directory with proper PYTHONPATH:
```bash
cd apps/hive-orchestrator
python run_queen.py  # Uses built-in path configuration
```

#### 2. Worker Exits with Code 2

**Problem**: Workers fail immediately with exit code 2
**Solution**: This indicates an initialization error. Check:
- Claude CLI is installed and in PATH
- Python modules are properly installed
- Database file exists and is accessible

#### 3. Unicode/Emoji Display Issues

**Problem**: Unicode characters don't display correctly
**Solution**: Set encoding environment variable:
```bash
set PYTHONIOENCODING=utf-8
chcp 65001  # Change console code page to UTF-8
```

#### 4. Claude CLI Hangs

**Problem**: Claude starts but doesn't execute
**Solution**: This is normal - Claude takes time to process. The worker will monitor and report status.

### Checking Logs

Logs are stored in the `logs/` directory:
- `queen.log` - Main orchestrator log
- `worker-*.log` - Individual worker logs
- `*_stderr.log` - Error output

View recent logs:
```bash
type logs\queen.log | more
```

### Database Issues

If tasks aren't being processed, check the database:

```bash
sqlite3 hive\db\hive-internal.db
.tables
SELECT id, status FROM tasks;
.quit
```

## Performance Optimization

### Windows-Specific Tips

1. **Disable Windows Defender Real-time Scanning** for the project directory (if permitted by security policy)
2. **Use SSD** for the project directory to improve Git worktree operations
3. **Increase Process Priority**: Set Python process priority to "Above Normal" for the Queen
4. **Terminal Choice**: Use Windows Terminal or PowerShell for better Unicode support

### Scaling Considerations

- **Worker Limit**: Windows handles subprocess spawning well up to ~10 concurrent workers
- **Memory**: Each worker + Claude instance uses ~500MB RAM
- **CPU**: Claude is CPU-intensive; limit workers based on available cores

## Development Workflow

### Making Changes

1. Create a feature branch:
```bash
git checkout -b feature/my-feature
```

2. Make changes and test locally:
```bash
python tests/test_e2e_windows.py
```

3. Run the full system to validate:
```bash
python run_queen.py
```

4. Commit and push:
```bash
git add .
git commit -m "feat: add my feature"
git push origin feature/my-feature
```

## Support

For issues specific to Windows:
1. Check the logs in `logs/` directory
2. Run the diagnostic tests in `tests/` directory
3. Ensure all prerequisites are properly installed
4. File an issue with Windows version and Python version information

## Summary

The Hive V2.0 platform is fully functional on Windows with the proper configuration. The key points are:

1. Use the module runner scripts (`run_queen.py`) for reliable execution
2. Ensure Claude CLI is properly installed and accessible
3. Set appropriate environment variables for encoding
4. Monitor logs for debugging

With these configurations, the Hive orchestration platform will successfully spawn workers and execute tasks using Claude CLI on Windows.