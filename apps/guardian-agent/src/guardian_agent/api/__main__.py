"""Run Guardian Agent API server using hive-app-toolkit."""

from hive_app_toolkit.runner import run_app

from .main import app

if __name__ == "__main__":
    run_app(app)
