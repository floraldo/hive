"""
Performance benchmarks for database operations.
"""
import tempfile
from pathlib import Path
import pytest
from hive_db import batch_insert, create_table_if_not_exists, get_sqlite_connection, table_exists

@pytest.mark.crust
class TestDatabasePerformance:
    """Benchmark tests for database operations."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        yield db_path
        Path(db_path).unlink()

    @pytest.mark.crust
    def test_batch_insert_small(self, benchmark, temp_db, small_dataset):
        """Benchmark batch insert with small dataset (100 records)."""
        conn = get_sqlite_connection(temp_db)
        create_table_if_not_exists(conn, 'test_data', '\n            id INTEGER PRIMARY KEY,\n            value TEXT,\n            score REAL\n            ')

        def insert_batch():
            batch_insert(conn, 'test_data', small_dataset, columns=['id', 'value', 'score'])
        benchmark(insert_batch)
        conn.close()

    @pytest.mark.crust
    def test_batch_insert_medium(self, benchmark, temp_db, medium_dataset):
        """Benchmark batch insert with medium dataset (10,000 records)."""
        conn = get_sqlite_connection(temp_db)
        create_table_if_not_exists(conn, 'test_data', '\n            id INTEGER PRIMARY KEY,\n            value TEXT,\n            score REAL\n            ')

        def insert_batch():
            batch_insert(conn, 'test_data', medium_dataset, columns=['id', 'value', 'score'])
        benchmark(insert_batch)
        conn.close()

    @pytest.mark.crust
    def test_connection_creation(self, benchmark, temp_db):
        """Benchmark database connection creation."""

        def create_connection():
            conn = get_sqlite_connection(temp_db)
            conn.close()
        benchmark(create_connection)

    @pytest.mark.crust
    def test_table_exists_check(self, benchmark, temp_db):
        """Benchmark table existence check."""
        conn = get_sqlite_connection(temp_db)
        create_table_if_not_exists(conn, 'existing_table', 'id INTEGER PRIMARY KEY')

        def check_table():
            return table_exists(conn, 'existing_table')
        result = benchmark(check_table)
        assert result is True
        conn.close()

    @pytest.mark.crust
    def test_select_performance_indexed(self, benchmark, temp_db, medium_dataset):
        """Benchmark SELECT queries with indexed column."""
        conn = get_sqlite_connection(temp_db)
        create_table_if_not_exists(conn, 'test_data', '\n            id INTEGER PRIMARY KEY,\n            value TEXT,\n            score REAL\n            ')
        batch_insert(conn, 'test_data', medium_dataset, columns=['id', 'value', 'score'])
        conn.execute('CREATE INDEX idx_score ON test_data(score)')
        conn.commit()

        def select_indexed():
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM test_data WHERE score > 5000 AND score < 5100')
            return cursor.fetchall()
        result = benchmark(select_indexed)
        assert len(result) > 0
        conn.close()

    @pytest.mark.crust
    def test_select_performance_unindexed(self, benchmark, temp_db, medium_dataset):
        """Benchmark SELECT queries without index."""
        conn = get_sqlite_connection(temp_db)
        create_table_if_not_exists(conn, 'test_data', '\n            id INTEGER PRIMARY KEY,\n            value TEXT,\n            score REAL\n            ')
        batch_insert(conn, 'test_data', medium_dataset, columns=['id', 'value', 'score'])

        def select_unindexed():
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM test_data WHERE value LIKE 'value_5%'")
            return cursor.fetchall()
        result = benchmark(select_unindexed)
        assert len(result) > 0
        conn.close()

    @pytest.mark.crust
    def test_transaction_performance(self, benchmark, temp_db, small_dataset):
        """Benchmark transaction performance."""
        conn = get_sqlite_connection(temp_db)
        create_table_if_not_exists(conn, 'test_data', '\n            id INTEGER PRIMARY KEY,\n            value TEXT,\n            score REAL\n            ')

        def run_transaction():
            cursor = conn.cursor()
            cursor.execute('BEGIN')
            for record in small_dataset:
                cursor.execute('INSERT OR REPLACE INTO test_data (id, value, score) VALUES (?, ?, ?)', (record['id'], record['value'], record['score']))
            cursor.execute('COMMIT')
        benchmark(run_transaction)
        conn.close()