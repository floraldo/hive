#!/usr/bin/env python3
"""Complete an escalated review."""
import sys
from pathlib import Path

# Add packages to path
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "hive-core-db" / "src"))

from hive_core_db.database import Database

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: hive_complete_review.py <task_id> <decision> <comments>")
        sys.exit(1)

    task_id = int(sys.argv[1])
    decision = sys.argv[2]
    comments = sys.argv[3]

    db = Database()

    # Update the task based on decision
    if decision == "approve":
        db.update_task_state(task_id, "test", metadata={"review_decision": "approved", "review_comments": comments})
    elif decision == "rework":
        db.update_task_state(task_id, "queued", metadata={"review_decision": "rework", "review_comments": comments})
    else:
        print(f"Invalid decision: {decision}. Must be 'approve' or 'rework'")
        sys.exit(1)

    print(f"Review completed for task {task_id}: {decision}")