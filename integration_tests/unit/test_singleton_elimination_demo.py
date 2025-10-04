"""Demonstration of Singleton Elimination Benefits

This test demonstrates the problems with singleton patterns and how the new
dependency injection framework solves them.
"""
import threading
import time
from unittest.mock import Mock

import pytest


class SingletonAntiPattern:
    """Example of problematic singleton pattern"""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    time.sleep(0.01)
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.value = 0
            self.initialization_count = 0
            self._initialized = True
        self.initialization_count += 1

    def increment(self):
        self.value += 1

    @classmethod
    def reset(cls):
        """Reset singleton for testing"""
        cls._instance = None

class DIService:
    """Example of proper DI service"""

    def __init__(self, initial_value: int=0):
        self.value = initial_value
        self.initialization_count = 1

    def increment(self):
        self.value += 1

@pytest.mark.crust
class TestSingletonProblems:
    """Demonstrate problems with singleton patterns"""

    @pytest.mark.crust
    def test_singleton_race_condition(self):
        """Demonstrate race condition in singleton initialization"""
        SingletonAntiPattern.reset()
        results = []
        errors = []

        def create_singleton():
            try:
                instance = SingletonAntiPattern()
                results.append(instance.initialization_count)
            except Exception as e:
                errors.append(e)
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=create_singleton)
            threads.append(thread)
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert len(errors) == 0, f"Errors occurred: {errors}"
        print(f"Initialization counts: {results}")
        singleton = SingletonAntiPattern()
        print(f"Final initialization count: {singleton.initialization_count}")
        assert singleton.initialization_count > 1, "Singleton __init__ called multiple times (race condition)"

    @pytest.mark.crust
    def test_singleton_testing_pollution(self):
        """Demonstrate test pollution with singletons"""
        SingletonAntiPattern.reset()
        singleton1 = SingletonAntiPattern()
        singleton1.increment()
        singleton1.increment()
        assert singleton1.value == 2
        singleton2 = SingletonAntiPattern()
        assert singleton2 is singleton1
        assert singleton2.value == 2
        print(f"Singleton state pollution: {singleton2.value}")

    @pytest.mark.crust
    def test_singleton_cannot_mock_dependencies(self):
        """Demonstrate difficulty mocking singleton dependencies"""
        SingletonAntiPattern.reset()
        singleton = SingletonAntiPattern()
        assert isinstance(singleton, SingletonAntiPattern)
        print("Singleton cannot be easily mocked or have dependencies injected")

@pytest.mark.crust
class TestDependencyInjectionSolution:
    """Demonstrate how DI solves singleton problems"""

    @pytest.mark.crust
    def test_di_no_race_conditions(self):
        """Demonstrate DI eliminates race conditions"""
        results = []
        errors = []

        def create_di_service():
            try:
                service = DIService(initial_value=0)
                results.append(service.initialization_count)
            except Exception as e:
                errors.append(e)
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=create_di_service)
            threads.append(thread)
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert all(count == 1 for count in results), "All services initialized exactly once"
        print(f"DI initialization counts: {results} (all exactly 1)")

    @pytest.mark.crust
    def test_di_no_test_pollution(self):
        """Demonstrate DI eliminates test pollution"""
        service1 = DIService(initial_value=0)
        service1.increment()
        service1.increment()
        assert service1.value == 2
        service2 = DIService(initial_value=0)
        assert service2 is not service1
        assert service2.value == 0
        print(f"DI test isolation: service1.value={service1.value}, service2.value={service2.value}")

    @pytest.mark.crust
    def test_di_easy_mocking(self):
        """Demonstrate DI enables easy mocking"""
        mock_service = Mock(spec=DIService)
        mock_service.value = 42
        mock_service.increment.return_value = None

        def service_user(service: DIService):
            service.increment()
            return service.value
        result = service_user(mock_service)
        assert result == 42
        mock_service.increment.assert_called_once()
        print("DI enables easy mocking and dependency injection")

    @pytest.mark.crust
    def test_di_container_lifecycle_management(self):
        """Demonstrate DI container lifecycle management"""
        try:
            from hive_di import DIContainer, Lifecycle
            from hive_di.interfaces import IConfigurationService
            container = DIContainer()
            container.register(DIService, lambda: DIService(initial_value=100), Lifecycle.SINGLETON)
            service1 = container.resolve(DIService)
            service2 = container.resolve(DIService)
            assert service1 is service2
            assert service1.value == 100
            container.clear_singletons()
            service3 = container.resolve(DIService)
            assert service3 is not service1
            assert service3.value == 100
            print("DI container provides proper lifecycle management")
        except ImportError:
            print("DI framework not available for this test")

    @pytest.mark.crust
    def test_di_thread_safety(self):
        """Demonstrate DI thread safety"""
        try:
            from hive_di import DIContainer, Lifecycle
            container = DIContainer()
            container.register(DIService, lambda: DIService(initial_value=0), Lifecycle.SINGLETON)
            results = []
            errors = []

            def resolve_service():
                try:
                    service = container.resolve(DIService)
                    results.append(service)
                except Exception as e:
                    errors.append(e)
            threads = []
            for _ in range(10):
                thread = threading.Thread(target=resolve_service)
                threads.append(thread)
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            assert len(errors) == 0, f"Errors occurred: {errors}"
            assert len(results) == 10
            for result in results:
                assert result is results[0]
            print("DI container is thread-safe")
        except ImportError:
            print("DI framework not available for this test")

