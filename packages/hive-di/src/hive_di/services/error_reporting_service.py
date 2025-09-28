"""
Error Reporting Service Implementation

Injectable error reporting service that replaces global error reporter singletons.
Provides comprehensive error tracking with database persistence and event integration.
"""

import json
import uuid
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum

from ..interfaces import (
    IErrorReportingService,
    IDatabaseConnectionService,
    IEventBusService,
    IConfigurationService,
    IDisposable
)


class ErrorSeverity(Enum):
    """Error severity levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ErrorContext:
    """Error context information"""
    component: Optional[str] = None
    operation: Optional[str] = None
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    additional_data: Optional[Dict[str, Any]] = None


@dataclass
class ErrorReport:
    """Error report data structure"""
    error_id: str
    timestamp: datetime
    severity: ErrorSeverity
    error_type: str
    error_message: str
    stack_trace: Optional[str]
    context: ErrorContext
    resolved: bool
    resolution_note: Optional[str]
    resolution_timestamp: Optional[datetime]


class ErrorReportingService(IErrorReportingService, IDisposable):
    """
    Injectable error reporting service

    Replaces global error reporter patterns with a proper service that can be
    configured and injected independently.
    """

    def __init__(self,
                 configuration_service: IConfigurationService,
                 database_service: IDatabaseConnectionService,
                 event_bus_service: IEventBusService,
                 config: Optional[Dict[str, Any]] = None):
        """
        Initialize error reporting service

        Args:
            configuration_service: Configuration service for getting error reporting settings
            database_service: Database service for error persistence
            event_bus_service: Event bus service for error event publishing
            config: Optional override configuration
        """
        self._config_service = configuration_service
        self._db_service = database_service
        self._event_bus = event_bus_service
        self._override_config = config or {}

        # Get error reporting configuration
        error_config = self._config_service.get_error_reporting_config()
        self._config = {**error_config, **self._override_config}

        # Error reporting settings
        self.max_errors_in_memory = self._config.get('max_errors_in_memory', 500)
        self.error_retention_days = self._config.get('error_retention_days', 90)
        self.enable_email_alerts = self._config.get('enable_email_alerts', False)
        self.alert_email = self._config.get('alert_email')

        # Initialize database tables
        self._ensure_error_tables()

    def _ensure_error_tables(self) -> None:
        """Ensure error storage tables exist"""
        with self._db_service.get_pooled_connection() as conn:
            cursor = conn.cursor()

            # Error reports table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS error_reports (
                    error_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    error_type TEXT NOT NULL,
                    error_message TEXT NOT NULL,
                    stack_trace TEXT,
                    component TEXT,
                    operation TEXT,
                    user_id TEXT,
                    request_id TEXT,
                    additional_data TEXT,
                    resolved BOOLEAN DEFAULT FALSE,
                    resolution_note TEXT,
                    resolution_timestamp TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Indexes for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_errors_timestamp
                ON error_reports(timestamp)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_errors_severity
                ON error_reports(severity, timestamp)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_errors_component
                ON error_reports(component, timestamp)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_errors_resolved
                ON error_reports(resolved, timestamp)
            """)

            conn.commit()

    def _create_error_id(self) -> str:
        """Create a unique error ID"""
        return str(uuid.uuid4())

    def _serialize_context(self, context: Optional[Dict[str, Any]]) -> ErrorContext:
        """Convert context dictionary to ErrorContext object"""
        if not context:
            return ErrorContext()

        return ErrorContext(
            component=context.get('component'),
            operation=context.get('operation'),
            user_id=context.get('user_id'),
            request_id=context.get('request_id'),
            additional_data=context.get('additional_data')
        )

    def _publish_error_event(self, error_report: ErrorReport) -> None:
        """Publish error event to event bus"""
        try:
            self._event_bus.publish(
                event_type="error.reported",
                payload={
                    "error_id": error_report.error_id,
                    "severity": error_report.severity.value,
                    "error_type": error_report.error_type,
                    "error_message": error_report.error_message,
                    "component": error_report.context.component,
                    "timestamp": error_report.timestamp.isoformat()
                },
                source_agent="error_reporting_service",
                correlation_id=error_report.context.request_id
            )
        except Exception:
            # Don't let event publishing errors break error reporting
            pass

    # IErrorReportingService interface implementation

    def report_error(self, error: Exception, context: Optional[Dict[str, Any]] = None,
                    severity: str = "error", component: Optional[str] = None) -> str:
        """Report an error and return error ID"""
        error_id = self._create_error_id()
        timestamp = datetime.now(timezone.utc)

        # Parse severity
        try:
            severity_enum = ErrorSeverity(severity.lower())
        except ValueError:
            severity_enum = ErrorSeverity.ERROR

        # Create context
        error_context = self._serialize_context(context)
        if component and not error_context.component:
            error_context.component = component

        # Get stack trace
        stack_trace = None
        if error:
            stack_trace = ''.join(traceback.format_exception(
                type(error), error, error.__traceback__
            ))

        # Create error report
        error_report = ErrorReport(
            error_id=error_id,
            timestamp=timestamp,
            severity=severity_enum,
            error_type=type(error).__name__ if error else "Unknown",
            error_message=str(error) if error else "No error provided",
            stack_trace=stack_trace,
            context=error_context,
            resolved=False,
            resolution_note=None,
            resolution_timestamp=None
        )

        # Store in database
        with self._db_service.get_pooled_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO error_reports (
                    error_id, timestamp, severity, error_type, error_message,
                    stack_trace, component, operation, user_id, request_id,
                    additional_data, resolved, resolution_note, resolution_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                error_report.error_id,
                error_report.timestamp.isoformat(),
                error_report.severity.value,
                error_report.error_type,
                error_report.error_message,
                error_report.stack_trace,
                error_report.context.component,
                error_report.context.operation,
                error_report.context.user_id,
                error_report.context.request_id,
                json.dumps(error_report.context.additional_data) if error_report.context.additional_data else None,
                error_report.resolved,
                error_report.resolution_note,
                error_report.resolution_timestamp.isoformat() if error_report.resolution_timestamp else None
            ))
            conn.commit()

        # Publish error event
        self._publish_error_event(error_report)

        return error_id

    async def report_error_async(self, error: Exception, context: Optional[Dict[str, Any]] = None,
                                severity: str = "error", component: Optional[str] = None) -> str:
        """Report an error asynchronously"""
        error_id = self._create_error_id()
        timestamp = datetime.now(timezone.utc)

        # Parse severity
        try:
            severity_enum = ErrorSeverity(severity.lower())
        except ValueError:
            severity_enum = ErrorSeverity.ERROR

        # Create context
        error_context = self._serialize_context(context)
        if component and not error_context.component:
            error_context.component = component

        # Get stack trace
        stack_trace = None
        if error:
            stack_trace = ''.join(traceback.format_exception(
                type(error), error, error.__traceback__
            ))

        # Create error report
        error_report = ErrorReport(
            error_id=error_id,
            timestamp=timestamp,
            severity=severity_enum,
            error_type=type(error).__name__ if error else "Unknown",
            error_message=str(error) if error else "No error provided",
            stack_trace=stack_trace,
            context=error_context,
            resolved=False,
            resolution_note=None,
            resolution_timestamp=None
        )

        # Store in database (async)
        async with self._db_service.get_async_pooled_connection() as conn:
            await conn.execute("""
                INSERT INTO error_reports (
                    error_id, timestamp, severity, error_type, error_message,
                    stack_trace, component, operation, user_id, request_id,
                    additional_data, resolved, resolution_note, resolution_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                error_report.error_id,
                error_report.timestamp.isoformat(),
                error_report.severity.value,
                error_report.error_type,
                error_report.error_message,
                error_report.stack_trace,
                error_report.context.component,
                error_report.context.operation,
                error_report.context.user_id,
                error_report.context.request_id,
                json.dumps(error_report.context.additional_data) if error_report.context.additional_data else None,
                error_report.resolved,
                error_report.resolution_note,
                error_report.resolution_timestamp.isoformat() if error_report.resolution_timestamp else None
            ))
            await conn.commit()

        # Publish error event
        self._publish_error_event(error_report)

        return error_id

    def get_error_summary(self, since: Optional[datetime] = None) -> Dict[str, Any]:
        """Get error summary statistics"""
        with self._db_service.get_pooled_connection() as conn:
            cursor = conn.cursor()

            # Build query conditions
            where_clause = "WHERE 1=1"
            params = []
            if since:
                where_clause += " AND timestamp >= ?"
                params.append(since.isoformat())

            # Get total count
            cursor.execute(f"SELECT COUNT(*) FROM error_reports {where_clause}", params)
            total_errors = cursor.fetchone()[0]

            # Get count by severity
            cursor.execute(f"""
                SELECT severity, COUNT(*) FROM error_reports {where_clause}
                GROUP BY severity
            """, params)
            severity_counts = dict(cursor.fetchall())

            # Get count by component
            cursor.execute(f"""
                SELECT component, COUNT(*) FROM error_reports {where_clause}
                GROUP BY component
                ORDER BY COUNT(*) DESC
                LIMIT 10
            """, params)
            component_counts = dict(cursor.fetchall())

            # Get resolved vs unresolved
            cursor.execute(f"""
                SELECT resolved, COUNT(*) FROM error_reports {where_clause}
                GROUP BY resolved
            """, params)
            resolution_counts = dict(cursor.fetchall())

        return {
            'total_errors': total_errors,
            'by_severity': severity_counts,
            'by_component': component_counts,
            'resolved': resolution_counts.get(True, 0),
            'unresolved': resolution_counts.get(False, 0),
            'summary_since': since.isoformat() if since else None
        }

    def get_error_details(self, error_id: str) -> Optional[Dict[str, Any]]:
        """Get details for a specific error"""
        with self._db_service.get_pooled_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM error_reports WHERE error_id = ?
            """, (error_id,))
            row = cursor.fetchone()

        if not row:
            return None

        error_dict = dict(row)
        if error_dict['additional_data']:
            error_dict['additional_data'] = json.loads(error_dict['additional_data'])

        return error_dict

    def mark_error_resolved(self, error_id: str, resolution_note: Optional[str] = None) -> bool:
        """Mark an error as resolved"""
        resolution_timestamp = datetime.now(timezone.utc)

        with self._db_service.get_pooled_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE error_reports
                SET resolved = TRUE, resolution_note = ?, resolution_timestamp = ?
                WHERE error_id = ?
            """, (resolution_note, resolution_timestamp.isoformat(), error_id))
            updated = cursor.rowcount > 0
            conn.commit()

        if updated:
            # Publish resolution event
            try:
                self._event_bus.publish(
                    event_type="error.resolved",
                    payload={
                        "error_id": error_id,
                        "resolution_note": resolution_note,
                        "resolution_timestamp": resolution_timestamp.isoformat()
                    },
                    source_agent="error_reporting_service"
                )
            except Exception:
                pass

        return updated

    # IDisposable interface implementation

    def dispose(self) -> None:
        """Clean up error reporting service resources"""
        # No specific cleanup needed for error reporting service
        pass

    # Additional utility methods

    def get_recent_errors(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent errors"""
        with self._db_service.get_pooled_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM error_reports
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()

        errors = []
        for row in rows:
            error_dict = dict(row)
            if error_dict['additional_data']:
                error_dict['additional_data'] = json.loads(error_dict['additional_data'])
            errors.append(error_dict)

        return errors

    def cleanup_old_errors(self) -> int:
        """Clean up errors older than retention period"""
        cutoff_date = datetime.now(timezone.utc).replace(
            day=datetime.now(timezone.utc).day - self.error_retention_days
        )

        with self._db_service.get_pooled_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM error_reports WHERE timestamp < ?
            """, (cutoff_date.isoformat(),))
            deleted_count = cursor.rowcount
            conn.commit()

        return deleted_count