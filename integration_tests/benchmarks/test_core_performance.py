"""Core performance benchmarks for standard operations.
"""
import asyncio
import json
import sqlite3
import tempfile
from pathlib import Path

import pytest


@pytest.mark.crust
class TestCorePerformance:
    """Benchmark tests for core Python operations."""

    @pytest.fixture
    def sample_data(self):
        """Generate sample data for testing."""
        return [{"id": i, "name": f"item_{i}", "value": i * 1.5} for i in range(1000)]

    @pytest.mark.crust
    def test_json_serialization_performance(self, benchmark, sample_data):
        """Benchmark JSON serialization and deserialization."""

        def json_operations():
            json_string = json.dumps(sample_data)
            parsed_data = json.loads(json_string)
            return len(parsed_data)
        result = benchmark(json_operations)
        assert result == len(sample_data)

    @pytest.mark.crust
    def test_file_io_performance(self, benchmark, sample_data):
        """Benchmark file I/O operations."""

        def file_operations():
            with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
                temp_file = f.name
                json.dump(sample_data, f)
            try:
                with open(temp_file) as f:
                    loaded_data = json.load(f)
                return len(loaded_data)
            finally:
                Path(temp_file).unlink()
        result = benchmark(file_operations)
        assert result == len(sample_data)

    @pytest.mark.crust
    def test_sqlite_basic_operations(self, benchmark, sample_data):
        """Benchmark basic SQLite operations."""

        def sqlite_operations():
            with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
                db_path = f.name
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("\n                    CREATE TABLE test_data (\n                        id INTEGER PRIMARY KEY,\n                        name TEXT,\n                        value REAL\n                    )\n                ")
                for item in sample_data[:100]:
                    cursor.execute("INSERT INTO test_data (id, name, value) VALUES (?, ?, ?)", (item["id"], item["name"], item["value"]))
                conn.commit()
                cursor.execute("SELECT COUNT(*) FROM test_data")
                count = cursor.fetchone()[0]
                conn.close()
                return count
            finally:
                Path(db_path).unlink()
        result = benchmark(sqlite_operations)
        assert result == 100

    @pytest.mark.crust
    def test_list_comprehension_performance(self, benchmark):
        """Benchmark list comprehension operations."""

        def list_operations():
            numbers = list(range(10000))
            evens = [x for x in numbers if x % 2 == 0]
            squares = [x ** 2 for x in evens]
            return len(squares)
        result = benchmark(list_operations)
        assert result == 5000

    @pytest.mark.crust
    def test_dictionary_operations_performance(self, benchmark, sample_data):
        """Benchmark dictionary operations."""

        def dict_operations():
            data_dict = {item["id"]: item for item in sample_data}
            lookup_results = []
            for i in range(0, len(sample_data), 10):
                if i in data_dict:
                    lookup_results.append(data_dict[i])
            for item in lookup_results:
                data_dict[item["id"]]["value"] *= 2
            return len(data_dict)
        result = benchmark(dict_operations)
        assert result == len(sample_data)

    @pytest.mark.crust
    def test_string_operations_performance(self, benchmark):
        """Benchmark string manipulation operations."""

        def string_operations():
            base_string = "Hello, World! This is a test string for benchmarking."
            results = []
            for i in range(1000):
                formatted = f"Item {i}: {base_string}"
                upper_case = formatted.upper()
                lower_case = upper_case.lower()
                replaced = lower_case.replace("test", "benchmark")
                words = replaced.split()
                rejoined = " ".join(words)
                results.append(len(rejoined))
            return sum(results)
        result = benchmark(string_operations)
        assert result > 0

    @pytest.mark.crust
    def test_async_basic_operations(self, benchmark):
        """Benchmark basic async operations."""

        async def async_operations():

            async def async_task(n):
                await asyncio.sleep(0.001)
                return n * 2
            tasks = [async_task(i) for i in range(50)]
            results = await asyncio.gather(*tasks)
            return sum(results)

        def run_async_test():
            return asyncio.run(async_operations())
        result = benchmark(run_async_test)
        expected = sum(i * 2 for i in range(50))
        assert result == expected

    @pytest.mark.crust
    def test_pathlib_operations_performance(self, benchmark):
        """Benchmark pathlib operations."""

        def pathlib_operations():
            with tempfile.TemporaryDirectory() as temp_dir:
                base_path = Path(temp_dir)
                for i in range(10):
                    sub_dir = base_path / f"subdir_{i}"
                    sub_dir.mkdir()
                    for j in range(5):
                        file_path = sub_dir / f"file_{j}.txt"
                        file_path.write_text(f"Content for file {i}_{j}")
                file_count = len(list(base_path.rglob("*.txt")))
                return file_count
        result = benchmark(pathlib_operations)
        assert result == 50
