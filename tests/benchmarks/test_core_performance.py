"""
Core performance benchmarks for standard operations.
"""

import asyncio
import json
import sqlite3
import tempfile
from pathlib import Path

import pytest


class TestCorePerformance:
    """Benchmark tests for core Python operations."""

    @pytest.fixture
    def sample_data(self):
        """Generate sample data for testing."""
        return [{"id": i, "name": f"item_{i}", "value": i * 1.5} for i in range(1000)]

    def test_json_serialization_performance(self, benchmark, sample_data):
        """Benchmark JSON serialization and deserialization."""

        def json_operations():
            # Serialize to JSON
            json_string = json.dumps(sample_data)

            # Deserialize from JSON
            parsed_data = json.loads(json_string)

            return len(parsed_data)

        result = benchmark(json_operations)
        assert result == len(sample_data)

    def test_file_io_performance(self, benchmark, sample_data):
        """Benchmark file I/O operations."""

        def file_operations():
            with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
                temp_file = f.name
                # Write data
                json.dump(sample_data, f)

            try:
                # Read data back
                with open(temp_file) as f:
                    loaded_data = json.load(f)
                return len(loaded_data)
            finally:
                Path(temp_file).unlink()

        result = benchmark(file_operations)
        assert result == len(sample_data)

    def test_sqlite_basic_operations(self, benchmark, sample_data):
        """Benchmark basic SQLite operations."""

        def sqlite_operations():
            with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
                db_path = f.name

            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()

                # Create table
                cursor.execute(
                    """
                    CREATE TABLE test_data (
                        id INTEGER PRIMARY KEY,
                        name TEXT,
                        value REAL
                    )
                """,
                )

                # Insert data
                for item in sample_data[:100]:  # Use smaller dataset for performance
                    cursor.execute(
                        "INSERT INTO test_data (id, name, value) VALUES (?, ?, ?)",
                        (item["id"], item["name"], item["value"]),
                    )

                conn.commit()

                # Query data
                cursor.execute("SELECT COUNT(*) FROM test_data")
                count = cursor.fetchone()[0]

                conn.close()
                return count

            finally:
                Path(db_path).unlink()

        result = benchmark(sqlite_operations)
        assert result == 100

    def test_list_comprehension_performance(self, benchmark):
        """Benchmark list comprehension operations."""

        def list_operations():
            # Create large list
            numbers = list(range(10000))

            # Filter even numbers
            evens = [x for x in numbers if x % 2 == 0]

            # Square the numbers
            squares = [x**2 for x in evens]

            return len(squares)

        result = benchmark(list_operations)
        assert result == 5000  # Half of 10000 are even

    def test_dictionary_operations_performance(self, benchmark, sample_data):
        """Benchmark dictionary operations."""

        def dict_operations():
            # Create dictionary from data
            data_dict = {item["id"]: item for item in sample_data}

            # Lookup operations
            lookup_results = []
            for i in range(0, len(sample_data), 10):  # Every 10th item
                if i in data_dict:
                    lookup_results.append(data_dict[i])

            # Update operations
            for item in lookup_results:
                data_dict[item["id"]]["value"] *= 2

            return len(data_dict)

        result = benchmark(dict_operations)
        assert result == len(sample_data)

    def test_string_operations_performance(self, benchmark):
        """Benchmark string manipulation operations."""

        def string_operations():
            base_string = "Hello, World! This is a test string for benchmarking."
            results = []

            for i in range(1000):
                # String formatting
                formatted = f"Item {i}: {base_string}"

                # String manipulation
                upper_case = formatted.upper()
                lower_case = upper_case.lower()
                replaced = lower_case.replace("test", "benchmark")

                # String splitting and joining
                words = replaced.split()
                rejoined = " ".join(words)

                results.append(len(rejoined))

            return sum(results)

        result = benchmark(string_operations)
        assert result > 0

    def test_async_basic_operations(self, benchmark):
        """Benchmark basic async operations."""

        async def async_operations():
            # Create coroutines
            async def async_task(n):
                await asyncio.sleep(0.001)  # Small delay
                return n * 2

            # Run concurrent tasks
            tasks = [async_task(i) for i in range(50)]
            results = await asyncio.gather(*tasks)

            return sum(results)

        def run_async_test():
            return asyncio.run(async_operations())

        result = benchmark(run_async_test)
        expected = sum(i * 2 for i in range(50))
        assert result == expected

    def test_pathlib_operations_performance(self, benchmark):
        """Benchmark pathlib operations."""

        def pathlib_operations():
            # Create temporary directory structure
            with tempfile.TemporaryDirectory() as temp_dir:
                base_path = Path(temp_dir)

                # Create directory structure
                for i in range(10):
                    sub_dir = base_path / f"subdir_{i}"
                    sub_dir.mkdir()

                    # Create files
                    for j in range(5):
                        file_path = sub_dir / f"file_{j}.txt"
                        file_path.write_text(f"Content for file {i}_{j}")

                # Walk directory and count files
                file_count = len(list(base_path.rglob("*.txt")))

                return file_count

        result = benchmark(pathlib_operations)
        assert result == 50  # 10 dirs * 5 files each
