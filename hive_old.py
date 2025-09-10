#!/usr/bin/env python3
"""
Hive CLI — single entrypoint to Queen, Workers, Status, and task ops.
Keeps architecture unchanged; just wraps your existing modules.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

# Import your existing modules
from queen_orchestrator import QueenOrchestrator
from hive_status import HiveStatus
from cc_worker import CCWorker

HIVE_ROOT = Path.cwd()
HIVE_DIR = HIVE_ROOT / "hive"
TASKS_DIR = HIVE_DIR / "tasks"
RESULTS_DIR = HIVE_DIR / "results"
BUS_DIR = HIVE_DIR / "bus"
OP_DIR = HIVE_DIR / "operator"
HINTS_DIR = OP_DIR / "hints"
INT_DIR = OP_DIR / "interrupts"
WORKTREES_DIR = HIVE_ROOT / ".worktrees"

def ensure_dirs():
    """Ensure all required directories exist"""
    for d in [HIVE_DIR, TASKS_DIR, RESULTS_DIR, BUS_DIR, OP_DIR, HINTS_DIR, INT_DIR, WORKTREES_DIR]:
        d.mkdir(parents=True, exist_ok=True)

def load_queue():
    """Load task queue from index.json"""
    idx = TASKS_DIR / "index.json"
    if idx.exists():
        try:
            return json.loads(idx.read_text()).get("queue", [])
        except Exception:
            return []
    return []

def save_queue(queue):
    """Save task queue to index.json"""
    (TASKS_DIR / "index.json").write_text(json.dumps({
        "queue": queue,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }, indent=2))

def load_task(task_id: str):
    """Load a task by ID"""
    tf = TASKS_DIR / f"{task_id}.json"
    if tf.exists():
        return json.loads(tf.read_text())
    return None

def save_task(task: dict):
    """Save a task to its file"""
    tf = TASKS_DIR / f"{task['id']}.json"
    tf.write_text(json.dumps(task, indent=2))

# ----------------- subcommand handlers -----------------

def cmd_init(args):
    """Initialize Hive directory structure"""
    ensure_dirs()
    print("[OK] HIVE directories ensured.")
    if args.sample:
        task = {
            "id": "tsk_001",
            "title": "Add /healthz endpoint",
            "description": "FastAPI route returning 200 + JSON",
            "tags": ["backend", "fastapi"],
            "priority": "P2",
            "risk": "low",
            "status": "queued"
        }
        save_task(task)
        q = load_queue()
        if "tsk_001" not in q:
            q.append("tsk_001")
        save_queue(q)
        print("[OK] Sample task tsk_001 created and queued.")

def cmd_queen(args):
    """Run the Queen orchestrator"""
    ensure_dirs()
    print("[Queen] Starting Queen Orchestrator (Ctrl+C to stop)...")
    try:
        QueenOrchestrator().run_forever()
    except KeyboardInterrupt:
        print("\n[Queen] Orchestrator stopped.")
        sys.exit(0)

def cmd_status(args):
    """Run the status dashboard"""
    ensure_dirs()
    try:
        HiveStatus().run(refresh_seconds=args.refresh)
    except KeyboardInterrupt:
        print("\n[Status] Dashboard stopped.")
        sys.exit(0)

def cmd_task_add(args):
    """Add a new task to the queue"""
    ensure_dirs()
    task = {
        "id": args.id,
        "title": args.title,
        "description": args.description or "",
        "tags": args.tags,
        "priority": args.priority,
        "risk": args.risk,
        "status": "queued",
    }
    save_task(task)
    q = load_queue()
    if args.front:
        # Remove if exists, then add to front
        q = [t for t in q if t != args.id]
        q.insert(0, args.id)
    else:
        if args.id not in q:
            q.append(args.id)
    save_queue(q)
    print(f"[Task] {args.id} saved and {'front-queued' if args.front else 'queued'}.")

def cmd_task_queue(args):
    """Show the current task queue"""
    q = load_queue()
    if not q:
        print("(queue empty)")
        return
    print("Queue:")
    for i, tid in enumerate(q, 1):
        task = load_task(tid)
        if task:
            print(f"  {i:02d}. {tid} - {task.get('title', 'No title')}")
        else:
            print(f"  {i:02d}. {tid} - (task file not found)")

def cmd_task_view(args):
    """View details of a specific task"""
    task = load_task(args.id)
    if task:
        print(json.dumps(task, indent=2))
    else:
        print(f"[Error] Task {args.id} not found")
        sys.exit(1)

def cmd_hint_set(args):
    """Set an operator hint for a task"""
    ensure_dirs()
    (HINTS_DIR / f"{args.id}.md").write_text(args.text)
    print(f"[Hint] Set for {args.id}")

def cmd_hint_clear(args):
    """Clear hint for a task"""
    p = HINTS_DIR / f"{args.id}.md"
    if p.exists():
        p.unlink()
        print(f"[Hint] Cleared for {args.id}")
    else:
        print(f"[Info] No hint found for {args.id}")

def cmd_interrupt_set(args):
    """Set an interrupt for a task"""
    ensure_dirs()
    (INT_DIR / f"{args.id}.json").write_text(json.dumps({"reason": args.reason}, indent=2))
    print(f"[Interrupt] Set for {args.id}: {args.reason}")

def cmd_interrupt_clear(args):
    """Clear interrupt for a task"""
    p = INT_DIR / f"{args.id}.json"
    if p.exists():
        p.unlink()
        print(f"[Interrupt] Cleared for {args.id}")
    else:
        print(f"[Info] No interrupt found for {args.id}")

def cmd_worker_oneshot(args):
    """Spawn a one-shot worker for a specific task"""
    ensure_dirs()
    # One-shot worker run for a specific task & role
    w = CCWorker(
        worker_id=args.role, 
        task_id=args.id, 
        run_id=args.run_id,
        workspace=args.workspace, 
        phase=args.phase
    )
    # Check if CCWorker has run_one_shot method, otherwise use run
    if hasattr(w, 'run_one_shot'):
        rc = w.run_one_shot()
    else:
        # Fallback to run method if run_one_shot doesn't exist
        rc = w.run()
    sys.exit(rc if rc is not None else 0)

def cmd_events_tail(args):
    """Tail the event bus in real-time"""
    ensure_dirs()
    
    def events_file():
        return BUS_DIR / f"events_{datetime.now().strftime('%Y%m%d')}.jsonl"
    
    pos = 0
    print("[Events] Tailing events... (Ctrl+C to stop)")
    try:
        while True:
            ef = events_file()
            if ef.exists():
                with ef.open("r", encoding="utf-8") as f:
                    f.seek(pos)
                    for line in f:
                        print(line.rstrip())
                    pos = f.tell()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[Events] Tailing stopped.")
        sys.exit(0)

# ----------------- argument parser -----------------

def build_parser():
    """Build the argument parser for all subcommands"""
    p = argparse.ArgumentParser(
        prog="hive", 
        description="Hive MAS CLI - Unified interface for Queen, Workers, and task operations"
    )
    sub = p.add_subparsers(dest="cmd", required=True, help="Available commands")

    # init command
    sp = sub.add_parser("init", help="Create directory structure (optionally seed sample task)")
    sp.add_argument("--sample", action="store_true", help="Create sample task tsk_001")
    sp.set_defaults(func=cmd_init)

    # queen command
    sp = sub.add_parser("queen", help="Run the Queen orchestrator (foreground)")
    sp.set_defaults(func=cmd_queen)

    # status command
    sp = sub.add_parser("status", help="Run the read-only status dashboard")
    sp.add_argument("--refresh", type=int, default=2, help="Refresh interval in seconds (default: 2)")
    sp.set_defaults(func=cmd_status)

    # task:add command
    sp = sub.add_parser("task:add", help="Add a task and queue it")
    sp.add_argument("--id", required=True, help="Task ID (e.g., tsk_001)")
    sp.add_argument("--title", required=True, help="Task title")
    sp.add_argument("--description", help="Task description")
    sp.add_argument("--tags", nargs="+", default=[], help="Task tags")
    sp.add_argument("--priority", default="P2", choices=["P0", "P1", "P2", "P3"], help="Priority level")
    sp.add_argument("--risk", default="low", choices=["low", "medium", "high"], help="Risk level")
    sp.add_argument("--front", action="store_true", help="Put task at front of queue")
    sp.set_defaults(func=cmd_task_add)

    # task:queue command
    sp = sub.add_parser("task:queue", help="Show queue order")
    sp.set_defaults(func=cmd_task_queue)

    # task:view command (bonus)
    sp = sub.add_parser("task:view", help="View task details")
    sp.add_argument("--id", required=True, help="Task ID to view")
    sp.set_defaults(func=cmd_task_view)

    # hint:set command
    sp = sub.add_parser("hint:set", help="Set operator hint text for task")
    sp.add_argument("--id", required=True, help="Task ID")
    sp.add_argument("--text", required=True, help="Hint text")
    sp.set_defaults(func=cmd_hint_set)

    # hint:clear command
    sp = sub.add_parser("hint:clear", help="Clear hint for task")
    sp.add_argument("--id", required=True, help="Task ID")
    sp.set_defaults(func=cmd_hint_clear)

    # interrupt:set command
    sp = sub.add_parser("interrupt:set", help="Interrupt a task with a reason")
    sp.add_argument("--id", required=True, help="Task ID")
    sp.add_argument("--reason", required=True, help="Interrupt reason")
    sp.set_defaults(func=cmd_interrupt_set)

    # interrupt:clear command
    sp = sub.add_parser("interrupt:clear", help="Clear interrupt for a task")
    sp.add_argument("--id", required=True, help="Task ID")
    sp.set_defaults(func=cmd_interrupt_clear)

    # worker:oneshot command
    sp = sub.add_parser("worker:oneshot", help="Spawn a one-shot worker for a task")
    sp.add_argument("--role", required=True, choices=["backend", "frontend", "infra"], help="Worker role")
    sp.add_argument("--id", required=True, help="Task ID")
    sp.add_argument("--phase", choices=["plan", "apply", "test"], default="apply", help="Execution phase")
    sp.add_argument("--workspace", help="Override workspace/worktree path")
    sp.add_argument("--run-id", help="Override run ID")
    sp.set_defaults(func=cmd_worker_oneshot)

    # events:tail command
    sp = sub.add_parser("events:tail", help="Tail today's event bus")
    sp.set_defaults(func=cmd_events_tail)

    return p

def main():
    """Main entry point for the CLI"""
    parser = build_parser()
    
    # Show help if no arguments
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)
    
    args = parser.parse_args()
    
    # Execute the selected command
    args.func(args)

if __name__ == "__main__":
    main()