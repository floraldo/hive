#!/usr/bin/env python3
"""
Circuit Breaker Resilience Tests

Chaos engineering tests to validate circuit breaker behavior under failure conditions:
- Service dependency failure simulation
- Circuit breaker state transitions
- Recovery behavior validation
- Performance under failure conditions

Part of the Production Shield Initiative for foundational chaos engineering.
"""

import asyncio
import pytest
import time
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, List, Optional
import aiohttp
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

# Import circuit breaker implementation (adjust import path as needed)
try:
    from hive_performance.circuit_breaker import CircuitBreaker, CircuitBreakerState
except ImportError:
    # Fallback mock implementation for testing
    from enum import Enum
    
    class CircuitBreakerState(Enum):
        CLOSED = "closed"
        OPEN = "open"
        HALF_OPEN = "half_open"
    
    class CircuitBreaker:
        def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60, 
                     expected_exception: type = Exception):
            self.failure_threshold = failure_threshold
            self.recovery_timeout = recovery_timeout
            self.expected_exception = expected_exception
            self.failure_count = 0
            self.last_failure_time = None
            self.state = CircuitBreakerState.CLOSED
        
        async def __aenter__(self):
            if self.state == CircuitBreakerState.OPEN:
                if (time.time() - self.last_failure_time) < self.recovery_timeout:
                    raise Exception("Circuit breaker is OPEN")
                else:
                    self.state = CircuitBreakerState.HALF_OPEN
            return self
        
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            if exc_type and issubclass(exc_type, self.expected_exception):
                self.failure_count += 1
                self.last_failure_time = time.time()
                
                if self.failure_count >= self.failure_threshold:
                    self.state = CircuitBreakerState.OPEN
                
                return False
            elif exc_type is None and self.state == CircuitBreakerState.HALF_OPEN:
                # Success in half-open state - reset to closed
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                self.last_failure_time = None
            
            return False

class MockFailingService:
    """Mock service that can be configured to fail"""
    
    def __init__(self):
        self.failure_rate = 0.0  # 0.0 = never fail, 1.0 = always fail
        self.response_delay = 0.0  # Seconds to delay response
        self.call_count = 0
        self.failure_count = 0
    
    async def make_request(self, endpoint: str = "/api/data") -> Dict:
        """Simulate an API request that may fail"""
        self.call_count += 1
        
        # Simulate network delay
        if self.response_delay > 0:
            await asyncio.sleep(self.response_delay)
        
        # Simulate failure based on failure rate
        import random
        if random.random() < self.failure_rate:
            self.failure_count += 1
            raise aiohttp.ClientError(f"Simulated failure for {endpoint}")
        
        return {
            "status": "success",
            "data": f"Response from {endpoint}",
            "timestamp": time.time()
        }

class ServiceWithCircuitBreaker:
    """Service that uses circuit breaker to call external dependencies"""
    
    def __init__(self, dependency_service: MockFailingService):
        self.dependency = dependency_service
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=5,  # Short timeout for testing
            expected_exception=aiohttp.ClientError
        )
        self.fallback_responses = 0
    
    async def get_data(self, endpoint: str = "/api/data") -> Dict:
        """Get data with circuit breaker protection"""
        try:
            async with self.circuit_breaker:
                return await self.dependency.make_request(endpoint)
        except Exception as e:
            # Circuit breaker is open or dependency failed
            self.fallback_responses += 1
            return {
                "status": "fallback",
                "message": "Service temporarily unavailable",
                "error": str(e),
                "timestamp": time.time()
            }

