#!/bin/bash
# Test run script for Hive MAS

echo "Setting up environment..."
export CLAUDE_BIN=claude
export HIVE_DISABLE_PR=1

echo "Environment variables set:"
echo "  CLAUDE_BIN=$CLAUDE_BIN"
echo "  HIVE_DISABLE_PR=$HIVE_DISABLE_PR"

echo ""
echo "To start the system:"
echo "  Terminal 1: python queen_orchestrator.py"
echo "  Terminal 2: python hive_status.py"
echo "  Terminal 3: tail -f hive/bus/events_$(date +%Y%m%d).jsonl"
echo ""
echo "To add a hint:"
echo "  echo 'Keep it minimal' > hive/operator/hints/tsk_001.md"
echo ""
echo "To interrupt:"
echo "  echo '{\"reason\":\"Pause for review\"}' > hive/operator/interrupts/tsk_001.json"
echo ""
echo "Starting Queen orchestrator in 3 seconds..."
sleep 3

python queen_orchestrator.py