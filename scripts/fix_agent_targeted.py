#!/usr/bin/env python3
"""Targeted fixer for ai-planner/agent.py using AST error detection"""
import re
from pathlib import Path

def fix_agent_file():
    """Fix all missing commas in agent.py"""
    file_path = Path(__file__).parent.parent / 'apps/ai-planner/src/ai_planner/agent.py'

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    fixes = 0

    # Known line numbers with missing commas (from git status and error messages)
    fix_patterns = [
        # Function call arguments - task["id"] followed by keyword arg
        (lambda line, next_line: 'task["id"]' in line and next_line.strip().startswith(('workflow_id=', 'task_description=')),
         lambda line: line.rstrip() + ',\n'),

        # Dict entries - "key": value followed by "nextkey":
        (lambda line, next_line: '": ' in line and not line.rstrip().endswith(',') and next_line.strip().startswith('"'),
         lambda line: line.rstrip() + ',\n'),

        # Dict entries - task["id"] followed by another key
        (lambda line, next_line: 'task["id"]' in line and not line.rstrip().endswith(',') and '"' in next_line and ':' in next_line,
         lambda line: line.rstrip() + ',\n'),

        # Dict entries - method call result followed by another key
        (lambda line, next_line: '.isoformat()' in line and not line.rstrip().endswith(',') and next_line.strip().startswith('"'),
         lambda line: line.rstrip() + ',\n'),

        # Dict resource map entries
        (lambda line, next_line: '["basic-compute"]' in line and not line.rstrip().endswith(',') and '"medium"' in next_line,
         lambda line: line.rstrip() + ',\n'),
        (lambda line, next_line: '"database-access"]' in line and not line.rstrip().endswith(',') and '"complex"' in next_line,
         lambda line: line.rstrip() + ',\n'),

        # Tuple entries in VALUES clause
        (lambda line, next_line: 'plan["plan_id"]' in line and not line.rstrip().endswith(',') and 'plan[' in next_line,
         lambda line: line.rstrip() + ',\n'),
        (lambda line, next_line: 'plan["task_id"]' in line and not line.rstrip().endswith(',') and ('json.dumps' in next_line or 'plan.' in next_line),
         lambda line: line.rstrip() + ',\n'),
        (lambda line, next_line: 'json.dumps(plan)' in line and not line.rstrip().endswith(',') and 'plan.' in next_line,
         lambda line: line.rstrip() + ',\n'),
        (lambda line, next_line: ('plan.get("metrics"' in line or 'plan.get("status"' in line or 'plan.get("created_at"' in line) and not line.rstrip().endswith(',') and 'plan[' in next_line,
         lambda line: line.rstrip() + ',\n'),
        (lambda line, next_line: 'plan["status"]' in line and not line.rstrip().endswith(',') and 'plan[' in next_line,
         lambda line: line.rstrip() + ',\n'),

        # Function call - create_task arguments
        (lambda line, next_line: ('sub_task["title"]' in line or 'sub_task["description"]' in line) and not line.rstrip().endswith(',') and ('task_type=' in next_line or 'description=' in next_line or 'payload=' in next_line),
         lambda line: line.rstrip() + ',\n'),

        # Nested dict in payload
        (lambda line, next_line: 'plan["plan_id"],' in line and '"subtask_id"' in next_line and not line.rstrip().endswith(','),
         lambda line: line if line.rstrip().endswith(',') else line.rstrip() + ',\n'),
        (lambda line, next_line: ('sub_task["id"]' in line or 'sub_task["assignee"]' in line or 'sub_task["complexity"]' in line or 'sub_task["estimated_duration"]' in line or 'sub_task["workflow_phase"]' in line or 'sub_task["required_skills"]' in line or 'sub_task["deliverables"]' in line) and not line.rstrip().endswith(',') and ('"' in next_line and ':' in next_line or '}' in next_line),
         lambda line: line.rstrip() + ',\n'),

        # Error constructor arguments
        (lambda line, next_line: 'task_id=sub_task["id"]' in line and not line.rstrip().endswith(',') and 'phase=' in next_line,
         lambda line: line.rstrip() + ',\n'),
        (lambda line, next_line: 'phase=' in line and not line.rstrip().endswith(',') and 'original_error=' in next_line,
         lambda line: line.rstrip() + ',\n'),
        (lambda line, next_line: 'task_id=task["id"]' in line and not line.rstrip().endswith(',') and ('phase=' in next_line or 'original_error=' in next_line),
         lambda line: line.rstrip() + ',\n'),

        # Event publishing - correlation_id followed by other args
        (lambda line, next_line: 'correlation_id=' in line and not line.rstrip().endswith(',') and ('phase=' in next_line or 'plan_id=' in next_line or 'failure_reason=' in next_line),
         lambda line: line.rstrip() + ',\n'),
        (lambda line, next_line: 'phase=' in line and not line.rstrip().endswith(',') and ('task_description=' in next_line or 'plan_id=' in next_line or 'failure_reason=' in next_line or 'error_type=' in next_line),
         lambda line: line.rstrip() + ',\n'),
        (lambda line, next_line: 'plan_id=' in line and not line.rstrip().endswith(',') and 'plan_name=' in next_line,
         lambda line: line.rstrip() + ',\n'),
        (lambda line, next_line: 'failure_reason=' in line and not line.rstrip().endswith(',') and 'error_type=' in next_line,
         lambda line: line.rstrip() + ',\n'),
    ]

    # Apply fixes
    i = 0
    while i < len(lines):
        if i < len(lines) - 1:  # Have a next line
            for condition, fix_func in fix_patterns:
                if condition(lines[i], lines[i + 1]):
                    fixed_line = fix_func(lines[i])
                    if fixed_line != lines[i]:
                        lines[i] = fixed_line
                        fixes += 1
                        break  # Only apply one fix per line
        i += 1

    # Write back
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    print(f"Fixed {fixes} missing commas in agent.py")
    return fixes

if __name__ == '__main__':
    fix_agent_file()