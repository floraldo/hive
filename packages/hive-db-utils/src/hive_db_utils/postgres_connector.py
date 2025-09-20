"""
PostgreSQL database connector for Hive applications.

Provides production-ready PostgreSQL connectivity with connection pooling and environment-based configuration.
"""

import os
import logging
from typing import Optional, Dict, Any, Union
from contextlib import contextmanager

try:
    import psycopg2
    import psycopg2.pool
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    psycopg2 = None

logger = logging.getLogger(__name__)


def get_postgres_connection(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    **kwargs
) -> 'psycopg2.connection':
    """
    Get a PostgreSQL database connection.

    Args:
        host: Database host (defaults to DB_HOST env var)
        port: Database port (defaults to DB_PORT env var or 5432)
        database: Database name (defaults to DB_NAME env var)
        user: Database user (defaults to DB_USER env var)
        password: Database password (defaults to DB_PASSWORD env var)
        **kwargs: Additional connection parameters

    Returns:
        PostgreSQL connection object

    Raises:
        ImportError: If psycopg2 is not installed
        psycopg2.Error: If connection fails

    Environment Variables:
        DB_HOST: Database host
        DB_PORT: Database port (default: 5432)
        DB_NAME: Database name
        DB_USER: Database user
        DB_PASSWORD: Database password
        DATABASE_URL: Full connection URL (overrides individual parameters)
    """
    if not PSYCOPG2_AVAILABLE:
        raise ImportError(
            "psycopg2-binary is required for PostgreSQL connectivity. "
            "Install it with: pip install psycopg2-binary"
        )

    # Check for full DATABASE_URL first
    database_url = os.getenv('DATABASE_URL')
    if database_url and not any([host, port, database, user, password]):
        try:
            conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor, **kwargs)
            logger.info("PostgreSQL connection established via DATABASE_URL")
            return conn
        except psycopg2.Error as e:
            logger.error(f"Failed to connect via DATABASE_URL: {e}")
            raise

    # Use individual parameters with environment fallbacks
    connection_params = {
        'host': host or os.getenv('DB_HOST', 'localhost'),
        'port': port or int(os.getenv('DB_PORT', '5432')),
        'database': database or os.getenv('DB_NAME'),
        'user': user or os.getenv('DB_USER'),
        'password': password or os.getenv('DB_PASSWORD'),
        'cursor_factory': RealDictCursor
    }

    # Add any additional parameters
    connection_params.update(kwargs)

    # Validate required parameters
    required = ['database', 'user', 'password']
    missing = [param for param in required if not connection_params.get(param)]
    if missing:
        raise ValueError(f"Missing required PostgreSQL parameters: {missing}")

    try:
        conn = psycopg2.connect(**connection_params)
        logger.info(f"PostgreSQL connection established: {connection_params['host']}:{connection_params['port']}/{connection_params['database']}")
        return conn

    except psycopg2.Error as e:
        logger.error(f"Failed to connect to PostgreSQL: {e}")
        raise


@contextmanager
def postgres_transaction(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    **kwargs
):
    """
    Context manager for PostgreSQL transactions.

    Args:
        Same as get_postgres_connection()

    Yields:
        PostgreSQL connection in transaction mode

    Example:
        with postgres_transaction() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO users (name) VALUES (%s)", ("Alice",))
                cur.execute("INSERT INTO users (name) VALUES (%s)", ("Bob",))
                # Transaction commits automatically on success
    """
    conn = None
    try:
        conn = get_postgres_connection(host, port, database, user, password, **kwargs)
        yield conn
        conn.commit()
        logger.debug("PostgreSQL transaction committed")

    except Exception as e:
        if conn:
            conn.rollback()
            logger.error(f"PostgreSQL transaction rolled back: {e}")
        raise

    finally:
        if conn:
            conn.close()


def create_connection_pool(
    minconn: int = 1,
    maxconn: int = 10,
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    **kwargs
) -> 'psycopg2.pool.ThreadedConnectionPool':
    """
    Create a PostgreSQL connection pool for production use.

    Args:
        minconn: Minimum connections in pool
        maxconn: Maximum connections in pool
        Other args: Same as get_postgres_connection()

    Returns:
        Connection pool object

    Example:
        pool = create_connection_pool(minconn=2, maxconn=20)

        # Get connection from pool
        conn = pool.getconn()
        try:
            # Use connection
            pass
        finally:
            pool.putconn(conn)  # Return to pool
    """
    if not PSYCOPG2_AVAILABLE:
        raise ImportError("psycopg2-binary is required for connection pooling")

    # Use same parameter resolution as get_postgres_connection
    database_url = os.getenv('DATABASE_URL')
    if database_url and not any([host, port, database, user, password]):
        try:
            pool = psycopg2.pool.ThreadedConnectionPool(
                minconn, maxconn, database_url, cursor_factory=RealDictCursor, **kwargs
            )
            logger.info(f"PostgreSQL connection pool created via DATABASE_URL: {minconn}-{maxconn} connections")
            return pool
        except psycopg2.Error as e:
            logger.error(f"Failed to create connection pool via DATABASE_URL: {e}")
            raise

    connection_params = {
        'host': host or os.getenv('DB_HOST', 'localhost'),
        'port': port or int(os.getenv('DB_PORT', '5432')),
        'database': database or os.getenv('DB_NAME'),
        'user': user or os.getenv('DB_USER'),
        'password': password or os.getenv('DB_PASSWORD'),
        'cursor_factory': RealDictCursor
    }
    connection_params.update(kwargs)

    # Validate required parameters
    required = ['database', 'user', 'password']
    missing = [param for param in required if not connection_params.get(param)]
    if missing:
        raise ValueError(f"Missing required PostgreSQL parameters: {missing}")

    try:
        pool = psycopg2.pool.ThreadedConnectionPool(minconn, maxconn, **connection_params)
        logger.info(f"PostgreSQL connection pool created: {minconn}-{maxconn} connections")
        return pool

    except psycopg2.Error as e:
        logger.error(f"Failed to create PostgreSQL connection pool: {e}")
        raise


def get_postgres_info(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get information about a PostgreSQL database.

    Args:
        Same as get_postgres_connection()

    Returns:
        Dictionary with database information
    """
    try:
        with postgres_transaction(host, port, database, user, password) as conn:
            with conn.cursor() as cur:
                # Get PostgreSQL version
                cur.execute("SELECT version()")
                pg_version = cur.fetchone()['version']

                # Get database size
                cur.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
                db_size = cur.fetchone()['pg_size_pretty']

                # Get table count
                cur.execute("""
                    SELECT COUNT(*) as table_count
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                """)
                table_count = cur.fetchone()['table_count']

                # Get connection info
                cur.execute("SELECT current_database(), current_user")
                db_info = cur.fetchone()

                return {
                    'database': db_info['current_database'],
                    'user': db_info['current_user'],
                    'version': pg_version,
                    'size': db_size,
                    'table_count': table_count,
                    'host': host or os.getenv('DB_HOST', 'localhost'),
                    'port': port or int(os.getenv('DB_PORT', '5432'))
                }

    except Exception as e:
        logger.error(f"Failed to get PostgreSQL info: {e}")
        raise


# Convenience aliases
connect = get_postgres_connection
transaction = postgres_transaction
pool = create_connection_pool
info = get_postgres_info