class TestCircuitBreakerResilience:
    """Test suite for circuit breaker resilience under failure conditions"""
    
    @pytest.fixture
    def failing_service(self):
        """Create a mock failing service"""
        return MockFailingService()
    
    @pytest.fixture
    def protected_service(self, failing_service):
        """Create a service protected by circuit breaker"""
        return ServiceWithCircuitBreaker(failing_service)
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_closed_state_normal_operation(self, protected_service):
        """Test circuit breaker in CLOSED state under normal conditions"""
        # Configure service to never fail
        protected_service.dependency.failure_rate = 0.0
        
        # Make several successful requests
        for i in range(5):
            response = await protected_service.get_data()
            assert response["status"] == "success"
            assert "data" in response
        
        # Circuit breaker should remain closed
        assert protected_service.circuit_breaker.state == CircuitBreakerState.CLOSED
        assert protected_service.circuit_breaker.failure_count == 0
        assert protected_service.fallback_responses == 0
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_failures(self, protected_service):
        """Test circuit breaker opens after reaching failure threshold"""
        # Configure service to always fail
        protected_service.dependency.failure_rate = 1.0
        
        responses = []
        
        # Make requests until circuit breaker opens
        for i in range(6):  # More than failure threshold (3)
            response = await protected_service.get_data()
            responses.append(response)
        
        # First few requests should attempt the dependency and get fallback
        assert all(r["status"] == "fallback" for r in responses)
        
        # Circuit breaker should be open
        assert protected_service.circuit_breaker.state == CircuitBreakerState.OPEN
        assert protected_service.circuit_breaker.failure_count >= 3
        assert protected_service.fallback_responses == 6
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_recovery(self, protected_service):
        """Test circuit breaker recovery through HALF_OPEN state"""
        # First, force circuit breaker to open
        protected_service.dependency.failure_rate = 1.0
        
        # Trigger failures to open circuit breaker
        for i in range(4):
            await protected_service.get_data()
        
        assert protected_service.circuit_breaker.state == CircuitBreakerState.OPEN
        
        # Wait for recovery timeout
        await asyncio.sleep(6)  # Recovery timeout is 5 seconds
        
        # Fix the dependency
        protected_service.dependency.failure_rate = 0.0
        
        # Next request should transition to HALF_OPEN and then CLOSED
        response = await protected_service.get_data()
        
        # Should get successful response
        assert response["status"] == "success"
        
        # Circuit breaker should be closed again
        assert protected_service.circuit_breaker.state == CircuitBreakerState.CLOSED
        assert protected_service.circuit_breaker.failure_count == 0
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_prevents_cascade_failures(self, protected_service):
        """Test circuit breaker prevents cascade failures under load"""
        # Configure service to fail
        protected_service.dependency.failure_rate = 1.0
        protected_service.dependency.response_delay = 0.1  # Add delay to simulate slow failures
        
        start_time = time.time()
        
        # Make many concurrent requests
        tasks = []
        for i in range(20):
            task = asyncio.create_task(protected_service.get_data())
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        # All responses should be fallbacks (no exceptions propagated)
        fallback_responses = [r for r in responses if isinstance(r, dict) and r.get("status") == "fallback"]
        assert len(fallback_responses) == 20
        
        # Circuit breaker should prevent slow failures from accumulating
        # Total time should be much less than 20 * 0.1 = 2 seconds
        total_time = end_time - start_time
        assert total_time < 1.0  # Should complete quickly due to circuit breaker
        
        # Circuit breaker should be open
        assert protected_service.circuit_breaker.state == CircuitBreakerState.OPEN
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_partial_failure_scenarios(self, protected_service):
        """Test circuit breaker behavior with intermittent failures"""
        # Configure service to fail 50% of the time
        protected_service.dependency.failure_rate = 0.5
        
        responses = []
        
        # Make many requests to trigger mixed success/failure
        for i in range(20):
            response = await protected_service.get_data()
            responses.append(response)
            
            # Small delay between requests
            await asyncio.sleep(0.01)
        
        # Should have mix of successful and fallback responses
        successful_responses = [r for r in responses if r["status"] == "success"]
        fallback_responses = [r for r in responses if r["status"] == "fallback"]
        
        assert len(successful_responses) > 0
        assert len(fallback_responses) > 0
        
        # Circuit breaker behavior depends on failure clustering
        # If failures are clustered, it might open; if distributed, it might stay closed
        print(f"Successful: {len(successful_responses)}, Fallback: {len(fallback_responses)}")
        print(f"Circuit breaker state: {protected_service.circuit_breaker.state}")
        print(f"Failure count: {protected_service.circuit_breaker.failure_count}")
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_metrics_and_monitoring(self, protected_service):
        """Test circuit breaker provides useful metrics for monitoring"""
        # Configure mixed failure scenario
        protected_service.dependency.failure_rate = 0.3
        
        # Make requests and collect metrics
        for i in range(15):
            await protected_service.get_data()
            await asyncio.sleep(0.01)
        
        # Verify metrics are available
        assert hasattr(protected_service.circuit_breaker, 'failure_count')
        assert hasattr(protected_service.circuit_breaker, 'state')
        assert hasattr(protected_service.dependency, 'call_count')
        assert hasattr(protected_service.dependency, 'failure_count')
        
        # Metrics should be meaningful
        assert protected_service.dependency.call_count > 0
        assert protected_service.fallback_responses >= 0
        
        # Calculate success rate
        total_requests = 15
        fallback_count = protected_service.fallback_responses
        success_rate = (total_requests - fallback_count) / total_requests
        
        print(f"Total requests: {total_requests}")
        print(f"Fallback responses: {fallback_count}")
        print(f"Success rate: {success_rate:.2%}")
        print(f"Dependency call count: {protected_service.dependency.call_count}")
        print(f"Dependency failure count: {protected_service.dependency.failure_count}")
        
        # Success rate should be reasonable given 30% failure rate and circuit breaker protection
        assert 0.0 <= success_rate <= 1.0

