#!/bin/bash
# Claude Code wrapper script for Git Bash
# This ensures the correct PATH is set before running claude

# Add essential paths
export PATH="/c/Program Files/Git/usr/bin:$PATH"
export PATH="/c/Program Files/nodejs:$PATH"
export PATH="/c/Users/flori/.npm-global:$PATH"

# Run claude with all arguments
exec /c/Users/flori/.npm-global/claude "$@"