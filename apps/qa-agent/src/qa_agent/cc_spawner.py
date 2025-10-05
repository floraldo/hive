"""CC Worker Spawner - Spawn CC Terminals with RAG Context.

Spawns headless or interactive CC terminals for complex QA tasks,
injecting RAG context via startup script environment variables.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from hive_config import HiveConfig
from hive_logging import get_logger

logger = get_logger(__name__)


class CCWorkerSpawner:
    """Spawn CC terminals with RAG context injection.

    Manages lifecycle of CC worker processes:
    - Headless workers for complex automated tasks
    - Interactive workers for HITL review and escalation
    - Worker registration in hive-orchestrator database
    - Process health monitoring

    Example:
        spawner = CCWorkerSpawner(config, db)
        process = await spawner.spawn_headless(task, rag_context)
    """

    def __init__(
        self,
        config: HiveConfig | None = None,
        db: Any | None = None,
    ):
        """Initialize CC worker spawner.

        Args:
            config: Hive configuration
            db: Database connection for worker registry
        """
        self.config = config
        self.db = db
        self.logger = logger

        # Active workers
        self.active_workers: dict[str, dict[str, Any]] = {}

        # Template paths
        self.templates_dir = Path(__file__).parent.parent.parent / "cli" / "templates"

        self.logger.info("CC worker spawner initialized")

    async def spawn_headless(
        self,
        task: dict[str, Any],
        rag_context: list[dict[str, Any]],
    ) -> asyncio.subprocess.Process:
        """Spawn headless CC worker for complex task.

        Args:
            task: Task dictionary from hive-orchestrator
            rag_context: Retrieved RAG patterns for context injection

        Returns:
            Subprocess handle for spawned CC terminal

        Example:
            process = await spawner.spawn_headless(
                task={"id": "task-123", "payload": {...}},
                rag_context=[{"fix_pattern": "..."}]
            )
        """
        task_id = task.get("id", "unknown")
        self.logger.info(f"Spawning headless CC worker for task: {task_id}")

        # Build worker persona with RAG context
        from .persona_builder import build_worker_persona

        persona = build_worker_persona(
            task=task,
            rag_context=rag_context,
            mode="headless",
        )

        # Generate startup script
        startup_script = self._generate_startup_script(
            persona=persona,
            template_type="headless",
        )

        # Write startup script to temp file
        startup_file = self._write_startup_script(startup_script, task_id)

        # Spawn CC terminal subprocess
        process = await self._spawn_cc_process(
            startup_file=startup_file,
            worker_id=persona["worker_id"],
            headless=True,
        )

        # Register worker in database
        await self._register_worker(
            worker_id=persona["worker_id"],
            task_id=task_id,
            process_id=process.pid,
            worker_type="cc-terminal-headless",
        )

        # Track in active workers
        self.active_workers[persona["worker_id"]] = {
            "task_id": task_id,
            "process": process,
            "persona": persona,
            "started_at": datetime.now(),
        }

        self.logger.info(
            f"Headless CC worker spawned: {persona['worker_id']} (PID: {process.pid})"
        )

        return process

    async def spawn_interactive(
        self,
        task: dict[str, Any],
        rag_context: list[dict[str, Any]],
        escalation_reason: str,
    ) -> asyncio.subprocess.Process:
        """Spawn interactive CC worker for HITL review.

        Opens terminal UI for human to review and resolve complex violations.

        Args:
            task: Task dictionary from hive-orchestrator
            rag_context: Retrieved RAG patterns for context
            escalation_reason: Why this was escalated to HITL

        Returns:
            Subprocess handle for spawned interactive CC terminal

        Example:
            process = await spawner.spawn_interactive(
                task={"id": "task-456", "payload": {...}},
                rag_context=[...],
                escalation_reason="Critical security violation"
            )
        """
        task_id = task.get("id", "unknown")
        self.logger.info(
            f"Spawning interactive CC worker for HITL: {task_id} "
            f"(reason: {escalation_reason})"
        )

        # Build worker persona with escalation context
        from .persona_builder import build_worker_persona

        persona = build_worker_persona(
            task=task,
            rag_context=rag_context,
            mode="interactive",
            escalation_reason=escalation_reason,
        )

        # Generate startup script
        startup_script = self._generate_startup_script(
            persona=persona,
            template_type="interactive",
        )

        # Write startup script to temp file
        startup_file = self._write_startup_script(startup_script, task_id)

        # Spawn CC terminal subprocess (interactive mode)
        process = await self._spawn_cc_process(
            startup_file=startup_file,
            worker_id=persona["worker_id"],
            headless=False,
        )

        # Register worker in database
        await self._register_worker(
            worker_id=persona["worker_id"],
            task_id=task_id,
            process_id=process.pid,
            worker_type="cc-terminal-interactive",
        )

        # Track in active workers
        self.active_workers[persona["worker_id"]] = {
            "task_id": task_id,
            "process": process,
            "persona": persona,
            "started_at": datetime.now(),
            "escalation_reason": escalation_reason,
        }

        self.logger.info(
            f"Interactive CC worker spawned: {persona['worker_id']} (PID: {process.pid})"
        )

        return process

    def _generate_startup_script(
        self,
        persona: dict[str, Any],
        template_type: str,
    ) -> str:
        """Generate startup script from template with persona injection.

        Args:
            persona: Worker persona with RAG context
            template_type: Template type ('headless' or 'interactive')

        Returns:
            Startup script content with environment variables
        """
        # Load template
        template_file = self.templates_dir / f"{template_type}_worker_startup.sh"

        if not template_file.exists():
            self.logger.warning(f"Template not found: {template_file}, using default")
            template_content = self._get_default_template(template_type)
        else:
            with open(template_file) as f:
                template_content = f.read()

        # Inject persona data
        script = template_content.format(
            worker_id=persona["worker_id"],
            task_id=persona["task"]["id"],
            task_description=persona["task"]["description"],
            rag_context_json=json.dumps(persona["rag_context"]),
            violations_json=json.dumps(persona.get("violations", [])),
            qa_type=persona["task"].get("qa_type", "unknown"),
            escalation_reason=persona.get("escalation_reason", "N/A"),
        )

        return script

    def _get_default_template(self, template_type: str) -> str:
        """Get default startup script template if file not found.

        Args:
            template_type: Template type ('headless' or 'interactive')

        Returns:
            Default template content
        """
        if template_type == "headless":
            return """#!/bin/bash
