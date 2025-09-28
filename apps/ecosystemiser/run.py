from hive_logging import get_logger

logger = get_logger(__name__)
#!/usr/bin/env python3
"""
EcoSystemiser Standalone Runner

This script sets up the proper Python path and environment to run EcoSystemiser
as a standalone application within the Hive ecosystem.
"""

import sys
import os

def setup_environment():
    """Setup environment for EcoSystemiser - now using proper package installation"""

    logger.info(f"🐝 EcoSystemiser starting in Hive ecosystem")
    logger.info(f"   Using installed package imports")
    logger.info(f"   Working directory: {os.getcwd()}")

    # No more path manipulation - EcoSystemiser should be properly installed

def run_server():
    """Run the EcoSystemiser FastAPI server"""

    try:
        # Import after path setup
        from ecosystemiser.main import app
        from ecosystemiser.hive_env import get_app_config
        import uvicorn

        # Get configuration using simplified settings
        from ecosystemiser.hive_env import get_app_settings
        settings = get_app_settings()
        host = settings.get('HOST', '0.0.0.0')
        port = int(settings.get('PORT', '8001'))
        workers = int(settings.get('WORKERS', '1'))
        log_level = settings.get('LOG_LEVEL', 'info').lower()

        logger.info(f"🚀 Starting EcoSystemiser server on {host}:{port}")
        logger.info(f"   Workers: {workers}")
        logger.info(f"   Log level: {log_level}")

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
        logger.error(f"❌ Import error: {e}")
        logger.info("   Make sure EcoSystemiser is installed:")
        logger.info("   pip install -e apps/ecosystemiser")
        sys.exit(1)

    except Exception as e:
        logger.error(f"❌ Failed to start server: {e}")
        sys.exit(1)

def run_cli():
    """Run EcoSystemiser CLI commands"""

    try:
        # Import after path setup
        from ecosystemiser.cli import main as cli_main

        # Remove script name and pass remaining args to CLI
        cli_args = sys.argv[2:] if len(sys.argv) > 2 else []

        logger.info(f"🔧 Running EcoSystemiser CLI: {' '.join(cli_args) if cli_args else 'help'}")

        # Call CLI main with remaining arguments
        sys.argv = ['ecosystemiser'] + cli_args
        cli_main()

    except ImportError as e:
        logger.info(f"❌ CLI not available: {e}")
        sys.exit(1)

    except Exception as e:
        logger.error(f"❌ CLI error: {e}")
        sys.exit(1)

def main():
    """Main entry point"""

    setup_environment()

    # Check command line arguments
    if len(sys.argv) < 2:
        logger.info("Usage:")
        logger.info("  python run.py server    # Start FastAPI server")
        logger.info("  python run.py cli [...] # Run CLI commands")
        logger.info("  python run.py help      # Show this help")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == 'server':
        run_server()
    elif command == 'cli':
        run_cli()
    elif command in ['help', '--help', '-h']:
        logger.info("EcoSystemiser Runner - Climate Data Platform")
        logger.info()
        logger.info("Commands:")
        logger.info("  server    Start the FastAPI web server")
        logger.info("  cli       Run CLI commands (pass additional args)")
        logger.info("  help      Show this help message")
        logger.info()
        logger.info("Examples:")
        logger.info("  python run.py server")
        logger.info("  python run.py cli --help")
        logger.info("  python run.py cli fetch-climate --location 'London, UK'")
    else:
        logger.info(f"❌ Unknown command: {command}")
        logger.info("Use 'python run.py help' for available commands")
        sys.exit(1)

if __name__ == '__main__':
    main()