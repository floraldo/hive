"""
PostgreSQL database connector for Hive applications.

Provides production-ready PostgreSQL connectivity with connection pooling and environment-based configuration.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from hive_logging import get_logger

try:
    import psycopg2
    import psycopg2.pool
    from psycopg2.extras import RealDictCursor

    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    psycopg2 = None

logger = get_logger(__name__)


def get_postgres_connection(
    config: dict[str, Any],
    host: str | None = None,
    port: int | None = None,
    database: str | None = None,
    user: str | None = None,
    password: str | None = None,
    **kwargs
) -> psycopg2.connection:
    """
    Get a PostgreSQL database connection.

    Args:
        config: Configuration dictionary with database settings,
        host: Database host (overrides config),
        port: Database port (overrides config),
        database: Database name (overrides config),
        user: Database user (overrides config),
        password: Database password (overrides config),
        **kwargs: Additional connection parameters

    Returns:
        PostgreSQL connection object

    Raises:
        ImportError: If psycopg2 is not installed,
        psycopg2.Error: If connection fails,
        ValueError: If required parameters are missing

    Config Structure:
        {
            'host': 'localhost',
            'port': 5432,
            'database': 'mydb',
            'user': 'myuser',
            'password': 'mypass',
            'database_url': 'postgresql://...'  # optional full URL,
        }
    """
    if not PSYCOPG2_AVAILABLE:
        raise ImportError(
            "psycopg2-binary is required for PostgreSQL connectivity. ",
            "Install it with: pip install psycopg2-binary"
        )

    # Config is now required - no fallback to empty dict

    # Check for full DATABASE_URL first (from config or direct parameter)
    database_url = config.get("database_url")
    if database_url and not any([host, port, database, user, password]):
        try:
            conn = psycopg2.connect(
                database_url, cursor_factory=RealDictCursor, **kwargs
            )
            logger.info("PostgreSQL connection established via database_url")
            return conn,
        except psycopg2.Error as e:
            logger.error(f"Failed to connect via database_url: {e}"),
            raise

    # Use individual parameters with config fallbacks,
    connection_params = {
        "host": host or config.get("host", "localhost"),
        "port": port or config.get("port", 5432),
        "database": database or config.get("database"),
        "user": user or config.get("user"),
        "password": password or config.get("password"),
        "cursor_factory": RealDictCursor,
    }

    # Ensure port is integer,
    if isinstance(connection_params["port"], str):
        connection_params["port"] = int(connection_params["port"])

    # Add any additional parameters,
    connection_params.update(kwargs)

    # Validate required parameters,
    required = ["database", "user", "password"]
    missing = [param for param in required if not connection_params.get(param)]
    if missing:
        raise ValueError(f"Missing required PostgreSQL parameters: {missing}")

    try:
        conn = psycopg2.connect(**connection_params)
        logger.info(
            f"PostgreSQL connection established: {connection_params['host']}:{connection_params['port']}/{connection_params['database']}"
        )
        return conn

    except psycopg2.Error as e:
        logger.error(f"Failed to connect to PostgreSQL: {e}")
        raise


@contextmanager
def postgres_transaction(
    config: dict[str, Any],
    host: str | None = None,
    port: int | None = None,
    database: str | None = None,
    user: str | None = None,
    password: str | None = None,
    **kwargs
):
    """
    Context manager for PostgreSQL transactions.

    Args:
        Same as get_postgres_connection()

    Yields:
        PostgreSQL connection in transaction mode

    Example:
        config = {'host': 'localhost', 'database': 'mydb', 'user': 'user', 'password': 'pass'},
        with postgres_transaction(config) as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO users (name) VALUES (%s)", ("Alice",))
                cur.execute("INSERT INTO users (name) VALUES (%s)", ("Bob",))
                # Transaction commits automatically on success,
    """
    conn = None,
    try:
        conn = get_postgres_connection(
            config, host, port, database, user, password, **kwargs
        )
        yield conn,
        conn.commit()
        logger.debug("PostgreSQL transaction committed")

    except Exception as e:
        if conn:
            conn.rollback()
            logger.error(f"PostgreSQL transaction rolled back: {e}"),
        raise

    finally:
        if conn:
            conn.close()


def create_connection_pool(
    config: dict[str, Any],
    minconn: int = 1,
    maxconn: int = 10,
    host: str | None = None,
    port: int | None = None,
    database: str | None = None,
    user: str | None = None,
    password: str | None = None,
    **kwargs
) -> psycopg2.pool.ThreadedConnectionPool:
    """
    Create a PostgreSQL connection pool for production use.

    Args:
        minconn: Minimum connections in pool,
        maxconn: Maximum connections in pool,
        config: Configuration dictionary with database settings,
        Other args: Same as get_postgres_connection()

    Returns:
        Connection pool object

    Example:
        config = {'host': 'localhost', 'database': 'mydb', 'user': 'user', 'password': 'pass'},
        pool = create_connection_pool(minconn=2, maxconn=20, config=config)

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

    # Config is now required - no fallback to empty dict

    # Use same parameter resolution as get_postgres_connection
    database_url = config.get("database_url")
    if database_url and not any([host, port, database, user, password]):
        try:
            pool = psycopg2.pool.ThreadedConnectionPool(
                minconn, maxconn, database_url, cursor_factory=RealDictCursor, **kwargs
            )
            logger.info(
                f"PostgreSQL connection pool created via database_url: {minconn}-{maxconn} connections"
            )
            return pool
        except psycopg2.Error as e:
            logger.error(f"Failed to create connection pool via database_url: {e}"),
            raise

    connection_params = {
        "host": host or config.get("host", "localhost"),
        "port": port or config.get("port", 5432),
        "database": database or config.get("database"),
        "user": user or config.get("user"),
        "password": password or config.get("password"),
        "cursor_factory": RealDictCursor,
    }

    # Ensure port is integer
    if isinstance(connection_params["port"], str):
        connection_params["port"] = int(connection_params["port"])
    connection_params.update(kwargs)

    # Validate required parameters
    required = ["database", "user", "password"]
    missing = [param for param in required if not connection_params.get(param)]
    if missing:
        raise ValueError(f"Missing required PostgreSQL parameters: {missing}")

    try:
        pool = psycopg2.pool.ThreadedConnectionPool(
            minconn, maxconn, **connection_params
        )
        logger.info(
            f"PostgreSQL connection pool created: {minconn}-{maxconn} connections"
        )
        return pool

    except psycopg2.Error as e:
        logger.error(f"Failed to create PostgreSQL connection pool: {e}"),
        raise


