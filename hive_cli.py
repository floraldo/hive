#!/usr/bin/env python3
"""
Hive CLI - Multi-agent orchestration system command-line interface
"""

import argparse
import os
import sys
import shutil
import json
from pathlib import Path
from typing import Optional, Dict, Any

try:
    from orchestrator.main import HiveOrchestrator
    ORCHESTRATOR_AVAILABLE = True
except ImportError:
    ORCHESTRATOR_AVAILABLE = False

from hive_deployment import (
    connect_to_server,
    deploy_application,
    rollback_deployment
)
from hive_logging import get_logger

# Setup logging
logger = get_logger("hive-cli")

def cmd_run(args):
    """Run the interactive orchestrator"""
    if not ORCHESTRATOR_AVAILABLE:
        logger.error("Orchestrator not available. Please install libtmux: pip install libtmux")
        return 1
    
    orchestrator = HiveOrchestrator(
        dry_run=args.dry_run,
        auto_merge=not args.no_auto_merge
    )
    
    print("🐝 Hive Orchestrator Ready")
    print("=" * 50)
    
    if args.task:
        # Single task execution
        orchestrator.run_task(args.task)
    else:
        # Interactive mode
        while True:
            goal = input("\n👑 Queen awaits your command (or 'exit'): ")
            if goal.lower() in ['exit', 'quit']:
                break
            
            orchestrator.run_task(goal)
            
            # Return to main branch
            if not args.dry_run:
                orchestrator.git.repo.git.checkout("main")
    
    print("\n🐝 Hive shutting down gracefully")

def cmd_deploy(args):
    """Deploy an application to a remote server"""
    logger.info(f"Starting deployment of {args.app_name}")
    
    # Load deployment configuration
    config_path = Path(args.config) if args.config else Path.cwd() / "deploy.json"
    if not config_path.exists():
        logger.error(f"Deployment config not found: {config_path}")
        return 1
    
    with open(config_path) as f:
        config = json.load(f)
    
    # Override config with CLI arguments
    if args.host:
        config['ssh_host'] = args.host
    if args.user:
        config['ssh_user'] = args.user
    if args.port:
        config['ssh_port'] = args.port
    
    # Connect to server
    ssh = connect_to_server(config)
    if not ssh:
        logger.error("Failed to connect to server")
        return 1
    
    try:
        # Deploy application
        app_path = Path(args.path) if args.path else Path.cwd()
        success = deploy_application(
            ssh=ssh,
            app_name=args.app_name,
            local_app_path=app_path,
            config=config
        )
        
        if success:
            logger.info(f"✅ Successfully deployed {args.app_name}")
            return 0
        else:
            logger.error(f"❌ Deployment failed for {args.app_name}")
            
            if args.rollback:
                logger.info("Attempting rollback...")
                if rollback_deployment(ssh, args.app_name, config):
                    logger.info("Rollback successful")
                else:
                    logger.error("Rollback failed")
            return 1
            
    finally:
        ssh.close()

def cmd_scaffold(args):
    """Create a new project from a template"""
    templates_dir = Path(__file__).parent / "templates"
    template_path = templates_dir / args.template
    
    if not template_path.exists():
        available = [d.name for d in templates_dir.iterdir() if d.is_dir()]
        logger.error(f"Template '{args.template}' not found")
        logger.info(f"Available templates: {', '.join(available)}")
        return 1
    
    # Create target directory
    target_path = Path(args.path) / args.name
    if target_path.exists() and not args.force:
        logger.error(f"Directory '{target_path}' already exists. Use --force to overwrite")
        return 1
    
    if target_path.exists() and args.force:
        logger.warning(f"Removing existing directory: {target_path}")
        shutil.rmtree(target_path)
    
    # Copy template
    logger.info(f"Creating project '{args.name}' from template '{args.template}'")
    shutil.copytree(template_path, target_path)
    
    # Replace template variables
    replacements = {
        "{{project_name}}": args.name,
        "{{project_description}}": args.description or f"{args.name} API",
        "{{author_name}}": args.author or "Hive Developer",
        "{{author_email}}": args.email or "developer@hive.example.com"
    }
    
    # Process all text files in the project
    for file_path in target_path.rglob("*"):
        if file_path.is_file() and file_path.suffix in ['.py', '.md', '.toml', '.yml', '.yaml', '.json', '.txt', '.env']:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Replace template variables
                for old, new in replacements.items():
                    content = content.replace(old, new)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            except Exception as e:
                logger.warning(f"Could not process {file_path}: {e}")
    
    # Initialize git repository if requested
    if args.git:
        os.chdir(target_path)
        os.system("git init")
        os.system("git add .")
        os.system(f'git commit -m "Initial commit: {args.name} scaffolded with Hive"')
        logger.info("Git repository initialized")
    
    logger.info(f"✅ Project '{args.name}' created successfully at {target_path}")
    logger.info(f"📝 Next steps:")
    logger.info(f"   cd {target_path}")
    logger.info(f"   pip install -e .")
    logger.info(f"   python app.py")
    
    return 0

