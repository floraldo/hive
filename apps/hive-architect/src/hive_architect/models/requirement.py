"""Requirement parsing models.

Structured representation of natural language requirements
after NLP extraction.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ServiceType(str, Enum):
    """Type of service to generate"""

    API = "api"  # REST API service
    WORKER = "worker"  # Event-driven worker
    BATCH = "batch"  # Batch processing job
    UNKNOWN = "unknown"  # Cannot determine type


class ParsedRequirement(BaseModel):
    """Structured representation of a natural language requirement.

    Example input: "Create a 'feedback-service' API that stores user feedback"
    Parsed output:
        - service_name: feedback-service
        - service_type: API
        - features: ["store user feedback"]
        - enable_database: True
    """

    service_name: str = Field(..., description="Extracted service name")
    service_type: ServiceType = Field(
        ...,
        description="Type of service to generate",
    )
    features: list[str] = Field(
        default_factory=list,
        description="Extracted feature requirements",
    )
    enable_database: bool = Field(
        default=False,
        description="Whether database integration is needed",
    )
    enable_caching: bool = Field(
        default=False,
        description="Whether caching is needed",
    )
    enable_async: bool = Field(
        default=False,
        description="Whether async operations are needed",
    )
    technical_constraints: list[str] = Field(
        default_factory=list,
        description="Extracted technical requirements",
    )
    business_rules: list[str] = Field(
        default_factory=list,
        description="Extracted business logic rules",
    )
    confidence_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence in the parsing (0-1)",
    )
