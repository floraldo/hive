# Hive CLI

Command-line interface utilities and tools for the Hive platform.

## Features

- Standardized CLI argument parsing
- Command registration and routing
- Progress indicators and formatting
- Configuration management

## Usage

```python
from hive_cli import CLIApp, Command

app = CLIApp()
app.register_command(MyCommand())
```
