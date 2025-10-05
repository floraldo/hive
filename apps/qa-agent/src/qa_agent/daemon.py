"""QA Agent Daemon - Autonomous Quality Enforcement Service.

Background service that continuously processes QA tasks from the hive-orchestrator queue,
intelligently routing violations to Chimera agents (fast, lightweight) or CC workers
(deep reasoning) based on complexity scoring.
"""

from __future__ import annotations

import asyncio
import signal
from datetime import datetime
from typing import Any

from hive_config import HiveConfig, create_config_from_sources
from hive_logging import get_logger
from hive_orchestration.client import OrchestrationClient

logger = get_logger(__name__)


class QAAgentDaemon:
    """Background daemon for autonomous QA task execution.

    Polls hive-orchestrator queue and intelligently routes violations:
    - Simple fixes → Chimera agents (in-process, fast)
    - Complex tasks → CC workers (spawned terminals, deep reasoning)
    - Critical issues → Interactive CC (HITL review)

    Example:
        daemon = QAAgentDaemon()
        await daemon.start()  # Runs until stopped (Ctrl+C)
    """

    def __init__(
        self,
        config: HiveConfig | None = None,
        poll_interval: float = 5.0,
        max_concurrent_chimera: int = 3,
        max_concurrent_cc_workers: int = 2,
    ):
        """Initialize QA Agent daemon.

        Args:
            config: Hive configuration (uses default if not provided)
            poll_interval: Queue polling interval in seconds
            max_concurrent_chimera: Max parallel Chimera agent executions
            max_concurrent_cc_workers: Max parallel CC worker spawns
        """
        self._config = config or create_config_from_sources()
        self.poll_interval = poll_interval
        self.max_concurrent_chimera = max_concurrent_chimera
        self.max_concurrent_cc_workers = max_concurrent_cc_workers
        self.running = False
        self.logger = logger

        # Orchestration client
        self.client = OrchestrationClient()

        # RAG engine (loaded on startup)
        self.rag_engine = None  # Initialized in start()

        # Decision engine (routes to Chimera vs CC workers)
        self.decision_engine = None  # Initialized in start()

        # Chimera executor for lightweight fixes
        self.chimera_executor = None  # Initialized in start()

        # CC worker spawner for complex tasks
        self.cc_spawner = None  # Initialized in start()

        # Worker monitor
        self.monitor = None  # Initialized in start()

        # Metrics
        self.started_at: datetime | None = None
        self.tasks_processed = 0
        self.tasks_chimera = 0
        self.tasks_cc_worker = 0
        self.tasks_escalated = 0
        self.tasks_failed = 0

        # Signal handlers
        self._setup_signal_handlers()

    def _setup_signal_handlers(self) -> None:
        """Set up graceful shutdown on SIGINT/SIGTERM."""

        def handle_signal(signum: int, frame: Any) -> None:  # noqa: ARG001
            self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self.running = False

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

    async def start(self) -> None:
        """Start daemon processing loop.

        Runs continuously until stopped via signal (SIGINT/SIGTERM).
        """
        # Initialize components
        await self._initialize_components()

        self.running = True
        self.started_at = datetime.now()
        self.logger.info("=" * 80)
        self.logger.info("QA Agent Daemon Started - Hybrid Chimera + CC Worker Architecture")
        self.logger.info("=" * 80)
        self.logger.info(f"Polling interval: {self.poll_interval}s")
        self.logger.info(f"Max concurrent Chimera agents: {self.max_concurrent_chimera}")
        self.logger.info(f"Max concurrent CC workers: {self.max_concurrent_cc_workers}")
        self.logger.info(f"RAG patterns loaded: {self._get_rag_pattern_count()}")
        self.logger.info("=" * 80)

        try:
            while self.running:
                await self._process_next_task()
                await asyncio.sleep(self.poll_interval)

        except Exception as e:
            self.logger.error(f"Daemon crashed: {e}", exc_info=True)
            raise

        finally:
            self.logger.info("QA Agent daemon stopping...")
            await self._shutdown_components()
            self.logger.info("QA Agent daemon stopped")
            self._log_final_metrics()

    async def _initialize_components(self) -> None:
        """Initialize all daemon components."""
        from .decision_engine import WorkerDecisionEngine
        from .monitoring import QAWorkerMonitor
        from .rag_priming import RAGEngine

        # Initialize RAG engine with pattern priming
        self.logger.info("Initializing RAG engine and priming patterns...")
        self.rag_engine = RAGEngine(config=self._config)
        await self.rag_engine.initialize()
        self.logger.info(f"RAG engine initialized with {self._get_rag_pattern_count()} patterns")

        # Initialize decision engine
        self.logger.info("Initializing decision engine...")
        self.decision_engine = WorkerDecisionEngine(rag_engine=self.rag_engine)

        # Initialize Chimera executor (will be implemented in Phase 2)
        self.logger.info("Initializing Chimera executor...")
        # For now, create placeholder - will use QA agents registry in Phase 2
        self.chimera_executor = None  # ChimeraExecutor(agents_registry=create_qa_agents_registry())

        # Initialize CC worker spawner (will be implemented in Phase 3)
        self.logger.info("Initializing CC worker spawner...")
        self.cc_spawner = None  # CCWorkerSpawner(config=self._config, db=self.db)

        # Initialize monitor (will be implemented in Phase 5)
        self.logger.info("Initializing worker monitor...")
        self.monitor = QAWorkerMonitor(
            chimera_executor=self.chimera_executor,
            cc_spawner=self.cc_spawner,
            client=self.client,
        )

        self.logger.info("All components initialized successfully")

    async def _shutdown_components(self) -> None:
        """Gracefully shutdown all components."""
        if self.chimera_executor:
            self.logger.info("Stopping Chimera executor...")
            # await self.chimera_executor.stop()

        if self.cc_spawner:
            self.logger.info("Stopping CC workers...")
            # await self.cc_spawner.shutdown_all()

        if self.monitor:
            self.logger.info("Stopping worker monitor...")
            await self.monitor.stop()

    async def _process_next_task(self) -> None:
        """Poll queue and process next QA task.

        Decision flow:
        1. Get next qa_workflow task from queue
        2. Parse violations from task payload
        3. Score complexity and check RAG confidence
        4. Route to Chimera agent OR CC worker based on decision
        5. Update task status and publish events
        """
        # Get next QA task from orchestrator queue
        qa_task = await self._get_next_qa_task()

        if not qa_task:
            return  # Queue empty, continue polling

        self.logger.info(f"Processing QA task: {qa_task['id']} ({qa_task.get('title', 'Untitled')})")
        self.tasks_processed += 1

        try:
            # Parse violations from task payload
            violations = self._parse_violations(qa_task)

            if not violations:
                self.logger.warning(f"No violations found in task {qa_task['id']}, marking complete")
                await self._mark_task_complete(qa_task)
                return

            # Decide worker type using decision engine
            decision = await self.decision_engine.decide(violations)

            self.logger.info(
                f"Decision: {decision.worker_type} "
                f"(complexity: {decision.complexity_score:.2f}, "
                f"confidence: {decision.rag_confidence:.2f})"
            )

            # Route to appropriate worker
            if decision.worker_type == "chimera-agent":
                await self._route_to_chimera(qa_task, violations, decision)
                self.tasks_chimera += 1

            elif decision.worker_type == "cc-worker-headless":
                await self._route_to_cc_worker(qa_task, violations, decision, interactive=False)
                self.tasks_cc_worker += 1

            elif decision.worker_type == "cc-worker-with-hitl":
                await self._route_to_cc_worker(qa_task, violations, decision, interactive=True)
                self.tasks_escalated += 1

            else:
                self.logger.error(f"Unknown worker type: {decision.worker_type}")
                await self._mark_task_failed(qa_task, f"Unknown worker type: {decision.worker_type}")
                self.tasks_failed += 1

        except Exception as e:
            self.logger.error(f"Task processing failed: {qa_task['id']} - {e}", exc_info=True)
            await self._mark_task_failed(qa_task, str(e))
            self.tasks_failed += 1

    async def _get_next_qa_task(self) -> dict[str, Any] | None:
        """Get next QA workflow task from orchestrator queue.

        Returns:
            Next queued QA task, or None if queue is empty
        """
        try:
            # Query orchestrator for queued qa_workflow tasks
            tasks = self.client.get_pending_tasks(task_type="qa_workflow")

            if not tasks:
                return None

            task = tasks[0]

            # Mark as IN_PROGRESS to prevent race conditions
            self.client.update_task_status(task["id"], "in_progress")

            return task

        except Exception as e:
            self.logger.error(f"Failed to fetch next QA task: {e}", exc_info=True)
            return None

    def _parse_violations(self, task: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse violations from task payload.

        Args:
            task: QA workflow task with violations in payload

        Returns:
            List of violation dictionaries with metadata
        """
        payload = task.get("payload") or {}
        violations = payload.get("violations", [])

        if not violations:
            self.logger.warning(f"Task {task['id']} has no violations in payload")

        return violations

    async def _route_to_chimera(
        self,
        task: dict[str, Any],
        violations: list[dict[str, Any]],
        decision: Any,
    ) -> None:
        """Route task to Chimera agent for fast auto-fix.

        Args:
            task: QA workflow task
            violations: Parsed violations
            decision: Worker decision with RAG context
        """
        self.logger.info(f"Routing to Chimera agent: {len(violations)} violations")

        if not self.chimera_executor:
            self.logger.warning("Chimera executor not initialized (Phase 2 pending)")
            await self._mark_task_failed(task, "Chimera executor not available")
            return

        # TODO: Phase 2 - Execute Chimera workflow with QA agents
        # result = await self.chimera_executor.execute_workflow(
        #     QAWorkflow(violations=violations, rag_context=decision.rag_context)
        # )

        # For now, just mark as complete (Phase 2 will implement actual execution)
        self.logger.info(f"Chimera execution complete (Phase 2 pending): {task['id']}")
        await self._mark_task_complete(task)

    async def _route_to_cc_worker(
        self,
        task: dict[str, Any],
        violations: list[dict[str, Any]],
        decision: Any,
        interactive: bool,
    ) -> None:
        """Route task to CC worker (headless or interactive).

        Args:
            task: QA workflow task
            violations: Parsed violations
            decision: Worker decision with RAG context
            interactive: If True, spawn interactive terminal for HITL
        """
        mode = "interactive (HITL)" if interactive else "headless"
        self.logger.info(f"Routing to CC worker ({mode}): {len(violations)} violations")

        if not self.cc_spawner:
            self.logger.warning("CC worker spawner not initialized (Phase 3 pending)")
            await self._mark_task_failed(task, "CC worker spawner not available")
            return

        # TODO: Phase 3 - Spawn CC worker with RAG context injection
        # if interactive:
        #     await self.cc_spawner.spawn_interactive(
        #         task=task, rag_context=decision.rag_context, escalation_reason=decision.reason
        #     )
        # else:
        #     await self.cc_spawner.spawn_headless(task=task, rag_context=decision.rag_context)

        # For now, just mark as in-progress (Phase 3 will implement actual spawning)
        self.logger.info(f"CC worker spawned (Phase 3 pending): {task['id']}")
        # Task will be completed by the spawned CC worker

    async def _mark_task_complete(self, task: dict[str, Any]) -> None:
        """Mark task as completed in orchestrator database."""
        self.client.update_task_status(task["id"], "completed")
        self.logger.info(f"Task completed: {task['id']}")

    async def _mark_task_failed(self, task: dict[str, Any], error: str) -> None:
        """Mark task as failed in orchestrator database."""
        self.client.update_task_status(task["id"], "failed")
        self.logger.error(f"Task failed: {task['id']} - {error}")

    def _get_rag_pattern_count(self) -> int:
        """Get number of loaded RAG patterns."""
        if not self.rag_engine:
            return 0
        return self.rag_engine.pattern_count

    def _log_final_metrics(self) -> None:
        """Log final metrics on shutdown."""
        uptime = (datetime.now() - self.started_at).total_seconds() if self.started_at else 0

        self.logger.info("=" * 80)
        self.logger.info("QA AGENT DAEMON METRICS")
        self.logger.info("=" * 80)
        self.logger.info(f"Uptime: {uptime:.0f}s")
        self.logger.info(f"Tasks Processed: {self.tasks_processed}")
        self.logger.info(f"  - Chimera Agents: {self.tasks_chimera}")
        self.logger.info(f"  - CC Workers: {self.tasks_cc_worker}")
        self.logger.info(f"  - Escalated (HITL): {self.tasks_escalated}")
        self.logger.info(f"  - Failed: {self.tasks_failed}")

        if self.tasks_processed > 0:
            chimera_rate = (self.tasks_chimera / self.tasks_processed) * 100
            cc_rate = (self.tasks_cc_worker / self.tasks_processed) * 100
            escalation_rate = (self.tasks_escalated / self.tasks_processed) * 100
            failure_rate = (self.tasks_failed / self.tasks_processed) * 100

            self.logger.info(f"Chimera Rate: {chimera_rate:.1f}%")
            self.logger.info(f"CC Worker Rate: {cc_rate:.1f}%")
            self.logger.info(f"Escalation Rate: {escalation_rate:.1f}%")
            self.logger.info(f"Failure Rate: {failure_rate:.1f}%")

        self.logger.info("=" * 80)


__all__ = ["QAAgentDaemon"]
