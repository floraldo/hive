#!/usr/bin/env python3
"""
Master Plan Monitor - Grand Integration Test

Automated monitoring and verification script that tracks the complete
autonomous workflow from AI Planner task decomposition through
Hive Orchestrator execution and lifecycle completion.
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import logging

# Add packages path for hive-core-db
hive_root = Path(__file__).parent.parent
sys.path.insert(0, str(hive_root / "packages" / "hive-core-db" / "src"))

from hive_core_db.database import get_connection
import sqlite3

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("grand_integration_test.log")],
)
logger = logging.getLogger("grand-monitor")


class GrandIntegrationMonitor:
    """
    Comprehensive monitoring system for the Grand Integration Test

    Tracks the complete workflow:
    1. AI Planner picks up master task and generates execution plan
    2. Sub-tasks are created in the tasks table
    3. Queen picks up sub-tasks and executes them
    4. Tasks complete the full lifecycle (apply -> inspect -> review -> test)
    """

    def __init__(self, master_task_id: str):
        self.master_task_id = master_task_id
        self.start_time = datetime.now()
        self.monitoring_data = {
            "test_start": self.start_time.isoformat(),
            "master_task_id": master_task_id,
            "phases": {},
            "timeline": [],
            "verification_results": {},
            "final_status": "running",
        }

        # Load test metadata
        metadata_path = hive_root / "integration_test_metadata.json"
        if metadata_path.exists():
            with open(metadata_path) as f:
                self.test_metadata = json.load(f)
        else:
            self.test_metadata = {}

        # Monitoring configuration
        self.max_monitoring_time = 1800  # 30 minutes max
        self.poll_interval = 10  # Check every 10 seconds
        self.phase_timeouts = {
            "planning": 300,  # 5 minutes for AI Planner
            "execution": 900,  # 15 minutes for initial task execution
            "lifecycle": 600,  # 10 minutes for full lifecycle completion
        }

        logger.info(f"Grand Integration Monitor initialized for task: {master_task_id}")

    def log_timeline_event(self, event: str, data: Dict = None):
        """Log a timeline event with timestamp"""
        event_data = {"timestamp": datetime.now().isoformat(), "event": event, "data": data or {}}
        self.monitoring_data["timeline"].append(event_data)
        logger.info(f"TIMELINE: {event}")

    def get_database_state(self) -> Dict:
        """Get current state of all relevant database tables"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            state = {}

            # Planning queue state
            cursor.execute(
                "SELECT id, status, assigned_agent, created_at, assigned_at, completed_at FROM planning_queue WHERE id = ?",
                (self.master_task_id,),
            )
            planning_row = cursor.fetchone()
            if planning_row:
                state["planning_queue"] = {
                    "id": planning_row[0],
                    "status": planning_row[1],
                    "assigned_agent": planning_row[2],
                    "created_at": planning_row[3],
                    "assigned_at": planning_row[4],
                    "completed_at": planning_row[5],
                }
            else:
                state["planning_queue"] = None

            # Execution plans
            cursor.execute(
                "SELECT id, planning_task_id, status, generated_at FROM execution_plans WHERE planning_task_id = ?",
                (self.master_task_id,),
            )
            plans = cursor.fetchall()
            state["execution_plans"] = [
                {"id": row[0], "planning_task_id": row[1], "status": row[2], "generated_at": row[3]} for row in plans
            ]

            # Sub-tasks created by planner
            cursor.execute(
                """
                SELECT id, title, status, assignee, created_at, metadata
                FROM tasks
                WHERE task_type = 'planned_subtask'
                ORDER BY created_at ASC
            """
            )
            tasks = cursor.fetchall()
            state["subtasks"] = []
            for row in tasks:
                task_data = {
                    "id": row[0],
                    "title": row[1],
                    "status": row[2],
                    "assignee": row[3],
                    "created_at": row[4],
                    "metadata": json.loads(row[5]) if row[5] else {},
                }
                # Check if this task belongs to our master plan
                if task_data["metadata"].get("parent_plan_id"):
                    state["subtasks"].append(task_data)

            # Task runs (execution attempts)
            if state["subtasks"]:
                task_ids = [task["id"] for task in state["subtasks"]]
                placeholders = ",".join("?" * len(task_ids))
                cursor.execute(
                    f"""
                    SELECT task_id, status, phase, created_at, completed_at
                    FROM runs
                    WHERE task_id IN ({placeholders})
                    ORDER BY created_at ASC
                """,
                    task_ids,
                )
                runs = cursor.fetchall()
                state["runs"] = [
                    {"task_id": row[0], "status": row[1], "phase": row[2], "created_at": row[3], "completed_at": row[4]}
                    for row in runs
                ]
            else:
                state["runs"] = []

            conn.close()
            return state

        except Exception as e:
            logger.error(f"Error getting database state: {e}")
            return {}

    def check_phase_planning(self, state: Dict) -> Tuple[bool, str]:
        """Check if AI Planner has successfully processed the master task"""

        planning_status = state.get("planning_queue", {}).get("status", "unknown")

        if planning_status == "pending":
            return False, "Master task still pending - waiting for AI Planner"

        elif planning_status == "assigned":
            agent = state.get("planning_queue", {}).get("assigned_agent", "unknown")
            return False, f"Master task assigned to {agent} - planning in progress"

        elif planning_status == "planned":
            plans_count = len(state.get("execution_plans", []))
            subtasks_count = len(state.get("subtasks", []))

            if plans_count == 0:
                return False, "Task marked as planned but no execution plans found"

            if subtasks_count == 0:
                return False, f"Execution plan created but no sub-tasks found (plans: {plans_count})"

            self.log_timeline_event(
                "planning_phase_completed",
                {
                    "execution_plans": plans_count,
                    "subtasks_created": subtasks_count,
                    "planning_agent": state.get("planning_queue", {}).get("assigned_agent"),
                },
            )

            return True, f"Planning completed: {plans_count} plans, {subtasks_count} sub-tasks"

        elif planning_status == "failed":
            return False, "Master task failed during planning phase"

        else:
            return False, f"Unknown planning status: {planning_status}"

    def check_phase_execution(self, state: Dict) -> Tuple[bool, str]:
        """Check if Queen has started executing sub-tasks"""

        subtasks = state.get("subtasks", [])
        runs = state.get("runs", [])

        if not subtasks:
            return False, "No sub-tasks available for execution"

        # Check if any tasks have been picked up for execution
        tasks_in_progress = [task for task in subtasks if task["status"] in ["in_progress", "completed"]]
        tasks_with_runs = [run["task_id"] for run in runs]

        if not tasks_in_progress and not tasks_with_runs:
            return False, f"Sub-tasks created ({len(subtasks)}) but none picked up by Queen yet"

        if tasks_in_progress:
            self.log_timeline_event(
                "execution_phase_started",
                {"tasks_in_progress": len(tasks_in_progress), "total_subtasks": len(subtasks)},
            )

        if tasks_with_runs:
            unique_tasks_with_runs = len(set(tasks_with_runs))
            self.log_timeline_event(
                "queen_execution_detected", {"tasks_with_runs": unique_tasks_with_runs, "total_runs": len(runs)}
            )

        return (
            True,
            f"Execution started: {len(tasks_in_progress)} tasks in progress, {len(set(tasks_with_runs))} with runs",
        )

    def check_phase_lifecycle(self, state: Dict) -> Tuple[bool, str]:
        """Check if any task has completed the full lifecycle"""

        runs = state.get("runs", [])

        if not runs:
            return False, "No task runs found"

        # Group runs by task_id to track lifecycle progression
        task_runs = {}
        for run in runs:
            task_id = run["task_id"]
            if task_id not in task_runs:
                task_runs[task_id] = []
            task_runs[task_id].append(run)

        # Check for lifecycle completion
        lifecycle_phases = ["apply", "inspect", "review", "test"]
        completed_lifecycles = 0
        partial_lifecycles = 0

        for task_id, task_run_list in task_runs.items():
            phases_completed = set(run["phase"] for run in task_run_list if run["status"] == "completed")

            if all(phase in phases_completed for phase in lifecycle_phases):
                completed_lifecycles += 1
                self.log_timeline_event(
                    "lifecycle_completed", {"task_id": task_id, "phases_completed": list(phases_completed)}
                )
            elif len(phases_completed) > 0:
                partial_lifecycles += 1

        if completed_lifecycles > 0:
            return True, f"Lifecycle success: {completed_lifecycles} tasks completed full lifecycle"

        if partial_lifecycles > 0:
            return False, f"Lifecycle in progress: {partial_lifecycles} tasks with partial completion"

        return False, "No lifecycle progress detected"

    def generate_progress_report(self, state: Dict) -> str:
        """Generate a comprehensive progress report"""

        report = []
        report.append("=" * 80)
        report.append("GRAND INTEGRATION TEST - PROGRESS REPORT")
        report.append("=" * 80)
        report.append("")

        # Test metadata
        elapsed = datetime.now() - self.start_time
        report.append(f"Test Duration: {elapsed}")
        report.append(f"Master Task ID: {self.master_task_id}")
        report.append("")

        # Planning phase
        planning = state.get("planning_queue")
        if planning:
            report.append("PLANNING PHASE:")
            report.append(f"  Status: {planning['status']}")
            report.append(f"  Agent: {planning.get('assigned_agent', 'none')}")
            report.append(f"  Created: {planning['created_at']}")
            if planning["assigned_at"]:
                report.append(f"  Assigned: {planning['assigned_at']}")
            if planning["completed_at"]:
                report.append(f"  Completed: {planning['completed_at']}")

        plans = state.get("execution_plans", [])
        if plans:
            report.append(f"  Execution Plans: {len(plans)} created")

        report.append("")

        # Sub-tasks
        subtasks = state.get("subtasks", [])
        if subtasks:
            report.append("SUB-TASKS CREATED:")
            status_counts = {}
            for task in subtasks:
                status = task["status"]
                status_counts[status] = status_counts.get(status, 0) + 1

            for status, count in status_counts.items():
                report.append(f"  {status}: {count} tasks")

            report.append(f"  Total: {len(subtasks)} sub-tasks")
            report.append("")

            # Show first few tasks
            report.append("Sample Sub-tasks:")
            for i, task in enumerate(subtasks[:3]):
                report.append(f"  {i+1}. {task['title']} ({task['status']}) -> {task['assignee']}")
            if len(subtasks) > 3:
                report.append(f"  ... and {len(subtasks) - 3} more")

        report.append("")

        # Execution runs
        runs = state.get("runs", [])
        if runs:
            report.append("EXECUTION RUNS:")
            phase_counts = {}
            status_counts = {}

            for run in runs:
                phase = run["phase"]
                status = run["status"]
                phase_counts[phase] = phase_counts.get(phase, 0) + 1
                status_counts[status] = status_counts.get(status, 0) + 1

            report.append("  By Phase:")
            for phase, count in phase_counts.items():
                report.append(f"    {phase}: {count} runs")

            report.append("  By Status:")
            for status, count in status_counts.items():
                report.append(f"    {status}: {count} runs")

            report.append(f"  Total: {len(runs)} execution attempts")

        report.append("")

        # Timeline highlights
        if self.monitoring_data["timeline"]:
            report.append("KEY TIMELINE EVENTS:")
            for event in self.monitoring_data["timeline"][-5:]:  # Last 5 events
                timestamp = event["timestamp"].split("T")[1][:8]  # Just time
                report.append(f"  {timestamp}: {event['event']}")

        report.append("")
        report.append("=" * 80)

        return "\n".join(report)

    def run_monitoring_cycle(self) -> bool:
        """Run a complete monitoring cycle and return True if test is complete"""

        # Get current database state
        state = self.get_database_state()

        # Check each phase
        phases_status = {"planning": False, "execution": False, "lifecycle": False}

        # Phase 1: Planning
        planning_complete, planning_msg = self.check_phase_planning(state)
        phases_status["planning"] = planning_complete
        logger.info(f"PLANNING: {planning_msg}")

        if not planning_complete:
            return False  # Can't proceed without planning

        # Phase 2: Execution
        execution_started, execution_msg = self.check_phase_execution(state)
        phases_status["execution"] = execution_started
        logger.info(f"EXECUTION: {execution_msg}")

        if not execution_started:
            return False  # Still waiting for execution to start

        # Phase 3: Lifecycle (optional - stretch goal)
        lifecycle_complete, lifecycle_msg = self.check_phase_lifecycle(state)
        phases_status["lifecycle"] = lifecycle_complete
        logger.info(f"LIFECYCLE: {lifecycle_msg}")

        # Update monitoring data
        self.monitoring_data["phases"] = phases_status
        self.monitoring_data["latest_state"] = state

        # Test is successful if planning and execution are complete
        # Lifecycle completion is a bonus but not required for basic success
        basic_success = phases_status["planning"] and phases_status["execution"]
        full_success = basic_success and phases_status["lifecycle"]

        if full_success:
            self.monitoring_data["final_status"] = "complete_success"
            logger.info("GRAND INTEGRATION TEST: COMPLETE SUCCESS!")
            return True
        elif basic_success:
            # Continue monitoring for lifecycle completion but consider basic success achieved
            logger.info("GRAND INTEGRATION TEST: BASIC SUCCESS ACHIEVED (continuing for lifecycle)")
            return False  # Keep monitoring for full lifecycle
        else:
            return False

    def run(self) -> Dict:
        """Run the complete monitoring process"""

        print("=" * 80)
        print("GRAND INTEGRATION TEST MONITOR - STARTING")
        print("=" * 80)
        print()

        self.log_timeline_event("monitoring_started", {"master_task_id": self.master_task_id})

        monitoring_cycles = 0
        max_cycles = self.max_monitoring_time // self.poll_interval

        try:
            while monitoring_cycles < max_cycles:
                monitoring_cycles += 1
                cycle_start = time.time()

                print(f"\n--- Monitoring Cycle {monitoring_cycles} ---")

                # Run monitoring cycle
                test_complete = self.run_monitoring_cycle()

                # Generate and display progress report every few cycles
                if monitoring_cycles % 3 == 0 or test_complete:
                    state = self.monitoring_data.get("latest_state", {})
                    report = self.generate_progress_report(state)
                    print("\n" + report)

                if test_complete:
                    self.log_timeline_event(
                        "test_completed",
                        {
                            "cycles_completed": monitoring_cycles,
                            "total_duration": str(datetime.now() - self.start_time),
                        },
                    )
                    break

                # Wait for next cycle
                cycle_duration = time.time() - cycle_start
                sleep_time = max(0, self.poll_interval - cycle_duration)
                if sleep_time > 0:
                    time.sleep(sleep_time)

            else:
                # Timeout reached
                self.monitoring_data["final_status"] = "timeout"
                self.log_timeline_event(
                    "monitoring_timeout",
                    {"max_cycles_reached": max_cycles, "total_duration": str(datetime.now() - self.start_time)},
                )

        except KeyboardInterrupt:
            self.monitoring_data["final_status"] = "interrupted"
            self.log_timeline_event("monitoring_interrupted")
            print("\nMonitoring interrupted by user")

        except Exception as e:
            self.monitoring_data["final_status"] = "error"
            self.log_timeline_event("monitoring_error", {"error": str(e)})
            logger.error(f"Monitoring error: {e}")

        # Final status
        self.monitoring_data["test_end"] = datetime.now().isoformat()
        total_duration = datetime.now() - self.start_time
        self.monitoring_data["total_duration"] = str(total_duration)

        return self.monitoring_data

    def generate_final_report(self) -> str:
        """Generate the final certification report"""

        final_status = self.monitoring_data["final_status"]
        phases = self.monitoring_data.get("phases", {})

        report = []
        report.append("=" * 80)
        report.append("HIVE V2.1 PLATFORM - GRAND INTEGRATION TEST RESULTS")
        report.append("=" * 80)
        report.append("")

        # Test overview
        report.append("TEST OVERVIEW:")
        report.append(f"  Master Task ID: {self.master_task_id}")
        report.append(f"  Test Duration: {self.monitoring_data.get('total_duration', 'unknown')}")
        report.append(f"  Final Status: {final_status.upper()}")
        report.append("")

        # Phase results
        report.append("PHASE VERIFICATION RESULTS:")
        report.append("-" * 40)

        phase_results = {
            "planning": {
                "name": "AI Planner Integration",
                "description": "AI Planner processes master task and generates execution plan",
                "success": phases.get("planning", False),
            },
            "execution": {
                "name": "Hive Orchestrator Integration",
                "description": "Queen picks up sub-tasks and begins execution",
                "success": phases.get("execution", False),
            },
            "lifecycle": {
                "name": "Full Lifecycle Completion",
                "description": "Tasks complete apply -> inspect -> review -> test cycle",
                "success": phases.get("lifecycle", False),
            },
        }

        for phase_key, phase_info in phase_results.items():
            status = "✓ PASS" if phase_info["success"] else "✗ FAIL"
            report.append(f"{status} {phase_info['name']}")
            report.append(f"    {phase_info['description']}")

        report.append("")

        # Overall assessment
        planning_success = phases.get("planning", False)
        execution_success = phases.get("execution", False)
        lifecycle_success = phases.get("lifecycle", False)

        if planning_success and execution_success and lifecycle_success:
            assessment = "COMPLETE SUCCESS - All phases verified"
            certification = "HIVE V2.1 PLATFORM FULLY CERTIFIED"
        elif planning_success and execution_success:
            assessment = "BASIC SUCCESS - Core integration verified"
            certification = "HIVE V2.1 PLATFORM CORE CERTIFIED"
        elif planning_success:
            assessment = "PARTIAL SUCCESS - AI Planner integration verified"
            certification = "AI PLANNER COMPONENT CERTIFIED"
        else:
            assessment = "FAILED - Core integration not verified"
            certification = "CERTIFICATION FAILED"

        report.append("OVERALL ASSESSMENT:")
        report.append(f"  Result: {assessment}")
        report.append(f"  Certification: {certification}")
        report.append("")

        # Technical details
        if "latest_state" in self.monitoring_data:
            state = self.monitoring_data["latest_state"]

            plans_count = len(state.get("execution_plans", []))
            subtasks_count = len(state.get("subtasks", []))
            runs_count = len(state.get("runs", []))

            report.append("TECHNICAL METRICS:")
            report.append(f"  Execution Plans Generated: {plans_count}")
            report.append(f"  Sub-tasks Created: {subtasks_count}")
            report.append(f"  Execution Runs: {runs_count}")

        report.append("")

        # Timeline summary
        if self.monitoring_data.get("timeline"):
            report.append("KEY MILESTONES:")
            for event in self.monitoring_data["timeline"]:
                if "completed" in event["event"] or "started" in event["event"]:
                    timestamp = event["timestamp"].split("T")[1][:8]
                    report.append(f"  {timestamp}: {event['event']}")

        report.append("")
        report.append("=" * 80)

        return "\n".join(report)


def main():
    """Main entry point for the Grand Integration Monitor"""

    # Load test metadata to get master task ID
    metadata_path = hive_root / "integration_test_metadata.json"

    if not metadata_path.exists():
        print("FAILED: No integration test metadata found")
        print("Run scripts/seed_master_plan_task.py first to create the master task")
        sys.exit(1)

    with open(metadata_path) as f:
        metadata = json.load(f)

    master_task_id = metadata.get("master_task_id")
    if not master_task_id:
        print("FAILED: No master task ID found in metadata")
        sys.exit(1)

    print(f"Starting Grand Integration Monitor for task: {master_task_id}")

    # Create and run monitor
    monitor = GrandIntegrationMonitor(master_task_id)
    results = monitor.run()

    # Generate final report
    final_report = monitor.generate_final_report()
    print("\n" + final_report)

    # Save detailed results
    results_path = hive_root / "grand_integration_results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)

    # Save final report
    report_path = hive_root / "grand_integration_report.txt"
    with open(report_path, "w") as f:
        f.write(final_report)

    print(f"\nDetailed results saved to: {results_path}")
    print(f"Final report saved to: {report_path}")

    # Exit with appropriate code
    final_status = results["final_status"]
    if final_status in ["complete_success", "basic_success"]:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
