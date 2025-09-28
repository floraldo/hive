"""
Pytest configuration for performance benchmarking.
"""

import pytest
from pathlib import Path
import sys

# Add src to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture
def benchmark_data_dir():
    """Directory containing benchmark test data."""
    data_dir = Path(__file__).parent / "test_data"
    data_dir.mkdir(exist_ok=True)
    return data_dir


@pytest.fixture
def small_dataset():
    """Small dataset for quick benchmarks (100 records)."""
    return [{"id": i, "value": f"value_{i}", "score": i * 1.5} for i in range(100)]


@pytest.fixture
def medium_dataset():
    """Medium dataset for standard benchmarks (10,000 records)."""
    return [{"id": i, "value": f"value_{i}", "score": i * 1.5} for i in range(10000)]


@pytest.fixture
def large_dataset():
    """Large dataset for stress benchmarks (100,000 records)."""
    return [{"id": i, "value": f"value_{i}", "score": i * 1.5} for i in range(100000)]