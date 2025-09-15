#!/usr/bin/env python3
"""
Simple log viewer for Hive task logs
Shows Claude's complete interaction from the log files
"""

import json
import sys
from pathlib import Path
import argparse

def view_log(log_file):
    """View and parse a Claude log file"""
    
    if not Path(log_file).exists():
        print(f"Error: Log file not found: {log_file}")
        return
    
    print(f"\n{'='*80}")
    print(f"LOG FILE: {log_file}")
    print(f"{'='*80}\n")
    
    with open(log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Track Claude's messages
    assistant_messages = []
    tool_uses = []
    result = None
    error = None
    
    for line in lines:
        # Try to parse as JSON
        try:
            data = json.loads(line)
            
            # Track different message types
            if data.get("type") == "assistant":
                msg = data.get("message", {})
                content = msg.get("content", [])
                for item in content:
                    if item.get("type") == "text":
                        text = item.get("text", "")
                        if text:
                            assistant_messages.append(f"[CLAUDE]: {text}")
                    elif item.get("type") == "tool_use":
                        tool_name = item.get("name", "")
                        tool_input = item.get("input", {})
                        if tool_name == "Bash":
                            cmd = tool_input.get("command", "")
                            tool_uses.append(f"[TOOL: Bash]: {cmd}")
                        elif tool_name in ["Write", "Edit", "MultiEdit"]:
                            file_path = tool_input.get("file_path", "")
                            tool_uses.append(f"[TOOL: {tool_name}]: {file_path}")
                        else:
                            tool_uses.append(f"[TOOL: {tool_name}]")
            
            elif data.get("type") == "user":
                # Tool results
                content = data.get("content", [])
                if isinstance(content, list):
                    for item in content:
                        if item.get("type") == "tool_result":
                            is_error = item.get("is_error", False)
                            result_content = item.get("content", "")[:200]
                            if is_error:
                                error = f"[ERROR]: {result_content}"
            
            elif data.get("type") == "result":
                # Final result
                result = {
                    "success": data.get("subtype") == "success",
                    "result": data.get("result", ""),
                    "duration_ms": data.get("duration_ms", 0),
                    "cost": data.get("total_cost_usd", 0)
                }
        
        except json.JSONDecodeError:
            # Not JSON - could be raw output or special markers
            if line.strip().startswith("=== EXIT CODE:"):
                print(f"\n{line.strip()}")
            elif line.strip() and not line.startswith("{"):
                # Non-JSON output
                print(f"[OUTPUT]: {line.strip()}")
    
    # Print summary
    print(f"\n{'='*80}")
    print("SUMMARY:")
    print(f"{'='*80}")
    
    print(f"\nAssistant Messages ({len(assistant_messages)}):")
    for msg in assistant_messages[:5]:  # Show first 5
        print(f"  {msg[:100]}...")
    if len(assistant_messages) > 5:
        print(f"  ... and {len(assistant_messages) - 5} more")
    
    print(f"\nTool Uses ({len(tool_uses)}):")
    for tool in tool_uses[:10]:  # Show first 10
        print(f"  {tool}")
    if len(tool_uses) > 10:
        print(f"  ... and {len(tool_uses) - 10} more")
    
    if error:
        print(f"\nErrors:")
        print(f"  {error}")
    
    if result:
        print(f"\nFinal Result:")
        print(f"  Success: {result['success']}")
        print(f"  Duration: {result['duration_ms']/1000:.1f} seconds")
        print(f"  Cost: ${result['cost']:.4f}")
        if result['result']:
            print(f"  Output: {result['result'][:200]}...")
    else:
        print(f"\nNo final result found - Claude may have timed out or crashed")

def find_latest_log(task_id):
    """Find the latest log file for a task"""
    logs_dir = Path("hive/logs") / task_id
    if not logs_dir.exists():
        print(f"No logs found for task: {task_id}")
        return None
    
    log_files = list(logs_dir.glob("*.log"))
    if not log_files:
        print(f"No log files found for task: {task_id}")
        return None
    
    # Get the most recent
    latest = max(log_files, key=lambda f: f.stat().st_mtime)
    return latest

def main():
    parser = argparse.ArgumentParser(description="View Hive task logs")
    parser.add_argument("task_id", help="Task ID to view logs for")
    parser.add_argument("--latest", action="store_true", help="View latest log (default)")
    parser.add_argument("--file", help="Specific log file to view")
    
    args = parser.parse_args()
    
    if args.file:
        view_log(args.file)
    else:
        # Find latest log for task
        log_file = find_latest_log(args.task_id)
        if log_file:
            view_log(log_file)

if __name__ == "__main__":
    main()