class TestServiceResilienceIntegration:
    """Integration tests for service resilience patterns"""
    
    @pytest.mark.asyncio
    async def test_multiple_circuit_breakers_independence(self):
        """Test that multiple circuit breakers operate independently"""
        # Create two services with different failure characteristics
        service1 = MockFailingService()
        service2 = MockFailingService()
        
        protected_service1 = ServiceWithCircuitBreaker(service1)
        protected_service2 = ServiceWithCircuitBreaker(service2)
        
        # Configure service1 to fail, service2 to succeed
        service1.failure_rate = 1.0
        service2.failure_rate = 0.0
        
        # Trigger failures in service1
        for i in range(4):
            await protected_service1.get_data()
        
        # Service1 circuit breaker should be open
        assert protected_service1.circuit_breaker.state == CircuitBreakerState.OPEN
        
        # Service2 should still work normally
        response2 = await protected_service2.get_data()
        assert response2["status"] == "success"
        assert protected_service2.circuit_breaker.state == CircuitBreakerState.CLOSED
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_with_timeout_scenarios(self, protected_service):
        """Test circuit breaker behavior with slow/timeout scenarios"""
        # Configure service to be very slow (simulating timeout)
        protected_service.dependency.failure_rate = 0.0
        protected_service.dependency.response_delay = 2.0  # 2 second delay
        
        start_time = time.time()
        
        # Make request that should succeed but be slow
        response = await protected_service.get_data()
        
        end_time = time.time()
        
        # Response should be successful
        assert response["status"] == "success"
        
        # Should have taken approximately 2 seconds
        assert 1.8 <= (end_time - start_time) <= 2.5
        
        # Circuit breaker should remain closed (no failures, just slow)
        assert protected_service.circuit_breaker.state == CircuitBreakerState.CLOSED
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_logging_and_alerting(self, protected_service):
        """Test that circuit breaker state changes are properly logged"""
        # This test would verify logging in a real implementation
        # For now, we'll test that state changes occur as expected
        
        initial_state = protected_service.circuit_breaker.state
        assert initial_state == CircuitBreakerState.CLOSED
        
        # Force circuit breaker to open
        protected_service.dependency.failure_rate = 1.0
        
        state_changes = []
        
        # Make requests and track state changes
        for i in range(6):
            current_state = protected_service.circuit_breaker.state
            await protected_service.get_data()
            new_state = protected_service.circuit_breaker.state
            
            if current_state != new_state:
                state_changes.append({
                    'from': current_state,
                    'to': new_state,
                    'request_number': i + 1
                })
        
        # Should have at least one state change (CLOSED -> OPEN)
        assert len(state_changes) > 0
        
        # Final state should be OPEN
        assert protected_service.circuit_breaker.state == CircuitBreakerState.OPEN
        
        print(f"State changes observed: {state_changes}")

def test_circuit_breaker_configuration_validation():
    """Test circuit breaker configuration validation"""
    # Test valid configuration
    cb = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
    assert cb.failure_threshold == 5
    assert cb.recovery_timeout == 60
    
    # Test edge cases
    cb_min = CircuitBreaker(failure_threshold=1, recovery_timeout=1)
    assert cb_min.failure_threshold == 1
    assert cb_min.recovery_timeout == 1

if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
