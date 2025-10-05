"""Unified database schema for all agents and workflows.

This schema provides a common foundation that both legacy and new services can use.
During migration, we use dual-write to keep both schemas in sync.

Architecture:
    - UnifiedTask: Base task model (all task types inherit)
    - UnifiedReviewTask: Review-specific fields
    - UnifiedWorkflowTask: Workflow execution tracking
    - UnifiedDeploymentTask: Deployment tracking

Migration Strategy:
    1. Add these tables alongside existing ones (non-breaking)
    2. Use dual-write to populate both schemas
    3. Gradually migrate agents to use unified schema
    4. Drop legacy tables in Q3 2025
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class TaskStatus(str, Enum):
    """Unified task status across all agents."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    REVIEW_PENDING = "review_pending"
    REVIEW_APPROVED = "review_approved"
    REVIEW_REJECTED = "review_rejected"
    REWORK_NEEDED = "rework_needed"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(str, Enum):
    """Task types corresponding to agent capabilities."""

    REVIEW = "review"
    PLAN = "plan"
    CODE = "code"
    DEPLOY = "deploy"
    TEST = "test"
    WORKFLOW = "workflow"


class UnifiedTask(Base):
    """Base task model used by all agents.

    This is the core abstraction that allows different agents to work together.
    Each agent type may have additional specific fields in derived tables.
    """

    __tablename__ = "unified_tasks"

    # Core identification
    id = Column(String, primary_key=True)
    correlation_id = Column(String, index=True, nullable=False)  # Track across agents
    task_type = Column(String, nullable=False, index=True)  # Maps to TaskType enum
    status = Column(String, nullable=False, index=True)  # Maps to TaskStatus enum

    # Agent routing
    agent_type = Column(String, nullable=False)  # Which agent handles this
    priority = Column(Integer, default=5)  # 1=highest, 10=lowest

    # Task data (JSON for flexibility)
    input_data = Column(JSON, nullable=False)  # Task inputs
    output_data = Column(JSON, nullable=True)  # Task outputs
    task_metadata = Column(JSON, nullable=True)  # Additional context (renamed to avoid SQLAlchemy conflict)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Error handling
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)


class UnifiedReviewTask(Base):
    """Review-specific task fields.

    Used by both ai-reviewer and guardian-agent during migration.
    """

    __tablename__ = "unified_review_tasks"

    # Links to base task
    task_id = Column(String, primary_key=True)
    correlation_id = Column(String, index=True, nullable=False)

    # Review-specific fields
    code_path = Column(String, nullable=False)  # Path to code being reviewed
    pr_id = Column(String, nullable=True)  # Pull request ID if applicable

    # Review results
    review_score = Column(Integer, nullable=True)  # Overall score (0-100)
    review_result = Column(JSON, nullable=True)  # Detailed review data
    violations = Column(JSON, nullable=True)  # Golden rules violations
    suggestions = Column(JSON, nullable=True)  # Fix suggestions

    # Auto-fix tracking
    auto_fix_enabled = Column(Integer, default=1)  # Boolean (0=False, 1=True)
    auto_fix_attempts = Column(Integer, default=0)
    auto_fix_result = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)


class UnifiedWorkflowTask(Base):
    """Workflow execution tracking.

    Used by orchestrator to track multi-phase workflows (Chimera, Colossus, etc.)
    """

    __tablename__ = "unified_workflow_tasks"

    # Links to base task
    task_id = Column(String, primary_key=True)
    correlation_id = Column(String, index=True, nullable=False)

    # Workflow metadata
    workflow_type = Column(String, nullable=False)  # 'chimera', 'colossus', etc.
    current_phase = Column(String, nullable=False)
    total_phases = Column(Integer, nullable=False)

    # Phase tracking
    phases_completed = Column(Integer, default=0)
    phase_history = Column(JSON, nullable=True)  # List of completed phases

    # Workflow data
    workflow_config = Column(JSON, nullable=True)  # Workflow-specific config
    workflow_result = Column(JSON, nullable=True)  # Final workflow result

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    workflow_started_at = Column(DateTime, nullable=True)
    workflow_completed_at = Column(DateTime, nullable=True)


class UnifiedDeploymentTask(Base):
    """Deployment tracking.

    Used by ai-deployer for deployment operations.
    """

    __tablename__ = "unified_deployment_tasks"

    # Links to base task
    task_id = Column(String, primary_key=True)
    correlation_id = Column(String, index=True, nullable=False)

    # Deployment metadata
    service_name = Column(String, nullable=False)
    environment = Column(String, nullable=False)  # 'staging', 'production', etc.
    commit_sha = Column(String, nullable=True)

    # Deployment strategy
    strategy = Column(String, nullable=False)  # 'docker', 'kubernetes', 'ssh', etc.
    deployment_config = Column(JSON, nullable=True)

    # Deployment results
    deployment_url = Column(String, nullable=True)
    deployment_status = Column(String, nullable=True)
    deployment_logs = Column(Text, nullable=True)

    # Health monitoring
    health_check_url = Column(String, nullable=True)
    health_status = Column(String, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    deployed_at = Column(DateTime, nullable=True)
    validated_at = Column(DateTime, nullable=True)


# Export all models
__all__ = [
    "Base",
    "TaskStatus",
    "TaskType",
    "UnifiedTask",
    "UnifiedReviewTask",
    "UnifiedWorkflowTask",
    "UnifiedDeploymentTask",
]
