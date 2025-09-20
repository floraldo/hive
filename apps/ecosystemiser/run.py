#!/usr/bin/env python3
"""
EcoSystemiser Standalone Runner

This script sets up the proper Python path and environment to run EcoSystemiser
as a standalone application within the Hive ecosystem.
"""

import sys
import os
from pathlib import Path

def setup_environment():
    """Setup paths and environment for EcoSystemiser"""

    # Get current directory (ecosystemiser app root)
    app_root = Path(__file__).parent

    # Add Hive root to Python path for accessing Hive utilities
    hive_root = app_root.parents[1]  # Go up two levels to hive root
    if str(hive_root) not in sys.path:
        sys.path.insert(0, str(hive_root))

    # Add app src directory to Python path for local imports
    src_path = app_root / 'src'
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    # Change working directory to app root
    os.chdir(app_root)

    print(f"🐝 EcoSystemiser starting in Hive ecosystem")
    print(f"   App root: {app_root}")
    print(f"   Hive root: {hive_root}")
    print(f"   Working directory: {os.getcwd()}")

def run_server():
    """Run the EcoSystemiser FastAPI server"""

    try:
        # Import after path setup
        from EcoSystemiser.main import app
        from EcoSystemiser.hive_env import get_app_config
        import uvicorn

        # Get configuration
        config = get_app_config()
        host = config.get('ECOSYSTEMISER_HOST', '0.0.0.0')
        port = int(config.get('ECOSYSTEMISER_PORT', '8001'))
        workers = int(config.get('ECOSYSTEMISER_WORKERS', '1'))
        log_level = config.get('ECOSYSTEMISER_LOG_LEVEL', 'info').lower()

        print(f"🚀 Starting EcoSystemiser server on {host}:{port}")
        print(f"   Workers: {workers}")
        print(f"   Log level: {log_level}")

        # Run the server
        uvicorn.run(
            app,
            host=host,
            port=port,
            workers=workers if workers > 1 else None,
            log_level=log_level,
            access_log=True,
            reload=False  # Disable reload in production
        )

    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("   Make sure all dependencies are installed:")
        print("   pip install -r requirements.txt")
        sys.exit(1)

    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        sys.exit(1)

def run_cli():
    """Run EcoSystemiser CLI commands"""

    try:
        # Import after path setup
        from EcoSystemiser.cli import main as cli_main

        # Remove script name and pass remaining args to CLI
        cli_args = sys.argv[2:] if len(sys.argv) > 2 else []

        print(f"🔧 Running EcoSystemiser CLI: {' '.join(cli_args) if cli_args else 'help'}")

        # Call CLI main with remaining arguments
        sys.argv = ['ecosystemiser'] + cli_args
        cli_main()

    except ImportError as e:
        print(f"❌ CLI not available: {e}")
        sys.exit(1)

    except Exception as e:
        print(f"❌ CLI error: {e}")
        sys.exit(1)

def main():
    """Main entry point"""

    setup_environment()

    # Check command line arguments
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python run.py server    # Start FastAPI server")
        print("  python run.py cli [...] # Run CLI commands")
        print("  python run.py help      # Show this help")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == 'server':
        run_server()
    elif command == 'cli':
        run_cli()
    elif command in ['help', '--help', '-h']:
        print("EcoSystemiser Runner - Climate Data Platform")
        print()
        print("Commands:")
        print("  server    Start the FastAPI web server")
        print("  cli       Run CLI commands (pass additional args)")
        print("  help      Show this help message")
        print()
        print("Examples:")
        print("  python run.py server")
        print("  python run.py cli --help")
        print("  python run.py cli fetch-climate --location 'London, UK'")
    else:
        print(f"❌ Unknown command: {command}")
        print("Use 'python run.py help' for available commands")
        sys.exit(1)

if __name__ == '__main__':
    main()