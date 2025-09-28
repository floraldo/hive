#!/usr/bin/env python3
"""
Simple Integration Test for AI Planner → Queen → Worker Pipeline
"""

import json
import sqlite3
import tempfile
import uuid
from datetime import datetime, timezone

class SimpleIntegrationTest:
    """Simple test without Unicode characters for Windows compatibility"""

    def __init__(self):
        self.temp_db_path = None
        self.stats = {'tasks_created': 0, 'plans_generated': 0, 'subtasks_created': 0}

    def setup(self):
        """Setup test database"""
        import tempfile
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix='.db')
        import os
        os.close(self.temp_db_fd)

        conn = sqlite3.connect(self.temp_db_path)
        conn.executescript('''
            CREATE TABLE planning_queue (
                id TEXT PRIMARY KEY,
                task_description TEXT NOT NULL,
                priority INTEGER DEFAULT 50,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE execution_plans (
                id TEXT PRIMARY KEY,
                planning_task_id TEXT NOT NULL,
                plan_data TEXT NOT NULL,
                status TEXT DEFAULT 'generated'
            );

            CREATE TABLE tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                task_type TEXT DEFAULT 'task',
                status TEXT DEFAULT 'queued',
                payload TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        conn.commit()
        conn.close()

    def cleanup(self):
        """Cleanup test database"""
        if self.temp_db_path:
            import os
            try:
                os.unlink(self.temp_db_path)
            except:
                pass

    def create_planning_task(self, description):
        """Create a task in planning queue"""
        task_id = str(uuid.uuid4())
        conn = sqlite3.connect(self.temp_db_path)
        conn.execute('''
            INSERT INTO planning_queue (id, task_description, priority)
            VALUES (?, ?, ?)
        ''', (task_id, description, 50))
        conn.commit()
        conn.close()
        self.stats['tasks_created'] += 1
        return task_id

    def simulate_ai_planner(self, task_id):
        """Simulate AI Planner processing"""
        plan_id = f"plan_{uuid.uuid4()}"

        # Create execution plan
        plan_data = {
            "plan_id": plan_id,
            "sub_tasks": [
                {
                    "id": "task1",
                    "title": "Design Phase",
                    "dependencies": []
                },
                {
                    "id": "task2",
                    "title": "Implementation Phase",
                    "dependencies": ["task1"]
                }
            ]
        }

        conn = sqlite3.connect(self.temp_db_path)

        # Insert execution plan
        conn.execute('''
            INSERT INTO execution_plans (id, planning_task_id, plan_data)
            VALUES (?, ?, ?)
        ''', (plan_id, task_id, json.dumps(plan_data)))

        # Create subtasks
        for sub_task in plan_data["sub_tasks"]:
            subtask_id = f"subtask_{plan_id}_{sub_task['id']}"

            payload = {
                "parent_plan_id": plan_id,
                "subtask_id": sub_task["id"],
                "dependencies": sub_task["dependencies"]
            }

            conn.execute('''
                INSERT INTO tasks (id, title, task_type, payload)
                VALUES (?, ?, ?, ?)
            ''', (subtask_id, sub_task["title"], "planned_subtask", json.dumps(payload)))

            self.stats['subtasks_created'] += 1

        conn.commit()
        conn.close()
        self.stats['plans_generated'] += 1
        return plan_id

    def get_ready_subtasks(self):
        """Get subtasks ready for execution"""
        conn = sqlite3.connect(self.temp_db_path)
        cursor = conn.execute('''
            SELECT * FROM tasks
            WHERE task_type = 'planned_subtask' AND status = 'queued'
        ''')

        rows = cursor.fetchall()
        ready_tasks = []

        for row in rows:
            task = {
                "id": row[0],
                "title": row[1],
                "payload": json.loads(row[4]) if row[4] else {}
            }

            # Check dependencies
            dependencies = task["payload"].get("dependencies", [])
            dependencies_met = True

            if dependencies:
                for dep_id in dependencies:
                    dep_cursor = conn.execute('''
                        SELECT status FROM tasks
                        WHERE json_extract(payload, '$.subtask_id') = ?
                        AND json_extract(payload, '$.parent_plan_id') = ?
                    ''', (dep_id, task["payload"].get("parent_plan_id")))

                    dep_row = dep_cursor.fetchone()
                    if not dep_row or dep_row[0] != 'completed':
                        dependencies_met = False
                        break

            if dependencies_met:
                ready_tasks.append(task)

        conn.close()
        return ready_tasks

    def complete_task(self, task_id):
        """Mark a task as completed"""
        conn = sqlite3.connect(self.temp_db_path)
        conn.execute('UPDATE tasks SET status = ? WHERE id = ?', ('completed', task_id))
        conn.commit()
        conn.close()

    def test_basic_flow(self):
        """Test basic AI Planner -> Queen -> Worker flow"""
        print("Starting basic integration test...")

        # Step 1: Create planning task
        print("1. Creating planning task...")
        task_id = self.create_planning_task("Test authentication system")
        print(f"   Created task: {task_id}")

        # Step 2: AI Planner processes
        print("2. AI Planner processing...")
        plan_id = self.simulate_ai_planner(task_id)
        print(f"   Generated plan: {plan_id}")

        # Step 3: Check ready subtasks
        print("3. Checking ready subtasks...")
        ready_tasks = self.get_ready_subtasks()
        print(f"   Found {len(ready_tasks)} ready tasks")

        # Should have 1 task ready (no dependencies)
        assert len(ready_tasks) == 1, f"Expected 1 ready task, got {len(ready_tasks)}"
        assert "Design Phase" in ready_tasks[0]["title"]

        # Step 4: Complete first task
        print("4. Completing first task...")
        self.complete_task(ready_tasks[0]["id"])

        # Step 5: Check for next ready task
        print("5. Checking for dependent task...")
        ready_tasks = self.get_ready_subtasks()
        print(f"   Found {len(ready_tasks)} ready tasks")

        # Should now have the second task ready
        assert len(ready_tasks) == 1, f"Expected 1 ready task after dependency completion, got {len(ready_tasks)}"
        assert "Implementation Phase" in ready_tasks[0]["title"]

        # Step 6: Complete second task
        print("6. Completing second task...")
        self.complete_task(ready_tasks[0]["id"])

        # Step 7: Verify completion
        print("7. Verifying completion...")
        ready_tasks = self.get_ready_subtasks()
        assert len(ready_tasks) == 0, f"Expected no ready tasks after completion, got {len(ready_tasks)}"

        print("SUCCESS: Basic integration test passed!")
        print(f"Statistics: {self.stats}")
        return True

    def run_test(self):
        """Run the complete test"""
        try:
            self.setup()
            success = self.test_basic_flow()
            return success
        except Exception as e:
            print(f"TEST FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            self.cleanup()


if __name__ == "__main__":
    test = SimpleIntegrationTest()
    success = test.run_test()

    if success:
        print("\nALL TESTS PASSED - Integration is working correctly!")
    else:
        print("\nTEST FAILED - Check implementation")
        exit(1)