# Headless CC Worker Startup Script
# Worker ID: {worker_id}
# Task: {task_id}

export WORKER_ID="{worker_id}"
export TASK_ID="{task_id}"
export QA_TYPE="{qa_type}"
export RAG_CONTEXT='{rag_context_json}'
export VIOLATIONS='{violations_json}'

echo "QA Worker {worker_id} starting..."
echo "Task: {task_description}"
echo "RAG Context: $(echo $RAG_CONTEXT | jq length) patterns loaded"

# Execute worker logic
# TODO: Implement actual CC worker execution
echo "Worker execution placeholder"
"""
        else:  # interactive
            return """#!/bin/bash
# Interactive CC Worker Startup Script (HITL)
# Worker ID: {worker_id}
# Task: {task_id}
# Escalation: {escalation_reason}

export WORKER_ID="{worker_id}"
export TASK_ID="{task_id}"
export QA_TYPE="{qa_type}"
export RAG_CONTEXT='{rag_context_json}'
export VIOLATIONS='{violations_json}'
export ESCALATION_REASON="{escalation_reason}"

echo "========================================="
echo "HITL REVIEW REQUIRED"
echo "========================================="
echo "Worker: {worker_id}"
echo "Task: {task_description}"
echo "Reason: {escalation_reason}"
echo "RAG Context: $(echo $RAG_CONTEXT | jq length) patterns available"
echo ""
echo "Press Ctrl+C to exit when review complete"
echo "========================================="

