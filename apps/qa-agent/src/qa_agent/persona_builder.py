"""Persona Builder - Build Worker Personas with RAG Context.

Constructs worker personas for CC terminals, injecting RAG context and
task metadata for intelligent autonomous execution.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from hive_logging import get_logger

logger = get_logger(__name__)


def build_worker_persona(
    task: dict[str, Any],
    rag_context: list[dict[str, Any]],
    mode: str,
    escalation_reason: str | None = None,
) -> dict[str, Any]:
    """Build worker persona with RAG context and task metadata.

    Persona structure:
    - worker_id: Unique worker identifier
    - mode: 'headless' or 'interactive'
    - task: Task metadata (id, description, payload)
    - rag_context: Retrieved fix patterns
    - violations: Parsed violations from task
    - timestamp: Persona creation timestamp
    - escalation_reason: Why escalated (if interactive mode)

    Args:
        task: Task dictionary from hive-orchestrator
        rag_context: Retrieved RAG patterns
        mode: Worker mode ('headless' or 'interactive')
        escalation_reason: Escalation reason (for interactive mode)

    Returns:
        Worker persona dictionary

    Example:
        persona = build_worker_persona(
            task={"id": "task-123", "payload": {...}},
            rag_context=[{"fix_pattern": "..."}],
            mode="headless"
        )
    """
    logger.info(f"Building {mode} worker persona for task: {task.get('id')}")

    # Generate unique worker ID
    worker_id = f"qa-cc-{mode}-{uuid.uuid4().hex[:8]}"

    # Parse violations from task payload
    violations = _parse_violations(task)

    # Extract task metadata
    task_metadata = {
        "id": task.get("id", "unknown"),
        "title": task.get("title", "QA Task"),
        "description": task.get("description", ""),
        "qa_type": task.get("payload", {}).get("qa_type", "unknown"),
        "scope": task.get("payload", {}).get("scope", "."),
        "severity_level": task.get("payload", {}).get("severity_level", "ERROR"),
    }

    # Build persona
    persona = {
        "worker_id": worker_id,
        "mode": mode,
        "task": task_metadata,
        "rag_context": _format_rag_context(rag_context),
        "violations": violations,
        "timestamp": datetime.now().isoformat(),
        "created_at": datetime.now(),
    }

    # Add escalation context for interactive mode
    if mode == "interactive" and escalation_reason:
        persona["escalation_reason"] = escalation_reason
        persona["requires_human_review"] = True

    logger.info(
        f"Persona built: {worker_id} "
        f"({len(violations)} violations, {len(rag_context)} RAG patterns)"
    )

    return persona


def _parse_violations(task: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse violations from task payload.

    Args:
        task: Task dictionary

    Returns:
        List of violation dictionaries
    """
    payload = task.get("payload", {})
    violations = payload.get("violations", [])

    if not violations:
        logger.warning(f"No violations found in task {task.get('id')}")

    return violations


def _format_rag_context(rag_patterns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Format RAG patterns for persona context.

    Extracts essential information and formats for CC worker consumption.

    Args:
        rag_patterns: Raw RAG patterns from retrieval

    Returns:
        Formatted RAG context
    """
    formatted = []

    for pattern in rag_patterns:
        pattern_type = pattern.get("type", "unknown")
        similarity = pattern.get("similarity", 0.0)
        data = pattern.get("data", {})

        if pattern_type == "git_commit":
            formatted.append({
                "type": "git_commit",
                "similarity": similarity,
                "message": data.get("message", ""),
                "commit_sha": data.get("sha", "")[:8],
                "diff": data.get("diff", "")[:500],  # Truncate diff
                "files_changed": data.get("files_changed", []),
            })

        elif pattern_type == "code_chunk":
            formatted.append({
                "type": "code_chunk",
                "similarity": similarity,
                "file": data.get("file", ""),
                "content": data.get("content", "")[:300],  # Truncate content
                "language": data.get("language", "python"),
            })

        else:
            formatted.append({
                "type": "unknown",
                "similarity": similarity,
                "data": str(data)[:200],  # Truncate
            })

    return formatted


def build_rag_context_string(persona: dict[str, Any], max_length: int = 2000) -> str:
    """Build RAG context string for startup script injection.

    Formats RAG patterns as human-readable text for CC worker guidance.

    Args:
        persona: Worker persona
        max_length: Maximum character length

    Returns:
        Formatted RAG context string
    """
    rag_context = persona.get("rag_context", [])

    if not rag_context:
        return "No similar patterns found in RAG index."

    lines = [
        "# RAG Context: Similar Fix Patterns",
        f"# Retrieved: {len(rag_context)} patterns",
        "",
    ]

    chars_used = sum(len(line) for line in lines)

    for i, pattern in enumerate(rag_context):
        pattern_lines = _format_pattern_for_display(pattern, i + 1)
        pattern_text = "\n".join(pattern_lines)

        if chars_used + len(pattern_text) > max_length:
            lines.append(f"# ... {len(rag_context) - i} more patterns (truncated)")
            break

        lines.extend(pattern_lines)
        chars_used += len(pattern_text)

    return "\n".join(lines)


def _format_pattern_for_display(pattern: dict[str, Any], index: int) -> list[str]:
    """Format single RAG pattern for display.

    Args:
        pattern: RAG pattern
        index: Pattern index (1-based)

    Returns:
        List of formatted lines
    """
    pattern_type = pattern.get("type", "unknown")
    similarity = pattern.get("similarity", 0.0)

    lines = [
        "",
        f"## Pattern {index}: {pattern_type.upper()} (similarity: {similarity:.2f})",
    ]

    if pattern_type == "git_commit":
        lines.extend([
            f"# Commit: {pattern.get('commit_sha', 'unknown')}",
            f"# Message: {pattern.get('message', 'No message')}",
            f"# Files: {', '.join(pattern.get('files_changed', [])[:3])}",
            "# Diff (truncated):",
            *[f"#   {line}" for line in pattern.get("diff", "").split("\n")[:5]],
        ])

    elif pattern_type == "code_chunk":
        lines.extend([
            f"# File: {pattern.get('file', 'unknown')}",
            f"# Language: {pattern.get('language', 'unknown')}",
            "# Content (truncated):",
            *[f"#   {line}" for line in pattern.get("content", "").split("\n")[:5]],
        ])

    else:
        lines.append(f"# Data: {pattern.get('data', 'No data')}")

    return lines


def build_violation_summary(persona: dict[str, Any]) -> str:
    """Build violation summary for worker context.

    Args:
        persona: Worker persona

    Returns:
        Formatted violation summary
    """
    violations = persona.get("violations", [])

    if not violations:
        return "No violations to fix."

    # Group violations by type
    by_type: dict[str, list[dict[str, Any]]] = {}
    for violation in violations:
        vtype = violation.get("type", "unknown")
        by_type.setdefault(vtype, []).append(violation)

    lines = [
        f"# Violations Summary: {len(violations)} total",
        "",
    ]

    for vtype, vlist in sorted(by_type.items()):
        lines.append(f"## {vtype}: {len(vlist)} violations")

        # Show first 3 examples
        for v in vlist[:3]:
            file_path = v.get("file", "unknown")
            message = v.get("message", "No message")
            lines.append(f"  - {file_path}: {message}")

        if len(vlist) > 3:
            lines.append(f"  ... and {len(vlist) - 3} more")

        lines.append("")

    return "\n".join(lines)


__all__ = [
    "build_worker_persona",
    "build_rag_context_string",
    "build_violation_summary",
]
