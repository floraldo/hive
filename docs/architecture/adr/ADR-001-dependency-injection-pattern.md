# ADR-001: Adoption of Dependency Injection Pattern

## Status
Accepted

## Context
The Hive platform initially suffered from tight coupling between components, making testing difficult and violating SOLID principles. Components were creating their own dependencies internally, leading to:
- Hard-to-test code requiring extensive mocking
- Violation of Dependency Inversion Principle
- Difficulty in swapping implementations
- Hidden dependencies making the system hard to understand

## Decision
We will adopt Dependency Injection (DI) as the standard pattern for managing dependencies across the Hive platform. All services and components must:
1. Accept dependencies through constructor parameters
2. Define dependencies as interfaces/protocols, not concrete classes
3. Never create their own dependencies internally
4. Use explicit injection, not service locators or singletons

## Consequences

### Positive
- **Testability**: Components can be tested in isolation with test doubles
- **Flexibility**: Easy to swap implementations without changing consumer code
- **Clarity**: All dependencies are explicit and visible in constructors
- **SOLID Compliance**: Adheres to Dependency Inversion and Single Responsibility principles
- **Maintainability**: Changes to implementations don't ripple through the system

### Negative
- **Initial Complexity**: Requires more upfront design with interfaces
- **Boilerplate**: More code for interface definitions and wiring
- **Learning Curve**: Developers need to understand DI patterns

## Implementation
```python
# Good - Dependency Injection
class OrderService:
    def __init__(self, payment_gateway: PaymentGatewayInterface,
                 notification_service: NotificationInterface):
        self.payment_gateway = payment_gateway
        self.notification_service = notification_service

# Bad - Creating dependencies internally
class OrderService:
    def __init__(self):
        self.payment_gateway = StripePaymentGateway()  # Tight coupling
        self.notification_service = EmailService()      # Hard to test
```

## Related
- ADR-002: Golden Rules Architectural Governance
- ADR-004: Service Layer Architecture