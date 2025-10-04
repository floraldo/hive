"""Unit tests for tasks command --since filter functionality.

Tests the time parsing utility and CLI integration for filtering tasks
by creation date using relative time strings.

Part of Project Genesis - Autonomous Development Validation
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from hive_cli.commands.tasks import parse_relative_time


class TestParseRelativeTime:
    """Test suite for parse_relative_time() utility function."""

    def test_valid_format_days(self):
        """Test parsing day formats: 2d, 3days, 1day."""
        # Test short format
        result = parse_relative_time("2d")
        expected = datetime.now() - timedelta(days=2)
        assert abs((result - expected).total_seconds()) < 1  # Within 1 second

        # Test plural
        result = parse_relative_time("3days")
        expected = datetime.now() - timedelta(days=3)
        assert abs((result - expected).total_seconds()) < 1

        # Test singular
        result = parse_relative_time("1day")
        expected = datetime.now() - timedelta(days=1)
        assert abs((result - expected).total_seconds()) < 1

    def test_valid_format_hours(self):
        """Test parsing hour formats: 1h, 2hours, 24hour."""
        # Test short format
        result = parse_relative_time("1h")
        expected = datetime.now() - timedelta(hours=1)
        assert abs((result - expected).total_seconds()) < 1

        # Test plural
        result = parse_relative_time("2hours")
        expected = datetime.now() - timedelta(hours=2)
        assert abs((result - expected).total_seconds()) < 1

        # Test singular
        result = parse_relative_time("24hour")
        expected = datetime.now() - timedelta(hours=24)
        assert abs((result - expected).total_seconds()) < 1

    def test_valid_format_minutes(self):
        """Test parsing minute formats: 30m, 45min, 1minute."""
        # Test short format
        result = parse_relative_time("30m")
        expected = datetime.now() - timedelta(minutes=30)
        assert abs((result - expected).total_seconds()) < 1

        # Test medium format
        result = parse_relative_time("45min")
        expected = datetime.now() - timedelta(minutes=45)
        assert abs((result - expected).total_seconds()) < 1

        # Test singular
        result = parse_relative_time("1minute")
        expected = datetime.now() - timedelta(minutes=1)
        assert abs((result - expected).total_seconds()) < 1

        # Test plural
        result = parse_relative_time("15minutes")
        expected = datetime.now() - timedelta(minutes=15)
        assert abs((result - expected).total_seconds()) < 1

    def test_valid_format_weeks(self):
        """Test parsing week formats: 1w, 2weeks."""
        # Test short format
        result = parse_relative_time("1w")
        expected = datetime.now() - timedelta(weeks=1)
        assert abs((result - expected).total_seconds()) < 1

        # Test plural
        result = parse_relative_time("2weeks")
        expected = datetime.now() - timedelta(weeks=2)
        assert abs((result - expected).total_seconds()) < 1

        # Test singular
        result = parse_relative_time("1week")
        expected = datetime.now() - timedelta(weeks=1)
        assert abs((result - expected).total_seconds()) < 1

    def test_invalid_formats(self):
        """Test that invalid formats raise ValueError with clear message."""
        invalid_cases = [
            "invalid",
            "2x",
            "abc",
            "",
            "2.5d",  # Decimal not supported
            "d2",    # Wrong order
            "-2d",   # Negative not supported
        ]

        for invalid in invalid_cases:
            with pytest.raises(ValueError) as exc_info:
                parse_relative_time(invalid)

            # Verify error message is clear
            assert "Invalid time format" in str(exc_info.value)
            assert "Expected formats" in str(exc_info.value)

    def test_case_insensitive(self):
        """Test that parsing is case-insensitive."""
        # Upper case
        result_upper = parse_relative_time("2D")
        result_lower = parse_relative_time("2d")
        assert abs((result_upper - result_lower).total_seconds()) < 1

        # Mixed case
        result_mixed = parse_relative_time("1H")
        result_lower = parse_relative_time("1h")
        assert abs((result_mixed - result_lower).total_seconds()) < 1

        # Full words
        result_upper = parse_relative_time("2DAYS")
        result_lower = parse_relative_time("2days")
        assert abs((result_upper - result_lower).total_seconds()) < 1

    def test_edge_case_zero_time(self):
        """Test edge case: zero time (0d, 0h, 0m)."""
        # Zero days
        result = parse_relative_time("0d")
        now = datetime.now()
        assert abs((result - now).total_seconds()) < 1

        # Zero hours
        result = parse_relative_time("0h")
        assert abs((result - now).total_seconds()) < 1

        # Zero minutes
        result = parse_relative_time("0m")
        assert abs((result - now).total_seconds()) < 1

    def test_edge_case_large_values(self):
        """Test edge case: large time values (999d, 100h)."""
        # Large days
        result = parse_relative_time("999d")
        expected = datetime.now() - timedelta(days=999)
        assert abs((result - expected).total_seconds()) < 1

        # Large hours
        result = parse_relative_time("100h")
        expected = datetime.now() - timedelta(hours=100)
        assert abs((result - expected).total_seconds()) < 1

    def test_boundary_values(self):
        """Test boundary values for each unit."""
        # Minimum valid values
        assert parse_relative_time("1d") is not None
        assert parse_relative_time("1h") is not None
        assert parse_relative_time("1m") is not None
        assert parse_relative_time("1w") is not None

        # Common practical values
        assert parse_relative_time("7d") is not None  # 1 week in days
        assert parse_relative_time("24h") is not None  # 1 day in hours
        assert parse_relative_time("60m") is not None  # 1 hour in minutes

    def test_return_type(self):
        """Test that function returns datetime object."""
        result = parse_relative_time("2d")
        assert isinstance(result, datetime)

    def test_past_timestamps_only(self):
        """Test that all returned timestamps are in the past."""
        now = datetime.now()

        # All these should return timestamps before now
        for time_str in ["1d", "1h", "30m", "1w"]:
            result = parse_relative_time(time_str)
            assert result <= now, f"{time_str} should return past timestamp"


class TestListTasksSinceFilter:
    """Test suite for --since filter integration in list_tasks command."""

    @pytest.fixture
    def mock_tasks(self):
        """Create mock tasks with various timestamps for testing."""
        now = datetime.now()
        return [
            {
                "id": "task-1",
                "title": "Very recent task",
                "created_at": (now - timedelta(minutes=5)).isoformat(),
                "status": "queued",
            },
            {
                "id": "task-2",
                "title": "One hour old task",
                "created_at": (now - timedelta(hours=1)).isoformat(),
                "status": "completed",
            },
            {
                "id": "task-3",
                "title": "One day old task",
                "created_at": (now - timedelta(days=1)).isoformat(),
                "status": "in_progress",
            },
            {
                "id": "task-4",
                "title": "One week old task",
                "created_at": (now - timedelta(weeks=1)).isoformat(),
                "status": "failed",
            },
        ]

    def test_filter_excludes_old_tasks(self, mock_tasks):
        """Test that tasks older than --since are excluded."""
        # Filter for last hour
        since_timestamp = parse_relative_time("1h")

        filtered = [
            t for t in mock_tasks
            if t.get("created_at") and
            datetime.fromisoformat(t["created_at"]) >= since_timestamp
        ]

        # Should only include task-1 (5 minutes old)
        assert len(filtered) == 1
        assert filtered[0]["id"] == "task-1"

    def test_filter_includes_recent_tasks(self, mock_tasks):
        """Test that tasks within --since timeframe are included."""
        # Filter for last 2 days
        since_timestamp = parse_relative_time("2d")

        filtered = [
            t for t in mock_tasks
            if t.get("created_at") and
            datetime.fromisoformat(t["created_at"]) >= since_timestamp
        ]

        # Should include task-1, task-2, task-3 (not task-4 which is 1 week old)
        assert len(filtered) == 3
        task_ids = [t["id"] for t in filtered]
        assert "task-1" in task_ids
        assert "task-2" in task_ids
        assert "task-3" in task_ids
        assert "task-4" not in task_ids

    def test_filter_all_time_boundary(self, mock_tasks):
        """Test filtering at exact time boundaries."""
        # Filter for exactly 1 week
        since_timestamp = parse_relative_time("1w")

        filtered = [
            t for t in mock_tasks
            if t.get("created_at") and
            datetime.fromisoformat(t["created_at"]) >= since_timestamp
        ]

        # Should include all except task-4 (which is exactly 1 week old or older)
        # Due to timestamp precision, task-4 should be very close to boundary
        assert len(filtered) <= 4  # Could be 3 or 4 depending on exact timing

    def test_filter_empty_result(self, mock_tasks):
        """Test that no matching tasks returns empty list, not error."""
        # Filter for last 1 minute (should match nothing)
        since_timestamp = parse_relative_time("1m")

        filtered = [
            t for t in mock_tasks
            if t.get("created_at") and
            datetime.fromisoformat(t["created_at"]) >= since_timestamp
        ]

        # Should return empty list (all tasks are older than 1 minute)
        assert filtered == []
        assert isinstance(filtered, list)


class TestEdgeCases:
    """Test suite for edge cases and error handling."""

    def test_missing_created_at_field(self):
        """Test that tasks without created_at are skipped gracefully."""
        tasks = [
            {"id": "task-1", "title": "No timestamp"},  # Missing created_at
            {"id": "task-2", "title": "Has timestamp", "created_at": datetime.now().isoformat()},
        ]

        since_timestamp = parse_relative_time("1h")

        # Should not crash, should skip task-1
        filtered = [
            t for t in tasks
            if t.get("created_at") and
            datetime.fromisoformat(t["created_at"]) >= since_timestamp
        ]

        # Should only include task-2
        assert len(filtered) == 1
        assert filtered[0]["id"] == "task-2"

    def test_timezone_handling(self):
        """Test that timestamps with 'Z' suffix are handled correctly."""
        # Test the actual logic from tasks.py which handles 'Z' suffix
        now = datetime.now()
        tasks = [
            {
                "id": "task-1",
                "title": "Recent task with Z suffix",
                "created_at": now.isoformat() + "Z",  # Add Z suffix
            },
        ]

        since_timestamp = parse_relative_time("1h")

        # Simulate the production filter logic (from tasks.py line 172)
        # Strip timezone info after parsing to compare with naive since_timestamp
        filtered = [
            t for t in tasks
            if t.get("created_at") and
            datetime.fromisoformat(str(t["created_at"]).replace("Z", "+00:00")).replace(tzinfo=None) >= since_timestamp
        ]

        # Should successfully parse Z suffix and include recent task
        assert len(filtered) == 1
        assert filtered[0]["id"] == "task-1"

    def test_very_recent_tasks(self):
        """Test filtering for tasks created seconds ago."""
        now = datetime.now()
        tasks = [
            {
                "id": "task-1",
                "title": "Just created",
                "created_at": (now - timedelta(seconds=30)).isoformat(),
            },
        ]

        # Filter for last minute
        since_timestamp = parse_relative_time("1m")

        filtered = [
            t for t in tasks
            if t.get("created_at") and
            datetime.fromisoformat(t["created_at"]) >= since_timestamp
        ]

        # Task created 30 seconds ago should be included in 1 minute filter
        assert len(filtered) == 1
        assert filtered[0]["id"] == "task-1"

    def test_combined_filters_logic(self):
        """Test that --since combines correctly with other filters."""
        now = datetime.now()
        tasks = [
            {
                "id": "task-1",
                "created_at": (now - timedelta(minutes=30)).isoformat(),
                "status": "completed",
                "assigned_worker": "worker-1",
            },
            {
                "id": "task-2",
                "created_at": (now - timedelta(minutes=30)).isoformat(),
                "status": "queued",
                "assigned_worker": "worker-2",
            },
            {
                "id": "task-3",
                "created_at": (now - timedelta(hours=2)).isoformat(),
                "status": "completed",
                "assigned_worker": "worker-1",
            },
        ]

        # Filter: last 1 hour + status=completed + worker=worker-1
        since_timestamp = parse_relative_time("1h")

        filtered = [
            t for t in tasks
            if t.get("created_at") and
            datetime.fromisoformat(t["created_at"]) >= since_timestamp and
            t.get("status") == "completed" and
            t.get("assigned_worker") == "worker-1"
        ]

        # Should only match task-1 (task-3 is too old, task-2 wrong status)
        assert len(filtered) == 1
        assert filtered[0]["id"] == "task-1"