# Open interactive terminal for human review
# TODO: Implement interactive CC terminal
read -p "Press Enter to continue..."
"""

    def _write_startup_script(self, script_content: str, task_id: str) -> Path:
        """Write startup script to temporary file.

        Args:
            script_content: Script content
            task_id: Task ID for filename

        Returns:
            Path to temporary startup script
        """
        # Create temp file
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".sh",
            prefix=f"qa_worker_{task_id}_",
            delete=False,
        ) as f:
            f.write(script_content)
            script_path = Path(f.name)

        # Make executable
        script_path.chmod(0o755)

        self.logger.info(f"Startup script written: {script_path}")

        return script_path

    async def _spawn_cc_process(
        self,
        startup_file: Path,
        worker_id: str,
        headless: bool,
    ) -> asyncio.subprocess.Process:
        """Spawn CC terminal subprocess.

        Args:
            startup_file: Path to startup script
            worker_id: Worker ID
            headless: If True, run in headless mode

        Returns:
            Subprocess handle
        """
        # Build command
        # For MVP, we'll just run the bash script directly
        # In production, this would invoke Claude Code CLI with the script
        cmd = ["/bin/bash", str(startup_file)]

        if headless:
            # Headless mode - capture output
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={
                    **dict(asyncio.subprocess.os.environ),
                    "CC_WORKER_MODE": "headless",
                    "WORKER_ID": worker_id,
                },
            )
        else:
            # Interactive mode - inherit terminal
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={
                    **dict(asyncio.subprocess.os.environ),
                    "CC_WORKER_MODE": "interactive",
                    "WORKER_ID": worker_id,
                },
            )

        self.logger.info(f"CC process spawned: PID {process.pid}")

        return process

    async def _register_worker(
        self,
        worker_id: str,
        task_id: str,
        process_id: int,
        worker_type: str,
    ) -> None:
        """Register worker in hive-orchestrator database.

        Args:
            worker_id: Worker ID
            task_id: Task ID
            process_id: Process PID
            worker_type: Worker type
        """
        if not self.db:
            self.logger.warning("Database not available, worker not registered")
            return

        try:
            await self.db.register_worker(
                worker_id=worker_id,
                task_id=task_id,
                process_id=process_id,
                worker_type=worker_type,
                status="active",
                registered_at=datetime.now(),
            )

            self.logger.info(f"Worker registered in database: {worker_id}")

        except Exception as e:
            self.logger.error(f"Worker registration failed: {e}", exc_info=True)

    async def shutdown_all(self) -> None:
        """Shutdown all active CC workers gracefully."""
        self.logger.info(f"Shutting down {len(self.active_workers)} active workers...")

        for worker_id, worker_info in list(self.active_workers.items()):
            try:
                process = worker_info["process"]

                # Send SIGTERM for graceful shutdown
                process.terminate()

                # Wait up to 10s for graceful shutdown
                try:
                    await asyncio.wait_for(process.wait(), timeout=10.0)
                    self.logger.info(f"Worker {worker_id} terminated gracefully")
                except TimeoutError:
                    # Force kill if not responding
                    process.kill()
                    self.logger.warning(f"Worker {worker_id} force-killed after timeout")

            except Exception as e:
                self.logger.error(f"Failed to shutdown worker {worker_id}: {e}")

        self.active_workers.clear()
        self.logger.info("All workers shutdown complete")

    def get_active_workers(self) -> dict[str, dict[str, Any]]:
        """Get dictionary of active workers.

        Returns:
            Dictionary mapping worker_id to worker info
        """
        return self.active_workers.copy()

    def get_worker_count(self) -> int:
        """Get count of active workers.

        Returns:
            Number of active workers
        """
        return len(self.active_workers)


__all__ = ["CCWorkerSpawner"]
