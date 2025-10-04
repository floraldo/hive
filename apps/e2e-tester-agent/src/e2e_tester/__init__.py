"""e2e-tester-agent - AI-powered end-to-end test generation and execution.

Generates comprehensive browser-based tests from natural language feature
descriptions and executes them using Playwright automation.

Example:
    from e2e_tester import TestGenerator, TestExecutor

    # Generate test
    generator = TestGenerator()
    test_code = await generator.generate_test(
        feature="User can login with Google",
        url="https://app.dev/login"
    )

    # Execute test
    executor = TestExecutor()
    result = executor.execute_test("tests/e2e/test_login.py")

"""

from .scenario_parser import ScenarioParser, TestScenario
from .test_executor import TestExecutor, TestResult
from .test_generator import TestGenerator

__all__ = [
    "ScenarioParser",
    "TestExecutor",
    "TestGenerator",
    "TestResult",
    "TestScenario",
]

__version__ = "0.1.0"
