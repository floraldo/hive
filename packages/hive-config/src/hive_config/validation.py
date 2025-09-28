"""
Configuration validation and system health checks for Hive workspace.

This module provides comprehensive validation functions to ensure system
integrity and catch configuration issues early.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .loader import find_project_root
from .path_manager import get_hive_paths, validate_hive_imports
from hive_logging import get_logger

logger = get_logger(__name__)


class ValidationError(Exception):
    """Raised when system validation fails."""
    pass


def validate_python_environment() -> Dict[str, any]:
    """
    Validate Python environment and interpreter requirements.

    Returns:
        Dictionary with validation results and recommendations
    """
    results = {
        'python_version': {
            'current': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            'compatible': sys.version_info >= (3, 8),
            'recommended': sys.version_info >= (3, 11)
        },
        'interpreter_path': sys.executable,
        'platform': sys.platform,
        'issues': [],
        'recommendations': []
    }

    # Check Python version compatibility
    if not results['python_version']['compatible']:
        results['issues'].append(
            f"Python {results['python_version']['current']} is not supported. "
            f"Minimum required: Python 3.8"
        )
    elif not results['python_version']['recommended']:
        results['recommendations'].append(
            f"Consider upgrading to Python 3.11+ for better performance and features"
        )

    # Check for virtual environment
    in_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
    results['virtual_environment'] = {
        'active': in_venv,
        'path': sys.prefix if in_venv else None
    }

    if not in_venv:
        results['recommendations'].append(
            "Consider using a virtual environment for better dependency isolation"
        )

    return results


def validate_project_structure() -> Dict[str, any]:
    """
    Validate Hive project directory structure and required files.

    Returns:
        Dictionary with structure validation results
    """
    try:
        root = find_project_root()
    except RuntimeError as e:
        return {
            'valid': False,
            'error': str(e),
            'issues': ['Could not locate Hive project root']
        }

    results = {
        'valid': True,
        'project_root': str(root),
        'issues': [],
        'missing_directories': [],
        'missing_files': []
    }

    # Check for required directories
    required_dirs = [
        'apps',
        'packages',
        'scripts',
        'tests',
        'hive',
        'hive/db'
    ]

    for dir_path in required_dirs:
        full_path = root / dir_path
        if not full_path.exists():
            results['missing_directories'].append(str(full_path))
            results['valid'] = False

    # Check for required files
    required_files = [
        'pyproject.toml',
        'hive/db/hive.db'
    ]

    for file_path in required_files:
        full_path = root / file_path
        if not full_path.exists():
            results['missing_files'].append(str(full_path))
            if file_path == 'pyproject.toml':
                results['valid'] = False  # Critical file

    return results


def validate_database_connectivity() -> Dict[str, any]:
    """
    Test database connectivity and basic operations.

    Returns:
        Dictionary with database validation results
    """
    results = {
        'accessible': False,
        'tables_exist': False,
        'can_query': False,
        'issues': []
    }

    try:
        import hive_core_db

        # Test basic connection
        conn = hive_core_db.create_connection()
        if conn:
            results['accessible'] = True
            cursor = conn.cursor()

            # Check if tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]

            if 'tasks' in tables:
                results['tables_exist'] = True

                # Test basic query
                cursor.execute("SELECT COUNT(*) FROM tasks")
                count = cursor.fetchone()[0]
                results['can_query'] = True
                results['task_count'] = count

            else:
                results['issues'].append("Required tables not found in database")

            conn.close()
        else:
            results['issues'].append("Could not establish database connection")

    except ImportError as e:
        results['issues'].append(f"Could not import hive_core_db: {e}")
    except Exception as e:
        results['issues'].append(f"Database validation error: {e}")

    return results


def validate_import_system() -> Dict[str, any]:
    """
    Validate the centralized import system and package availability.

    Returns:
        Dictionary with import validation results
    """
    results = {
        'path_manager_working': False,
        'all_imports_successful': False,
        'issues': [],
        'import_results': {}
    }

    try:
        # Test path discovery
        hive_paths = get_hive_paths()
        results['hive_paths_found'] = len(hive_paths)
        results['path_manager_working'] = len(hive_paths) > 0

        # Test imports
        import_results = validate_hive_imports()
        results['import_results'] = import_results

        failed_imports = [mod for mod, result in import_results.items() if result != 'SUCCESS']
        results['all_imports_successful'] = len(failed_imports) == 0

        if failed_imports:
            results['issues'].extend([
                f"Import failed: {mod} - {import_results[mod]}"
                for mod in failed_imports
            ])

    except Exception as e:
        results['issues'].append(f"Import system validation error: {e}")

    return results


def validate_worker_requirements() -> Dict[str, any]:
    """
    Validate that worker spawning requirements are met.

    Returns:
        Dictionary with worker requirements validation
    """
    results = {
        'python_executable': False,
        'modules_importable': False,
        'environment_ready': False,
        'issues': []
    }

    # Check Python executable
    if sys.executable and Path(sys.executable).exists():
        results['python_executable'] = True
    else:
        results['issues'].append("Python executable not found or not accessible")

    # Check if worker module can be imported
    try:
        import hive_orchestrator.worker
        results['modules_importable'] = True
    except ImportError as e:
        results['issues'].append(f"Cannot import worker module: {e}")

    # Check environment variables that workers need
    env_vars = ['PATH', 'PYTHONPATH']
    missing_vars = [var for var in env_vars if var not in os.environ]

    if missing_vars:
        results['issues'].append(f"Missing environment variables: {missing_vars}")
    else:
        results['environment_ready'] = True

    return results


def run_comprehensive_validation() -> Tuple[bool, Dict[str, any]]:
    """
    Run all validation checks and return comprehensive results.

    Returns:
        Tuple of (all_passed: bool, results: dict)
    """
    validation_results = {
        'timestamp': str(Path.cwd() / 'validation_timestamp'),  # Simple timestamp
        'overall_status': 'PENDING',
        'python_environment': validate_python_environment(),
        'project_structure': validate_project_structure(),
        'database': validate_database_connectivity(),
        'import_system': validate_import_system(),
        'worker_requirements': validate_worker_requirements()
    }

    # Determine overall status
    critical_failures = []

    if not validation_results['python_environment']['python_version']['compatible']:
        critical_failures.append('Incompatible Python version')

    if not validation_results['project_structure']['valid']:
        critical_failures.append('Invalid project structure')

    if not validation_results['database']['accessible']:
        critical_failures.append('Database not accessible')

    if not validation_results['import_system']['all_imports_successful']:
        critical_failures.append('Import system failures')

    if not validation_results['worker_requirements']['modules_importable']:
        critical_failures.append('Worker modules not importable')

    if critical_failures:
        validation_results['overall_status'] = 'FAILED'
        validation_results['critical_failures'] = critical_failures
    else:
        validation_results['overall_status'] = 'PASSED'

        # Check for warnings
        warnings = []
        if validation_results['python_environment']['recommendations']:
            warnings.extend(validation_results['python_environment']['recommendations'])

        if warnings:
            validation_results['warnings'] = warnings

    return validation_results['overall_status'] == 'PASSED', validation_results


def format_validation_report(results: Dict[str, any], include_details: bool = True) -> str:
    """
    Format validation results into a human-readable report.

    Args:
        results: Results from run_comprehensive_validation
        include_details: Whether to include detailed information

    Returns:
        Formatted validation report string
    """
    lines = []

    # Header
    status = results['overall_status']
    status_symbol = '✅' if status == 'PASSED' else '❌' if status == 'FAILED' else '⚠️'
    lines.append(f"Hive System Validation Report")
    lines.append(f"Status: {status_symbol} {status}")
    lines.append("=" * 50)

    if include_details:
        # Python Environment
        py_env = results['python_environment']
        lines.append(f"Python Environment:")
        lines.append(f"  Version: {py_env['python_version']['current']} ({'✅' if py_env['python_version']['compatible'] else '❌'})")
        lines.append(f"  Virtual Env: {'✅' if py_env['virtual_environment']['active'] else '⚠️'}")

        # Project Structure
        proj = results['project_structure']
        lines.append(f"Project Structure: {'✅' if proj['valid'] else '❌'}")
        if proj.get('missing_directories'):
            lines.append(f"  Missing dirs: {len(proj['missing_directories'])}")

        # Database
        db = results['database']
        lines.append(f"Database: {'✅' if db['accessible'] and db['can_query'] else '❌'}")
        if 'task_count' in db:
            lines.append(f"  Tasks in DB: {db['task_count']}")

        # Import System
        imports = results['import_system']
        lines.append(f"Import System: {'✅' if imports['all_imports_successful'] else '❌'}")
        lines.append(f"  Paths found: {imports.get('hive_paths_found', 0)}")

        # Worker Requirements
        workers = results['worker_requirements']
        worker_ok = workers['python_executable'] and workers['modules_importable']
        lines.append(f"Worker System: {'✅' if worker_ok else '❌'}")

    # Critical failures
    if 'critical_failures' in results:
        lines.append("\nCritical Issues:")
        for failure in results['critical_failures']:
            lines.append(f"  ❌ {failure}")

    # Warnings
    if 'warnings' in results:
        lines.append("\nRecommendations:")
        for warning in results['warnings']:
            lines.append(f"  ⚠️ {warning}")

    return '\n'.join(lines)