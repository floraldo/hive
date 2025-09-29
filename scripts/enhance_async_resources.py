#!/usr/bin/env python3
"""
Enhance Async Resource Management for Hive Platform V4.4

Identifies and fixes async resource management issues:
- Missing context managers for async resources
- Improper exception handling in async contexts
- Missing resource cleanup in finally blocks
- Unprotected concurrent access to shared resources
"""

import ast
import os
import re
from pathlib import Path
from typing import List, Dict, Tuple, Set
from dataclasses import dataclass
from datetime import datetime

from hive_logging import get_logger

logger = get_logger(__name__)


@dataclass
class AsyncIssue:
    """Represents an async resource management issue"""
    file_path: Path
    line_number: int
    issue_type: str
    description: str
    severity: str  # high, medium, low
    suggested_fix: str


class AsyncResourceAnalyzer:
    """Analyzes async resource management patterns"""

    def __init__(self, hive_root: Path = None):
        self.hive_root = hive_root or Path.cwd()
        self.issues = []

    def find_python_files(self) -> List[Path]:
        """Find all Python files with async code"""
        python_files = []

        for pattern in ["packages/**/*.py", "apps/**/*.py"]:
            python_files.extend(self.hive_root.glob(pattern))

        # Filter for files with async patterns
        async_files = []
        for file_path in python_files:
            path_str = str(file_path).lower()
            if not any(exclude in path_str for exclude in ["__pycache__", "archive", "legacy", ".backup"]):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if 'async ' in content or 'asyncio' in content or 'await ' in content:
                            async_files.append(file_path)
                except Exception:
                    pass

        return async_files

    def analyze_file(self, file_path: Path) -> List[AsyncIssue]:
        """Analyze a single file for async resource issues"""
        issues = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')

            # Issue 1: asyncio.create_task without storing reference
            task_pattern = re.compile(r'asyncio\.create_task\([^)]+\)(?!\s*=)')
            for i, line in enumerate(lines, 1):
                if task_pattern.search(line):
                    issue = AsyncIssue(
                        file_path=file_path,
                        line_number=i,
                        issue_type="untracked_task",
                        description="Task created without storing reference - may be garbage collected",
                        severity="high",
                        suggested_fix="Store task: task = asyncio.create_task(...)"
                    )
                    issues.append(issue)

            # Issue 2: Missing async context manager
            resource_patterns = [
                (r'await.*\.connect\(', 'connection'),
                (r'await.*\.open\(', 'file'),
                (r'await.*\.acquire\(', 'lock'),
                (r'ClientSession\(', 'session')
            ]

            for pattern, resource_type in resource_patterns:
                pattern_re = re.compile(pattern)
                for i, line in enumerate(lines, 1):
                    if pattern_re.search(line) and 'async with' not in line:
                        # Check if it's not within an async with block (crude check)
                        if i > 1 and 'async with' not in lines[i-2]:
                            issue = AsyncIssue(
                                file_path=file_path,
                                line_number=i,
                                issue_type="missing_context_manager",
                                description=f"{resource_type} opened without async context manager",
                                severity="high",
                                suggested_fix=f"Use: async with ... as {resource_type}:"
                            )
                            issues.append(issue)

            # Issue 3: Missing finally blocks for cleanup
            try_pattern = re.compile(r'^\s*try:')
            await_pattern = re.compile(r'await')
            finally_pattern = re.compile(r'^\s*finally:')

            for i, line in enumerate(lines, 1):
                if try_pattern.match(line):
                    # Check if there's async resource usage in try block
                    has_await = False
                    has_finally = False
                    j = i
                    indent = len(line) - len(line.lstrip())

                    while j < len(lines):
                        next_line = lines[j]
                        next_indent = len(next_line) - len(next_line.lstrip())

                        if next_indent <= indent and next_line.strip():
                            break

                        if await_pattern.search(next_line):
                            has_await = True
                        if finally_pattern.match(next_line):
                            has_finally = True

                        j += 1

                    if has_await and not has_finally:
                        issue = AsyncIssue(
                            file_path=file_path,
                            line_number=i,
                            issue_type="missing_finally",
                            description="Async operations in try block without finally for cleanup",
                            severity="medium",
                            suggested_fix="Add finally block for resource cleanup"
                        )
                        issues.append(issue)

            # Issue 4: Concurrent access without locks
            shared_state_pattern = re.compile(r'self\._\w+\s*=\s*')
            async_def_pattern = re.compile(r'async\s+def\s+')

            # Find all async methods that modify shared state
            async_methods_with_state = []
            for i, line in enumerate(lines, 1):
                if async_def_pattern.search(line):
                    # Check next 20 lines for state modification
                    for j in range(i, min(i + 20, len(lines))):
                        if shared_state_pattern.search(lines[j]):
                            if 'async with' not in lines[j] and 'Lock' not in ' '.join(lines[i:j]):
                                async_methods_with_state.append(i)
                                break

            for line_num in async_methods_with_state:
                issue = AsyncIssue(
                    file_path=file_path,
                    line_number=line_num,
                    issue_type="unprotected_state",
                    description="Async method modifies shared state without lock",
                    severity="medium",
                    suggested_fix="Use asyncio.Lock() to protect shared state"
                )
                issues.append(issue)

            # Issue 5: asyncio.gather without return_exceptions
            gather_pattern = re.compile(r'asyncio\.gather\([^)]+\)(?!.*return_exceptions)')
            for i, line in enumerate(lines, 1):
                if gather_pattern.search(line):
                    issue = AsyncIssue(
                        file_path=file_path,
                        line_number=i,
                        issue_type="unsafe_gather",
                        description="asyncio.gather without return_exceptions=True",
                        severity="low",
                        suggested_fix="Add return_exceptions=True for safer error handling"
                    )
                    issues.append(issue)

        except Exception as e:
            logger.error(f"Error analyzing {file_path}: {e}")

        return issues

    def analyze_all(self) -> Tuple[int, Dict[str, int]]:
        """Analyze all async files for resource management issues"""
        async_files = self.find_python_files()
        logger.info(f"Analyzing {len(async_files)} files with async code")

        stats = {
            "untracked_task": 0,
            "missing_context_manager": 0,
            "missing_finally": 0,
            "unprotected_state": 0,
            "unsafe_gather": 0,
            "total": 0
        }

        for file_path in async_files:
            file_issues = self.analyze_file(file_path)
            self.issues.extend(file_issues)

            for issue in file_issues:
                stats[issue.issue_type] = stats.get(issue.issue_type, 0) + 1
                stats["total"] += 1

        return len(async_files), stats

    def generate_report(self) -> str:
        """Generate async resource management report"""
        files_analyzed, stats = self.analyze_all()

        # Group by severity
        high_severity = [i for i in self.issues if i.severity == "high"]
        medium_severity = [i for i in self.issues if i.severity == "medium"]
        low_severity = [i for i in self.issues if i.severity == "low"]

        report = f"""
# Async Resource Management Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Summary
- Files analyzed: {files_analyzed}
- Total issues found: {stats['total']}
- High severity: {len(high_severity)}
- Medium severity: {len(medium_severity)}
- Low severity: {len(low_severity)}

## Issues by Type
- Untracked tasks: {stats.get('untracked_task', 0)}
- Missing context managers: {stats.get('missing_context_manager', 0)}
- Missing finally blocks: {stats.get('missing_finally', 0)}
- Unprotected shared state: {stats.get('unprotected_state', 0)}
- Unsafe gather operations: {stats.get('unsafe_gather', 0)}

## High Severity Issues
"""
        # Show top high severity issues
        for issue in high_severity[:10]:
            rel_path = issue.file_path.relative_to(self.hive_root)
            report += f"\n### {rel_path}:{issue.line_number}\n"
            report += f"- **Issue**: {issue.description}\n"
            report += f"- **Fix**: {issue.suggested_fix}\n"

        if len(high_severity) > 10:
            report += f"\n... and {len(high_severity) - 10} more high severity issues\n"

        # Group by file for summary
        by_file = {}
        for issue in self.issues:
            if issue.file_path not in by_file:
                by_file[issue.file_path] = []
            by_file[issue.file_path].append(issue)

        report += "\n## Files with Most Issues\n"
        sorted_files = sorted(by_file.items(), key=lambda x: len(x[1]), reverse=True)

        for file_path, issues in sorted_files[:5]:
            rel_path = file_path.relative_to(self.hive_root)
            report += f"- {rel_path}: {len(issues)} issues\n"

        return report

    def generate_fixes_script(self) -> str:
        """Generate a script with common async resource management patterns"""
        script = '''#!/usr/bin/env python3
"""
Async Resource Management Best Practices for Hive Platform

Common patterns and utilities for proper async resource management.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional, List, Any
import weakref


class TaskManager:
    """Manages async tasks with proper lifecycle"""

    def __init__(self):
        self._tasks: weakref.WeakSet = weakref.WeakSet()

    def create_task(self, coro) -> asyncio.Task:
        """Create and track a task"""
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        return task

    async def cancel_all(self):
        """Cancel all tracked tasks"""
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()

        # Wait for cancellation
        await asyncio.gather(*tasks, return_exceptions=True)


@asynccontextmanager
async def managed_connection(create_conn, close_conn=None):
    """Generic async context manager for connections"""
    conn = None
    try:
        conn = await create_conn()
        yield conn
    finally:
        if conn and close_conn:
            await close_conn(conn)


class AsyncResourcePool:
    """Thread-safe async resource pool"""

    def __init__(self, create_resource, max_size=10):
        self._create_resource = create_resource
        self._pool = asyncio.Queue(maxsize=max_size)
        self._lock = asyncio.Lock()
        self._closed = False

    async def acquire(self):
        """Acquire resource with proper error handling"""
        if self._closed:
            raise RuntimeError("Pool is closed")

        try:
            # Try to get from pool
            return await asyncio.wait_for(
                self._pool.get(),
                timeout=5.0
            )
        except asyncio.TimeoutError:
            # Create new resource if pool is empty
            async with self._lock:
                return await self._create_resource()

    async def release(self, resource):
        """Release resource back to pool"""
        if not self._closed:
            try:
                await self._pool.put(resource)
            except asyncio.QueueFull:
                # Pool is full, close the resource
                await self._close_resource(resource)

    async def close(self):
        """Close all resources in pool"""
        async with self._lock:
            self._closed = True
            while not self._pool.empty():
                try:
                    resource = self._pool.get_nowait()
                    await self._close_resource(resource)
                except asyncio.QueueEmpty:
                    break


async def safe_gather(*coros, return_exceptions=True):
    """Safer version of asyncio.gather"""
    return await asyncio.gather(
        *coros,
        return_exceptions=return_exceptions
    )


class AsyncStateLock:
    """Lock for protecting shared state in async context"""

    def __init__(self):
        self._lock = asyncio.Lock()
        self._state = {}

    async def update_state(self, key, value):
        """Update state with lock protection"""
        async with self._lock:
            self._state[key] = value

    async def get_state(self, key, default=None):
        """Get state with lock protection"""
        async with self._lock:
            return self._state.get(key, default)


# Example usage patterns
async def example_proper_resource_management():
    """Example of proper async resource management"""

    # 1. Task management
    task_manager = TaskManager()
    task = task_manager.create_task(some_async_operation())

    try:
        await task
    except Exception as e:
        logger.error(f"Task failed: {e}")
    finally:
        await task_manager.cancel_all()

    # 2. Connection management
    async with managed_connection(
        create_conn=create_database_connection,
        close_conn=close_database_connection
    ) as conn:
        await conn.execute("SELECT 1")

    # 3. Pool management
    pool = AsyncResourcePool(create_resource=create_connection)
    try:
        resource = await pool.acquire()
        try:
            await use_resource(resource)
        finally:
            await pool.release(resource)
    finally:
        await pool.close()

    # 4. Safe gathering
    results = await safe_gather(
        operation1(),
        operation2(),
        operation3(),
        return_exceptions=True
    )

    # 5. Protected state
    state_lock = AsyncStateLock()
    await state_lock.update_state("counter", 1)
    value = await state_lock.get_state("counter")
'''
        return script


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Enhance async resource management")
    parser.add_argument("--report", action="store_true", help="Generate analysis report")
    parser.add_argument("--generate-patterns", action="store_true",
                       help="Generate best practices script")

    args = parser.parse_args()

    analyzer = AsyncResourceAnalyzer()

    if args.report:
        print(analyzer.generate_report())
    elif args.generate_patterns:
        script = analyzer.generate_fixes_script()
        output_path = Path.cwd() / "async_resource_patterns.py"
        with open(output_path, 'w') as f:
            f.write(script)
        print(f"Generated best practices script: {output_path}")
    else:
        print("Use --report for analysis or --generate-patterns for best practices")


if __name__ == "__main__":
    main()