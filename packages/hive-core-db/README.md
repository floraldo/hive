# Hive Core DB

Core database management package for the Hive ecosystem.

Provides base database functionality and patterns that can be inherited and extended by Hive applications.

## Features

- Database connection management
- Transaction handling
- Query builders and utilities
- Migration support
- Connection pooling

## Usage

```python
from hive_core_db import DatabaseConnection

# Basic usage
db = DatabaseConnection("sqlite:///my_app.db")
result = db.execute("SELECT * FROM users")
```

## Installation

```bash
pip install -e .
```