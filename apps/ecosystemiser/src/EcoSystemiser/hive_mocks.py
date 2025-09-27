"""
Temporary mock implementations for Hive packages during development.

This module provides simplified implementations of Hive base classes
to enable development and testing when the full Hive packages are not available.
"""

from typing import Dict, Any, Optional, List, Callable, Awaitable
from datetime import datetime
from dataclasses import dataclass, field
import uuid
import asyncio
import json


# Mock HiveError for development
class HiveError(Exception):
    """Mock implementation of HiveError for development."""

    def __init__(self,
                 message: str,
                 component: str = "unknown",
                 operation: str = "unknown",
                 details: Optional[Dict[str, Any]] = None,
                 recovery_suggestions: Optional[List[str]] = None):
        super().__init__(message)
        self.message = message
        self.component = component
        self.operation = operation
        self.details = details or {}
        self.recovery_suggestions = recovery_suggestions or []

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary."""
        return {
            'component': self.component,
            'operation': self.operation,
            'message': self.message,
            'details': self.details,
            'recovery_suggestions': self.recovery_suggestions
        }


class HiveValidationError(HiveError):
    """Mock validation error."""
    pass


class HiveAPIError(HiveError):
    """Mock API error."""
    pass


class HiveTimeoutError(HiveError):
    """Mock timeout error."""
    pass


# Mock Event and EventBus for development
@dataclass
class Event:
    """Mock implementation of Event for development."""
    event_type: str
    source_agent: str = ""
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    payload: Dict[str, Any] = field(default_factory=dict)


class EventBus:
    """Mock implementation of EventBus for development."""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._subscription_counter = 0

    async def subscribe(self, event_type: str, handler: Callable[[Event], Awaitable[None]]) -> str:
        """Subscribe to events of a specific type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []

        self._subscribers[event_type].append(handler)
        subscription_id = f"sub_{self._subscription_counter}"
        self._subscription_counter += 1
        return subscription_id

    async def unsubscribe(self, subscription_id: str) -> None:
        """Unsubscribe from events."""
        # Simple mock implementation
        pass

    async def publish(self, event: Event) -> None:
        """Publish an event to all subscribers."""
        if event.event_type in self._subscribers:
            for handler in self._subscribers[event.event_type]:
                try:
                    await handler(event)
                except Exception as e:
                    print(f"Error in event handler: {e}")


def create_workflow_event(**kwargs) -> Event:
    """Create a workflow event."""
    return Event(**kwargs)


# Mock SQLite utilities for development
import sqlite3
from pathlib import Path
from contextlib import contextmanager


def get_sqlite_connection(db_path: str, **kwargs) -> sqlite3.Connection:
    """Mock SQLite connection."""
    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)

    defaults = {
        'timeout': 30.0,
        'check_same_thread': False,
        'isolation_level': None
    }
    defaults.update(kwargs)

    conn = sqlite3.connect(db_path, **defaults)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


@contextmanager
def sqlite_transaction(db_path: str, **kwargs):
    """Mock SQLite transaction context manager."""
    conn = None
    try:
        conn = get_sqlite_connection(db_path, **kwargs)
        conn.execute('BEGIN')
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def create_table_if_not_exists(conn: sqlite3.Connection, table_name: str, schema: str) -> None:
    """Mock table creation utility."""
    sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({schema})"
    conn.execute(sql)


def get_sqlite_info(db_path: str) -> Dict[str, Any]:
    """Mock SQLite info utility."""
    db_file = Path(db_path)
    return {
        'db_path': str(db_path),
        'file_size_bytes': db_file.stat().st_size if db_file.exists() else 0,
        'table_count': 0,
        'sqlite_version': '3.0.0',
        'exists': db_file.exists()
    }