def cmd_test(args):
    """Run tests for Hive or a specific component"""
    import subprocess
    
    if args.component:
        # Test specific component
        test_path = Path("packages") / f"hive-{args.component}" / "tests"
        if not test_path.exists():
            logger.error(f"Component '{args.component}' not found")
            return 1
        pytest_args = ["pytest", str(test_path)]
    else:
        # Test everything
        pytest_args = ["pytest", "packages/", "apps/", "tests/"]
    
    if args.coverage:
        pytest_args.extend(["--cov=.", "--cov-report=term-missing"])
    
    if args.verbose:
        pytest_args.append("-v")
    
    logger.info(f"Running: {' '.join(pytest_args)}")
    result = subprocess.run(pytest_args)
    return result.returncode

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Hive Multi-Agent Orchestration System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  hive run --task "implement user authentication"
  hive deploy my-app --config deploy.json
  hive scaffold flask-api my-service --git
  hive test --component api --coverage
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Run command
    run_parser = subparsers.add_parser('run', help='Run the orchestrator')
    run_parser.add_argument('--task', help='Single task to execute')
    run_parser.add_argument('--dry-run', action='store_true', help='Simulate without making changes')
    run_parser.add_argument('--no-auto-merge', action='store_true', help='Disable auto-merge on PRs')
    run_parser.set_defaults(func=cmd_run)
    
    # Deploy command
    deploy_parser = subparsers.add_parser('deploy', help='Deploy application to server')
    deploy_parser.add_argument('app_name', help='Application name')
    deploy_parser.add_argument('--path', help='Local application path (default: current directory)')
    deploy_parser.add_argument('--config', help='Deployment config file (default: deploy.json)')
    deploy_parser.add_argument('--host', help='Override SSH host')
    deploy_parser.add_argument('--user', help='Override SSH user')
    deploy_parser.add_argument('--port', type=int, help='Override SSH port')
    deploy_parser.add_argument('--rollback', action='store_true', help='Rollback on failure')
    deploy_parser.set_defaults(func=cmd_deploy)
    
    # Scaffold command
    scaffold_parser = subparsers.add_parser('scaffold', help='Create new project from template')
    scaffold_parser.add_argument('template', help='Template name (e.g., flask-api)')
    scaffold_parser.add_argument('name', help='Project name')
    scaffold_parser.add_argument('--path', default='apps', help='Parent directory for project (default: apps)')
    scaffold_parser.add_argument('--description', help='Project description')
    scaffold_parser.add_argument('--author', help='Author name')
    scaffold_parser.add_argument('--email', help='Author email')
    scaffold_parser.add_argument('--git', action='store_true', help='Initialize git repository')
    scaffold_parser.add_argument('--force', action='store_true', help='Overwrite existing directory')
    scaffold_parser.set_defaults(func=cmd_scaffold)
    
    # Test command
    test_parser = subparsers.add_parser('test', help='Run tests')
    test_parser.add_argument('--component', help='Test specific component (api, logging, db, deployment)')
    test_parser.add_argument('--coverage', action='store_true', help='Generate coverage report')
    test_parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    test_parser.set_defaults(func=cmd_test)
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    # Execute command
    return args.func(args)

if __name__ == "__main__":
    sys.exit(main())