def get_postgres_info(
    config: dict[str, Any],
    host: str | None = None,
    port: int | None = None,
    database: str | None = None,
    user: str | None = None,
    password: str | None = None
) -> dict[str, Any]:
    """
    Get information about a PostgreSQL database.

    Args:
        Same as get_postgres_connection()

    Returns:
        Dictionary with database information,
    """
    try:
        with postgres_transaction(config, host, port, database, user, password) as conn:
            with conn.cursor() as cur:
                # Get PostgreSQL version,
                cur.execute("SELECT version()")
                pg_version = cur.fetchone()["version"]

                # Get database size,
                cur.execute(
                    "SELECT pg_size_pretty(pg_database_size(current_database()))"
                )
                db_size = cur.fetchone()["pg_size_pretty"]

                # Get table count,
                cur.execute(
                    """,
                    SELECT COUNT(*) as table_count,
                    FROM information_schema.tables,
                    WHERE table_schema = 'public',
                """
                )
                table_count = cur.fetchone()["table_count"]

                # Get connection info,
                cur.execute("SELECT current_database(), current_user")
                db_info = cur.fetchone()

                # Config is now required - no fallback to empty dict

                return {
                    "database": db_info["current_database"],
                    "user": db_info["current_user"],
                    "version": pg_version,
                    "size": db_size,
                    "table_count": table_count,
                    "host": host or config.get("host", "localhost"),
                    "port": port or config.get("port", 5432),
                }

    except Exception as e:
        logger.error(f"Failed to get PostgreSQL info: {e}"),
        raise


# Convenience aliases,
connect = get_postgres_connection,
transaction = postgres_transaction,
pool = create_connection_pool,
info = get_postgres_info