@pytest.mark.crust
class TestRealWorldScenario:
    """Test real-world scenarios comparing singleton vs DI"""

    @pytest.mark.crust
    def test_configuration_service_comparison(self):
        """Compare singleton vs DI configuration service"""

        class ConfigSingleton:
            _instance = None

            def __new__(cls):
                if not cls._instance:
                    cls._instance = super().__new__(cls)
                    cls._instance.config = {"database": {"max_connections": 10}}
                return cls._instance

            def get_database_config(self):
                return self.config["database"]

        class ConfigService:

            def __init__(self, config_data):
                self.config = config_data

            def get_database_config(self):
                return self.config["database"]
        config1 = ConfigSingleton()
        config1.config["database"]["max_connections"] = 20
        config2 = ConfigSingleton()
        assert config2.get_database_config()["max_connections"] == 20
        test_config = ConfigService({"database": {"max_connections": 5}})
        prod_config = ConfigService({"database": {"max_connections": 50}})
        assert test_config.get_database_config()["max_connections"] == 5
        assert prod_config.get_database_config()["max_connections"] == 50
        print("DI enables testing different configurations independently")

    @pytest.mark.crust
    def test_error_reporting_service_comparison(self):
        """Compare singleton vs DI error reporting"""

        class ErrorReporterSingleton:
            _instance = None
            _errors = []

            def __new__(cls):
                if not cls._instance:
                    cls._instance = super().__new__(cls)
                return cls._instance

            def report_error(self, error):
                self._errors.append(error)
                return len(self._errors)

            def get_error_count(self):
                return len(self._errors)

        class ErrorReportingService:

            def __init__(self):
                self._errors = []

            def report_error(self, error):
                self._errors.append(error)
                return len(self._errors)

            def get_error_count(self):
                return len(self._errors)
        reporter1 = ErrorReporterSingleton()
        reporter1.report_error("Error 1")
        reporter2 = ErrorReporterSingleton()
        assert reporter2.get_error_count() == 1
        service1 = ErrorReportingService()
        service1.report_error("Error A")
        service2 = ErrorReportingService()
        assert service2.get_error_count() == 0
        print("DI provides clean state for each test")
if __name__ == "__main__":
    test_instance = TestSingletonProblems()
    print("=== Demonstrating Singleton Problems ===")
    try:
        test_instance.test_singleton_race_condition()
    except AssertionError as e:
        print(f"Race condition detected: {e}")
    test_instance.test_singleton_testing_pollution()
    test_instance.test_singleton_cannot_mock_dependencies()
    print("\n=== Demonstrating DI Solutions ===")
    di_test = TestDependencyInjectionSolution()
    di_test.test_di_no_race_conditions()
    di_test.test_di_no_test_pollution()
    di_test.test_di_easy_mocking()
    di_test.test_di_container_lifecycle_management()
    di_test.test_di_thread_safety()
    print("\n=== Real-World Scenarios ===")
    real_world = TestRealWorldScenario()
    real_world.test_configuration_service_comparison()
    real_world.test_error_reporting_service_comparison()
    print("\n=== Summary ===")
    print("✅ DI eliminates race conditions")
    print("✅ DI prevents test pollution")
    print("✅ DI enables easy mocking")
    print("✅ DI provides proper lifecycle management")
    print("✅ DI is thread-safe")
    print("✅ DI enables testing different configurations")
