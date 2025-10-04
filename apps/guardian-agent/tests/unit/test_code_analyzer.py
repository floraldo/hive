"""Comprehensive unit tests for CodeAnalyzer including edge cases."""
from pathlib import Path

import pytest

from guardian_agent.analyzers.code_analyzer import CodeAnalyzer
from guardian_agent.core.interfaces import Severity, ViolationType


@pytest.mark.crust
class TestCodeAnalyzer:
    """Test suite for CodeAnalyzer AST-based analysis."""

    @pytest.fixture
    def analyzer(self):
        """Create CodeAnalyzer instance."""
        return CodeAnalyzer()

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_analyze_high_complexity(self, analyzer):
        """Test detection of high cyclomatic complexity."""
        complex_code = '\ndef very_complex_function(a, b, c, d):\n    """Function with very high complexity."""\n    if a > 0:\n        if b > 0:\n            if c > 0:\n                if d > 0:\n                    for i in range(10):\n                        if i % 2 == 0:\n                            while i < 5:\n                                try:\n                                    if i == 3:\n                                        return i\n                                except:\n                                    pass\n                                i += 1\n                        elif i % 3 == 0:\n                            continue\n                        else:\n                            break\n    elif a < 0:\n        for j in range(5):\n            if j > 2:\n                return j\n    else:\n        try:\n            return 0\n        except:\n            return -1\n'
        result = await analyzer.analyze(Path("test.py"), complex_code)
        complexity_violations = [v for v in result.violations if "complexity" in v.rule.lower()]
        assert len(complexity_violations) > 0
        assert any(v.severity in [Severity.WARNING, Severity.ERROR] for v in complexity_violations)

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_analyze_missing_type_hints(self, analyzer):
        """Test detection of missing type hints."""
        code_without_hints = "\ndef calculate(x, y):\n    return x + y\n\nclass Calculator:\n    def add(self, a, b):\n        return a + b\n\n    def multiply(self, x, y):\n        result = x * y\n        return result\n"
        result = await analyzer.analyze(Path("test.py"), code_without_hints)
        type_suggestions = [s for s in result.suggestions if "type" in s.category.lower()]
        assert len(type_suggestions) > 0
        assert len(type_suggestions) >= 3

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_analyze_long_function(self, analyzer):
        """Test detection of overly long functions."""
        long_function = ("def long_func():\n" + "    x = 1\n" * 100 + "    return x\n",)
        result = await analyzer.analyze(Path("test.py"), long_function)
        long_violations = [v for v in result.violations if "long" in v.rule.lower()]
        assert len(long_violations) > 0

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_analyze_duplicate_code(self, analyzer):
        """Test detection of duplicate code patterns."""
        duplicate_code = '\ndef process_user_data(user):\n    if user.age > 18:\n        user.status = "adult"\n        user.privileges = ["read", "write"]\n        user.validated = True\n        return user\n\ndef process_admin_data(admin):\n    if admin.age > 18:\n        admin.status = "adult"\n        admin.privileges = ["read", "write"]\n        admin.validated = True\n        return admin\n'
        result = await analyzer.analyze(Path("test.py"), duplicate_code)
        duplicate_suggestions = [s for s in result.suggestions if "duplicate" in s.message.lower() or "similar" in s.message.lower()]
        assert len(duplicate_suggestions) > 0

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_analyze_unused_variables(self, analyzer):
        """Test detection of unused variables."""
        unused_var_code = "\ndef function_with_unused():\n    x = 10,\n    y = 20,\n    z = 30  # z is never used,\n    result = x + y,\n    unused_var = 42  # This is never used\n    return result\n"
        result = await analyzer.analyze(Path("test.py"), unused_var_code)
        unused_violations = [v for v in result.violations if "unused" in v.message.lower()]
        assert len(unused_violations) >= 2

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_analyze_malformed_code(self, analyzer):
        """Test handling of malformed/unparseable code."""
        malformed_code = '\ndef broken_function(\n    print("This is broken",\n    if True\n        return,\n'
        result = await analyzer.analyze(Path("test.py"), malformed_code)
        syntax_violations = [v for v in result.violations if v.type == ViolationType.BUG or "syntax" in v.message.lower()]
        assert len(syntax_violations) > 0

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_analyze_empty_file(self, analyzer):
        """Test handling of empty files."""
        result = await analyzer.analyze(Path("empty.py"), "")
        assert result.analyzer_name == "CodeAnalyzer"
        assert result.metrics.get("lines_of_code", 0) == 0

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_analyze_large_file(self, analyzer):
        """Test handling of very large files."""
        large_code = ("\n".join([f"x{i} = {i}" for i in range(10000)]),)
        result = await analyzer.analyze(Path("large.py"), large_code)
        assert result is not None
        assert result.metrics["lines_of_code"] >= 10000

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_analyze_nested_classes(self, analyzer):
        """Test analysis of deeply nested classes and functions."""
        nested_code = "\nclass OuterClass:\n    class MiddleClass:\n        class InnerClass:\n            def deep_method(self):\n                def nested_function():\n                    def even_deeper():\n                        return 42\n                    return even_deeper()\n                return nested_function()\n"
        result = await analyzer.analyze(Path("test.py"), nested_code)
        nesting_violations = [v for v in result.violations if "nest" in v.rule.lower()]
        assert len(nesting_violations) > 0

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_analyze_imports(self, analyzer):
        """Test analysis of import statements."""
        import_code = "\nimport os\nimport sys\nfrom pathlib import Path\nimport json\nimport requests\nfrom typing import List, Dict, Optional\nimport numpy as np\nimport pandas as pd\nfrom . import local_module\nfrom ..parent import parent_module\nimport os  # Duplicate import\n"
        result = await analyzer.analyze(Path("test.py"), import_code)
        assert result.metrics["num_imports"] > 0
        duplicate_import_violations = [v for v in result.violations if "duplicate" in v.message.lower() and "import" in v.message.lower()]
        assert len(duplicate_import_violations) > 0

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_analyze_async_code(self, analyzer):
        """Test analysis of async/await code."""
        async_code = '\nimport asyncio\n\nasync def fetch_data(url):\n    # Missing await\n    result = asyncio.sleep(1)\n    return result\n\nasync def process_data():\n    data = await fetch_data("http://example.com")\n    # Correct usage\n    await asyncio.sleep(0.1)\n    return data\n\ndef sync_function():\n    # Can\'t use await in sync function\n    # await asyncio.sleep(1)\n    pass\n'
        result = await analyzer.analyze(Path("test.py"), async_code)
        await_violations = [v for v in result.violations if "await" in v.message.lower()]
        assert len(await_violations) > 0

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_analyze_exception_handling(self, analyzer):
        """Test analysis of exception handling patterns."""
        exception_code = '\ndef bad_exception_handling():\n    try:\n        risky_operation()\n    except:  # Bare except - bad practice\n        pass\n\ndef good_exception_handling():\n    try:\n        risky_operation()\n    except ValueError as e:\n        logger.error(f"Value error: {e}")\n        raise\n\ndef too_broad_exception():\n    try:\n        something()\n    except Exception:  # Too broad\n        return None\n'
        result = await analyzer.analyze(Path("test.py"), exception_code)
        exception_violations = [v for v in result.violations if "except" in v.message.lower()]
        assert len(exception_violations) >= 2

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_analyze_code_metrics(self, analyzer):
        """Test collection of code metrics."""
        metrics_code = '\nimport os\nimport sys\n\nclass MyClass:\n    def __init__(self):\n        self.value = 0\n\n    def method1(self):\n        return self.value\n\n    def method2(self, x):\n        return x * 2\n\nclass AnotherClass:\n    pass\n\ndef function1():\n    pass\n\ndef function2(a, b):\n    return a + b\n\nasync def async_func():\n    await something()\n\n# Comment line\n"""\nDocstring\nlines\n"""\n'
        result = await analyzer.analyze(Path("test.py"), metrics_code)
        assert result.metrics["num_classes"] == 2
        assert result.metrics["num_functions"] == 3
        assert result.metrics["num_async_functions"] == 1
        assert result.metrics["num_imports"] == 2
        assert result.metrics["lines_of_code"] > 20

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_analyze_security_issues(self, analyzer):
        """Test detection of basic security issues."""
        security_code = '\nimport os\nimport subprocess\nimport pickle\n\ndef unsafe_command(user_input):\n    # Command injection vulnerability\n    os.system(f"echo {user_input}")\n\ndef unsafe_subprocess(cmd):\n    # Shell injection\n    subprocess.call(cmd, shell=True)\n\ndef unsafe_eval(user_code):\n    # Code injection\n    result = eval(user_code)\n    return result\n\ndef unsafe_pickle(data):\n    # Pickle can execute arbitrary code\n    return pickle.loads(data)\n'
        result = await analyzer.analyze(Path("test.py"), security_code)
        security_violations = [v for v in result.violations if v.severity == Severity.CRITICAL or "security" in v.message.lower()]
        assert len(security_violations) >= 3

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_analyze_naming_conventions(self, analyzer):
        """Test detection of naming convention violations."""
        naming_code = "\ndef BadFunctionName():  # Should be snake_case\n    pass\n\nclass my_class:  # Should be PascalCase\n    pass\n\ndef __private_function():  # OK\n    pass\n\nMyConstant = 42  # Should be UPPER_CASE for constants\nmy_VARIABLE = 10  # Mixed case\n\nclass _PrivateClass:  # OK\n    pass\n"
        result = await analyzer.analyze(Path("test.py"), naming_code)
        naming_violations = [v for v in result.violations if "naming" in v.rule.lower() or "convention" in v.message.lower()]
        assert len(naming_violations) >= 2
