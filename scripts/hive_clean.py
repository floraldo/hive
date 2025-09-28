#!/usr/bin/env python3
"""Clean the hive database."""
from pathlib import Path


def clean_database():
    """Clean the database."""
    db_path = Path("hive/db/hive-internal.db")
    if db_path.exists():
        db_path.unlink()
        print(f"Database cleaned: {db_path}")
    else:
        print(f"Database not found: {db_path}")


if __name__ == "__main__":
    clean_database()
