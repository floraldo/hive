"""Knowledge Fragment Parser

Extracts structured knowledge fragments from completed tasks:
- Summary: Executive summary (2-3 sentences)
- Errors: Each error with context + resolution
- Decisions: Key architectural/design choices
- Artifacts: Code files, reports, diagrams created
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from hive_logging import get_logger

logger = get_logger(__name__)


@dataclass
class KnowledgeFragment:
    """A single knowledge fragment extracted from a task."""

    fragment_type: str  # 'summary' | 'error' | 'decision' | 'artifact'
    content: str
    task_id: str
    task_type: str
    status: str
    timestamp: str
    metadata: dict[str, Any]


class FragmentParser:
    """Parse completed tasks into structured knowledge fragments.

    Implements Decision 2-B: Structured Knowledge Fragments architecture.
    Creates multiple vectors per task for granular, searchable knowledge.
    """

    def __init__(self):
        """Initialize the fragment parser."""

    def parse_task(self, task: dict[str, Any]) -> list[KnowledgeFragment]:
        """Parse a completed task into knowledge fragments.

        Args:
            task: Task dictionary from orchestration DB

        Returns:
            List of knowledge fragments ready for embedding

        Example:
            >>> task = {'id': 'abc123', 'title': 'Deploy v2.1', ...}
            >>> fragments = parser.parse_task(task)
            >>> len(fragments)  # summary + N errors + M decisions
            5

        """
        fragments = []

        # Extract base metadata
        task_id = task.get("id", "unknown")
        task_type = task.get("task_type", "general")
        status = task.get("status", "completed")
        timestamp = task.get("updated_at", task.get("created_at", ""))

        # PROJECT CHIMERA Phase 3: Check if this task resolved an alert
        resolution_metadata = self._extract_resolution_metadata(task)

        # 1. SUMMARY FRAGMENT
        summary = self._generate_summary(task)
        if summary:
            fragments.append(
                KnowledgeFragment(
                    fragment_type="summary",
                    content=summary,
                    task_id=task_id,
                    task_type=task_type,
                    status=status,
                    timestamp=timestamp,
                    metadata={
                        "title": task.get("title", ""),
                        "priority": task.get("priority", 1),
                        "assigned_worker": task.get("assigned_worker", ""),
                        **resolution_metadata,  # Include resolution info if present
                    },
                ),
            )

        # 2. ERROR FRAGMENTS
        error_fragments = self._extract_errors(task, task_id, task_type, status, timestamp)
        fragments.extend(error_fragments)

        # 3. DECISION FRAGMENTS
        decision_fragments = self._extract_decisions(task, task_id, task_type, status, timestamp)
        fragments.extend(decision_fragments)

        # 4. ARTIFACT FRAGMENTS
        artifact_fragments = self._extract_artifacts(task, task_id, task_type, status, timestamp)
        fragments.extend(artifact_fragments)

        logger.info(
            f"Parsed task {task_id[:8]} into {len(fragments)} fragments: "
            f"{sum(1 for f in fragments if f.fragment_type == 'summary')} summaries, "
            f"{sum(1 for f in fragments if f.fragment_type == 'error')} errors, "
            f"{sum(1 for f in fragments if f.fragment_type == 'decision')} decisions, "
            f"{sum(1 for f in fragments if f.fragment_type == 'artifact')} artifacts",
        )

        return fragments

    def _generate_summary(self, task: dict[str, Any]) -> str:
        """Generate executive summary from task data.

        For Phase 1, uses rule-based extraction. Phase 2 will use AI.
        """
        title = task.get("title", "Untitled task")
        description = task.get("description", "")
        status = task.get("status", "completed")

        # Get run results if available
        result_snippet = ""
        payload = task.get("payload")
        if payload and isinstance(payload, str):
            try:
                payload_data = json.loads(payload)
                if "result" in payload_data:
                    result_snippet = f" Result: {str(payload_data['result'])[:100]}"
            except (json.JSONDecodeError, TypeError):
                pass

        # Construct concise summary
        summary = f"{title} ({status}). {description[:150]}{result_snippet}"

        return summary.strip()

    def _extract_errors(
        self,
        task: dict[str, Any],
        task_id: str,
        task_type: str,
        status: str,
        timestamp: str,
    ) -> list[KnowledgeFragment]:
        """Extract error fragments from task execution.

        Looks for errors in:
        - Task failure_reason field
        - Run error_message fields
        - Payload error data
        """
        fragments = []

        # Check task-level failure reason
        if task.get("failure_reason"):
            fragments.append(
                KnowledgeFragment(
                    fragment_type="error",
                    content=f"Task failure: {task['failure_reason']}",
                    task_id=task_id,
                    task_type=task_type,
                    status=status,
                    timestamp=timestamp,
                    metadata={
                        "error_source": "task",
                        "title": task.get("title", ""),
                    },
                ),
            )

        # Extract from payload if present
        payload = task.get("payload")
        if payload and isinstance(payload, str):
            try:
                payload_data = json.loads(payload)
                if "errors" in payload_data and isinstance(payload_data["errors"], list):
                    for idx, error in enumerate(payload_data["errors"]):
                        error_text = error if isinstance(error, str) else str(error)
                        fragments.append(
                            KnowledgeFragment(
                                fragment_type="error",
                                content=f"Error #{idx + 1}: {error_text}",
                                task_id=task_id,
                                task_type=task_type,
                                status=status,
                                timestamp=timestamp,
                                metadata={
                                    "error_source": "payload",
                                    "error_index": idx,
                                },
                            ),
                        )
            except (json.JSONDecodeError, TypeError):
                pass

        return fragments

    def _extract_decisions(
        self,
        task: dict[str, Any],
        task_id: str,
        task_type: str,
        status: str,
        timestamp: str,
    ) -> list[KnowledgeFragment]:
        """Extract decision fragments from task metadata.

        Decisions are key architectural or design choices made during task execution.
        """
        fragments = []

        # Look for decisions in payload
        payload = task.get("payload")
        if payload and isinstance(payload, str):
            try:
                payload_data = json.loads(payload)
                if "decisions" in payload_data and isinstance(payload_data["decisions"], list):
                    for idx, decision in enumerate(payload_data["decisions"]):
                        decision_text = decision if isinstance(decision, str) else str(decision)
                        fragments.append(
                            KnowledgeFragment(
                                fragment_type="decision",
                                content=decision_text,
                                task_id=task_id,
                                task_type=task_type,
                                status=status,
                                timestamp=timestamp,
                                metadata={
                                    "decision_index": idx,
                                    "title": task.get("title", ""),
                                },
                            ),
                        )
            except (json.JSONDecodeError, TypeError):
                pass

        return fragments

    def _extract_artifacts(
        self,
        task: dict[str, Any],
        task_id: str,
        task_type: str,
        status: str,
        timestamp: str,
    ) -> list[KnowledgeFragment]:
        """Extract artifact fragments (files, reports, outputs created).

        Artifacts link tasks to concrete deliverables.
        """
        fragments = []

        # Check generated_artifacts field (if already populated)
        artifacts_json = task.get("generated_artifacts")
        if artifacts_json and isinstance(artifacts_json, str):
            try:
                artifacts_list = json.loads(artifacts_json)
                if isinstance(artifacts_list, list):
                    for artifact_path in artifacts_list:
                        fragments.append(
                            KnowledgeFragment(
                                fragment_type="artifact",
                                content=f"Generated artifact: {artifact_path}",
                                task_id=task_id,
                                task_type=task_type,
                                status=status,
                                timestamp=timestamp,
                                metadata={
                                    "artifact_path": artifact_path,
                                    "title": task.get("title", ""),
                                },
                            ),
                        )
            except (json.JSONDecodeError, TypeError):
                pass

        # Also check payload for artifacts
        payload = task.get("payload")
        if payload and isinstance(payload, str):
            try:
                payload_data = json.loads(payload)
                if "artifacts" in payload_data and isinstance(payload_data["artifacts"], list):
                    for artifact in payload_data["artifacts"]:
                        artifact_str = artifact if isinstance(artifact, str) else str(artifact)
                        fragments.append(
                            KnowledgeFragment(
                                fragment_type="artifact",
                                content=f"Created: {artifact_str}",
                                task_id=task_id,
                                task_type=task_type,
                                status=status,
                                timestamp=timestamp,
                                metadata={"artifact_source": "payload"},
                            ),
                        )
            except (json.JSONDecodeError, TypeError):
                pass

        return fragments

    def _extract_resolution_metadata(self, task: dict[str, Any]) -> dict[str, Any]:
        """Extract resolution action metadata if task resolved an alert.

        PROJECT CHIMERA Phase 3: Track "what worked before" for automated recovery.

        Args:
            task: Task dictionary

        Returns:
            Dictionary with resolution metadata

        """
        metadata = {}

        # Check task metadata for resolution markers
        task_metadata = task.get("metadata", {})

        if isinstance(task_metadata, str):
            try:
                import json
                task_metadata = json.loads(task_metadata)
            except (json.JSONDecodeError, TypeError):
                task_metadata = {}

        # Check if task was a resolution
        if "resolution_for_alert" in task_metadata:
            metadata["is_resolution"] = True
            metadata["resolved_alert_id"] = task_metadata["resolution_for_alert"]
            metadata["resolution_action"] = task_metadata.get("action_taken", "manual")
            metadata["resolution_success"] = task.get("status") == "completed"
        elif "automated_recovery" in task_metadata:
            metadata["is_resolution"] = True
            metadata["resolution_action"] = task_metadata.get("playbook_id", "unknown")
            metadata["resolution_success"] = task.get("status") == "completed"

        return metadata


__all__ = ["FragmentParser", "KnowledgeFragment"]
