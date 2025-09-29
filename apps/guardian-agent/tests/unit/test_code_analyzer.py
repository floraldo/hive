"""Comprehensive unit tests for CodeAnalyzer including edge cases."""

from pathlib import Path

import pytest
from guardian_agent.analyzers.code_analyzer import CodeAnalyzer
from guardian_agent.core.interfaces import Severity, ViolationType


class TestCodeAnalyzer:
    """Test suite for CodeAnalyzer AST-based analysis."""

    @pytest.fixture
    def analyzer(self):
        """Create CodeAnalyzer instance."""
        return CodeAnalyzer()

    @pytest.mark.asyncio
    async def test_analyze_high_complexity(self, analyzer):
        """Test detection of high cyclomatic complexity."""
        complex_code = '''
def very_complex_function(a, b, c, d):
    """Function with very high complexity."""
    if a > 0:
        if b > 0:
            if c > 0:
                if d > 0:
                    for i in range(10):
                        if i % 2 == 0:
                            while i < 5:
                                try:
                                    if i == 3:
                                        return i
                                except:
                                    pass
                                i += 1
                        elif i % 3 == 0:
                            continue
                        else:
                            break
    elif a < 0:
        for j in range(5):
            if j > 2:
                return j
    else:
        try:
            return 0
        except:
            return -1
'''

        result = await analyzer.analyze(Path("test.py"), complex_code)

        complexity_violations = [v for v in result.violations if "complexity" in v.rule.lower()]
        assert len(complexity_violations) > 0
        assert any(v.severity in [Severity.WARNING, Severity.ERROR] for v in complexity_violations)

    @pytest.mark.asyncio
    async def test_analyze_missing_type_hints(self, analyzer):
        """Test detection of missing type hints."""
        code_without_hints = """
def calculate(x, y):
    return x + y

class Calculator:
    def add(self, a, b):
        return a + b

    def multiply(self, x, y):
        result = x * y
        return result
"""

        result = await analyzer.analyze(Path("test.py"), code_without_hints)

        type_suggestions = [s for s in result.suggestions if "type" in s.category.lower()]
        assert len(type_suggestions) > 0
        # Should suggest type hints for all functions
        assert len(type_suggestions) >= 3

    @pytest.mark.asyncio
    async def test_analyze_long_function(self, analyzer):
        """Test detection of overly long functions."""
        long_function = "def long_func():\n" + "    x = 1\n" * 100 + "    return x\n"

        result = await analyzer.analyze(Path("test.py"), long_function)

        long_violations = [v for v in result.violations if "long" in v.rule.lower()]
        assert len(long_violations) > 0

    @pytest.mark.asyncio
    async def test_analyze_duplicate_code(self, analyzer):
        """Test detection of duplicate code patterns."""
        duplicate_code = """
def process_user_data(user):
    if user.age > 18:
        user.status = "adult"
        user.privileges = ["read", "write"]
        user.validated = True
        return user

def process_admin_data(admin):
    if admin.age > 18:
        admin.status = "adult"
        admin.privileges = ["read", "write"]
        admin.validated = True
        return admin
"""

        result = await analyzer.analyze(Path("test.py"), duplicate_code)

        duplicate_suggestions = [
            s for s in result.suggestions if "duplicate" in s.message.lower() or "similar" in s.message.lower()
        ]
        assert len(duplicate_suggestions) > 0

    @pytest.mark.asyncio
    async def test_analyze_unused_variables(self, analyzer):
        """Test detection of unused variables."""
        unused_var_code = """
def function_with_unused():
    x = 10
    y = 20
    z = 30  # z is never used
    result = x + y
    unused_var = 42  # This is never used
    return result
"""

        result = await analyzer.analyze(Path("test.py"), unused_var_code)

        unused_violations = [v for v in result.violations if "unused" in v.message.lower()]
        assert len(unused_violations) >= 2

    @pytest.mark.asyncio
    async def test_analyze_malformed_code(self, analyzer):
        """Test handling of malformed/unparseable code."""
        malformed_code = """
def broken_function(
    print("This is broken",
    if True
        return,
"""

        result = await analyzer.analyze(Path("test.py"), malformed_code)

        # Should handle gracefully and report syntax error
        syntax_violations = [
            v for v in result.violations if v.type == ViolationType.BUG or "syntax" in v.message.lower()
        ]
        assert len(syntax_violations) > 0

    @pytest.mark.asyncio
    async def test_analyze_empty_file(self, analyzer):
        """Test handling of empty files."""
        result = await analyzer.analyze(Path("empty.py"), "")

        # Should handle empty files without crashing
        assert result.analyzer_name == "CodeAnalyzer"
        assert result.metrics.get("lines_of_code", 0) == 0

    @pytest.mark.asyncio
    async def test_analyze_large_file(self, analyzer):
        """Test handling of very large files."""
        # Create a large file with 10,000 lines
        large_code = "\n".join([f"x{i} = {i}" for i in range(10000)])

        result = await analyzer.analyze(Path("large.py"), large_code)

        # Should complete analysis without timeout
        assert result is not None
        assert result.metrics["lines_of_code"] >= 10000

    @pytest.mark.asyncio
    async def test_analyze_nested_classes(self, analyzer):
        """Test analysis of deeply nested classes and functions."""
        nested_code = """
class OuterClass:
    class MiddleClass:
        class InnerClass:
            def deep_method(self):
                def nested_function():
                    def even_deeper():
                        return 42
                    return even_deeper()
                return nested_function()
"""

        result = await analyzer.analyze(Path("test.py"), nested_code)

        # Should detect deep nesting
        nesting_violations = [v for v in result.violations if "nest" in v.rule.lower()]
        assert len(nesting_violations) > 0

    @pytest.mark.asyncio
    async def test_analyze_imports(self, analyzer):
        """Test analysis of import statements."""
        import_code = """
import os
import sys
from pathlib import Path
import json
import requests
from typing import List, Dict, Optional
import numpy as np
import pandas as pd
from . import local_module
from ..parent import parent_module
import os  # Duplicate import
"""

        result = await analyzer.analyze(Path("test.py"), import_code)

        # Check import metrics
        assert result.metrics["num_imports"] > 0

        # Should detect duplicate imports
        duplicate_import_violations = [
            v for v in result.violations if "duplicate" in v.message.lower() and "import" in v.message.lower()
        ]
        assert len(duplicate_import_violations) > 0

    @pytest.mark.asyncio
    async def test_analyze_async_code(self, analyzer):
        """Test analysis of async/await code."""
        async_code = """
import asyncio

async def fetch_data(url):
    # Missing await
    result = asyncio.sleep(1)
    return result

async def process_data():
    data = await fetch_data("http://example.com")
    # Correct usage
    await asyncio.sleep(0.1)
    return data

def sync_function():
    # Can't use await in sync function
    # await asyncio.sleep(1)
    pass
"""

        result = await analyzer.analyze(Path("test.py"), async_code)

        # Should detect missing await
        await_violations = [v for v in result.violations if "await" in v.message.lower()]
        assert len(await_violations) > 0

    @pytest.mark.asyncio
    async def test_analyze_exception_handling(self, analyzer):
        """Test analysis of exception handling patterns."""
        exception_code = """
def bad_exception_handling():
    try:
        risky_operation()
    except:  # Bare except - bad practice
        pass

def good_exception_handling():
    try:
        risky_operation()
    except ValueError as e:
        logger.error(f"Value error: {e}")
        raise

def too_broad_exception():
    try:
        something()
    except Exception:  # Too broad
        return None
"""

        result = await analyzer.analyze(Path("test.py"), exception_code)

        exception_violations = [v for v in result.violations if "except" in v.message.lower()]
        assert len(exception_violations) >= 2  # Bare except and too broad

    @pytest.mark.asyncio
    async def test_analyze_code_metrics(self, analyzer):
        """Test collection of code metrics."""
        metrics_code = '''
import os
import sys

class MyClass:
    def __init__(self):
        self.value = 0

    def method1(self):
        return self.value

    def method2(self, x):
        return x * 2

class AnotherClass:
    pass

def function1():
    pass

def function2(a, b):
    return a + b

async def async_func():
    await something()

# Comment line
"""
Docstring
lines
"""
'''

        result = await analyzer.analyze(Path("test.py"), metrics_code)

        assert result.metrics["num_classes"] == 2
        assert result.metrics["num_functions"] == 3
        assert result.metrics["num_async_functions"] == 1
        assert result.metrics["num_imports"] == 2
        assert result.metrics["lines_of_code"] > 20

    @pytest.mark.asyncio
    async def test_analyze_security_issues(self, analyzer):
        """Test detection of basic security issues."""
        security_code = """
import os
import subprocess
import pickle

def unsafe_command(user_input):
    # Command injection vulnerability
    os.system(f"echo {user_input}")

def unsafe_subprocess(cmd):
    # Shell injection
    subprocess.call(cmd, shell=True)

def unsafe_eval(user_code):
    # Code injection
    result = eval(user_code)
    return result

def unsafe_pickle(data):
    # Pickle can execute arbitrary code
    return pickle.loads(data)
"""

        result = await analyzer.analyze(Path("test.py"), security_code)

        security_violations = [
            v for v in result.violations if v.severity == Severity.CRITICAL or "security" in v.message.lower()
        ]
        assert len(security_violations) >= 3

    @pytest.mark.asyncio
    async def test_analyze_naming_conventions(self, analyzer):
        """Test detection of naming convention violations."""
        naming_code = """
def BadFunctionName():  # Should be snake_case
    pass

class my_class:  # Should be PascalCase
    pass

def __private_function():  # OK
    pass

MyConstant = 42  # Should be UPPER_CASE for constants
my_VARIABLE = 10  # Mixed case

class _PrivateClass:  # OK
    pass
"""

        result = await analyzer.analyze(Path("test.py"), naming_code)

        naming_violations = [
            v for v in result.violations if "naming" in v.rule.lower() or "convention" in v.message.lower()
        ]
        assert len(naming_violations) >= 2
