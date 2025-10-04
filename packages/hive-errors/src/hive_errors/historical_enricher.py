"""Historical Context Enricher

Bridges predictive alerts with RAG-based historical incident data.
Part of PROJECT CHIMERA - Fusion of Memory (Aegis) and Foresight (Vanguard).

Enriches predictive alerts with:
- Similar past incidents
- Successful resolution strategies
- Root cause patterns
- Time-to-resolution statistics
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from hive_logging import get_logger

from .predictive_alerts import DegradationAlert

logger = get_logger(__name__)


@dataclass
class HistoricalIncident:
    """Historical incident retrieved from RAG."""

    task_id: str
    summary: str
    resolution: str
    service_name: str
    metric_type: str
    timestamp: str
    similarity_score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EnrichedAlertContext:
    """Historical context for a predictive alert."""

    alert_id: str
    similar_incidents: list[HistoricalIncident]
    total_historical_occurrences: int
    average_resolution_time_minutes: float | None
    most_common_root_cause: str | None
    confidence: float  # 0.0-1.0
    retrieval_timestamp: datetime

    # PROJECT CHIMERA Phase 3: Resolution action tracking
    successful_resolution_action: str | None = None
    resolution_success_rate: float | None = None


class HistoricalContextEnricher:
    """Enrich predictive alerts with historical context from RAG.

    Integrates PROJECT AEGIS (Memory Nexus) with PROJECT VANGUARD (Predictive Alerts)
    to create context-aware, actionable alerts.
    """

    def __init__(self, context_service=None):
        """Initialize historical context enricher.

        Args:
            context_service: ContextRetrievalService from hive-ai/memory

        """
        self.context_service = context_service
        self._stats = {
            "total_enrichments": 0,
            "successful_enrichments": 0,
            "avg_similar_incidents_found": 0.0,
        }

    async def enrich_alert_with_history_async(
        self,
        alert: DegradationAlert,
        top_k: int = 3,
    ) -> EnrichedAlertContext:
        """Enrich alert with historical incident context from RAG.

        Args:
            alert: Predictive alert to enrich
            top_k: Number of similar historical incidents to retrieve

        Returns:
            Enriched context containing similar incidents and resolution patterns

        Example:
            >>> enricher = HistoricalContextEnricher(context_service)
            >>> context = await enricher.enrich_alert_with_history_async(alert)
            >>> print(f"Found {len(context.similar_incidents)} similar incidents")
            >>> print(f"Average resolution: {context.average_resolution_time_minutes} min")

        """
        start_time = datetime.utcnow()
        self._stats["total_enrichments"] += 1

        try:
            # Construct RAG query from alert metadata
            query = self._build_query_from_alert(alert)

            # Search historical knowledge base
            if not self.context_service:
                logger.warning("ContextService not available, returning empty context")
                return self._empty_context(alert.alert_id)

            # Query RAG for similar incidents
            search_results = await self.context_service.search_knowledge_async(
                query=query,
                top_k=top_k,
                filter_by_type=alert.service_name,  # Filter by service
            )

            # Parse RAG results into structured incidents
            incidents = self._parse_search_results(search_results, alert)

            # Compute statistics from historical data
            stats = self._compute_statistics(incidents)

            # Build enriched context
            enriched = EnrichedAlertContext(
                alert_id=alert.alert_id,
                similar_incidents=incidents,
                total_historical_occurrences=len(incidents),
                average_resolution_time_minutes=stats.get("avg_resolution_time"),
                most_common_root_cause=stats.get("common_root_cause"),
                confidence=self._calculate_confidence(incidents),
                retrieval_timestamp=start_time,
            )

            self._stats["successful_enrichments"] += 1
            self._update_avg_incidents(len(incidents))

            logger.info(
                f"Enriched alert {alert.alert_id[:8]} with {len(incidents)} "
                f"historical incidents (confidence: {enriched.confidence:.2%})",
            )

            return enriched

        except Exception as e:
            logger.error(f"Failed to enrich alert {alert.alert_id}: {e}", exc_info=True)
            return self._empty_context(alert.alert_id)

    def _build_query_from_alert(self, alert: DegradationAlert) -> str:
        """Build RAG search query from alert metadata.

        Combines service name, metric type, and alert context for optimal retrieval.
        """
        # Primary query components
        service = alert.service_name
        metric = alert.metric_type.value
        severity = alert.severity.value

        # Construct semantic query
        query = (
            f"{service} service experiencing {metric} degradation. "
            f"Similar to {severity} severity incidents. "
            f"Looking for root causes, resolutions, and recovery procedures."
        )

        return query

    def _parse_search_results(
        self,
        search_results: str,
        alert: DegradationAlert,
    ) -> list[HistoricalIncident]:
        """Parse RAG search results into structured HistoricalIncident objects.

        RAG returns compressed text with symbols - parse into structured data.
        """
        incidents = []

        if not search_results or search_results.startswith("No relevant"):
            return incidents

        # Parse compressed RAG results
        # Format: "📋 abc12345 → ✅ deployment (2024-10-03)\nSummary: ..."
        lines = search_results.split("\n\n")

        for block in lines:
            if not block.strip() or block.startswith("📅"):
                continue

            try:
                # Extract task ID (8 chars after symbol)
                if " " in block and "→" in block:
                    parts = block.split("→")
                    header = parts[0]
                    task_id_match = header.split()[-1] if len(header.split()) > 1 else "unknown"

                    # Extract summary (after status symbol)
                    content = parts[1] if len(parts) > 1 else block
                    summary = content.split("\n")[0] if "\n" in content else content
                    summary = summary.strip()

                    # Remove status symbols and timestamp
                    for symbol in ["✅", "❌", "(", ")"]:
                        summary = summary.replace(symbol, " ")

                    incident = HistoricalIncident(
                        task_id=task_id_match[:16],  # Truncate to reasonable length
                        summary=summary.strip()[:200],
                        resolution="",  # Parse from fragment metadata if available
                        service_name=alert.service_name,
                        metric_type=alert.metric_type.value,
                        timestamp="",  # Extract from block if present
                        similarity_score=0.8,  # RAG handles similarity ranking
                        metadata={},
                    )

                    incidents.append(incident)

            except Exception as e:
                logger.debug(f"Failed to parse incident block: {e}")
                continue

        return incidents

    def _compute_statistics(
        self,
        incidents: list[HistoricalIncident],
    ) -> dict[str, Any]:
        """Compute aggregate statistics from historical incidents.

        Returns:
            Dictionary with avg_resolution_time, common_root_cause, etc.

        """
        if not incidents:
            return {
                "avg_resolution_time": None,
                "common_root_cause": None,
            }

        # Placeholder for Phase 2 enhancement
        # Would analyze incident metadata to extract:
        # - Resolution times
        # - Root cause patterns
        # - Success rates

        return {
            "avg_resolution_time": 45.0,  # minutes (placeholder)
            "common_root_cause": "Connection pool exhaustion",  # placeholder
        }

    def _calculate_confidence(self, incidents: list[HistoricalIncident]) -> float:
        """Calculate confidence score for enriched context.

        Based on number of similar incidents and their similarity scores.
        """
        if not incidents:
            return 0.0

        # More incidents = higher confidence (plateaus at 5)
        incident_factor = min(len(incidents) / 5.0, 1.0)

        # Average similarity score
        avg_similarity = sum(i.similarity_score for i in incidents) / len(incidents)

        # Combined confidence (geometric mean)
        confidence = (incident_factor * avg_similarity) ** 0.5

        return min(confidence, 1.0)

    def _empty_context(self, alert_id: str) -> EnrichedAlertContext:
        """Return empty context when RAG retrieval fails."""
        return EnrichedAlertContext(
            alert_id=alert_id,
            similar_incidents=[],
            total_historical_occurrences=0,
            average_resolution_time_minutes=None,
            most_common_root_cause=None,
            confidence=0.0,
            retrieval_timestamp=datetime.utcnow(),
        )

    def _update_avg_incidents(self, count: int) -> None:
        """Update running average of incidents found per enrichment."""
        total = self._stats["total_enrichments"]
        current_avg = self._stats["avg_similar_incidents_found"]

        # Running average formula
        new_avg = ((current_avg * (total - 1)) + count) / total
        self._stats["avg_similar_incidents_found"] = new_avg

    def get_stats(self) -> dict[str, Any]:
        """Get enricher statistics."""
        return {
            **self._stats,
            "success_rate": (
                self._stats["successful_enrichments"] / self._stats["total_enrichments"]
                if self._stats["total_enrichments"] > 0
                else 0.0
            ),
        }


__all__ = ["EnrichedAlertContext", "HistoricalContextEnricher", "HistoricalIncident"]
