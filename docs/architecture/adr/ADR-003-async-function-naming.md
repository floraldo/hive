# ADR-003: Async Function Naming Convention

## Status
Accepted

## Context
The Hive platform uses extensive async/await patterns for performance and scalability. However, inconsistent naming made it difficult to:
- Distinguish async from sync functions at call sites
- Catch accidental sync calls in async contexts
- Understand code flow without checking function definitions
- Maintain consistent patterns across teams

## Decision
All async functions must follow the `_async` suffix convention:
1. Any function defined with `async def` must end with `_async`
2. This applies to all methods, including class methods and properties
3. No exceptions for "obvious" async functions like handlers
4. Enforced via Golden Rule validation

## Consequences

### Positive
- **Clarity**: Immediately obvious which functions are async at call sites
- **Error Prevention**: Harder to accidentally call sync functions in async contexts
- **Consistency**: Single pattern across entire codebase
- **Searchability**: Easy to find all async functions with grep/search
- **Self-Documenting**: Code explains itself without checking definitions

### Negative
- **Verbosity**: Longer function names throughout codebase
- **Migration Effort**: Existing code requires renaming
- **External APIs**: May differ from third-party library conventions

## Implementation
```python
# Good - Clear async naming
async def fetch_user_async(user_id: str) -> User:
    result = await db.query_async("SELECT * FROM users WHERE id = ?", user_id)
    return User.from_dict(result)

async def process_order_async(order: Order) -> None:
    await validate_inventory_async(order.items)
    await charge_payment_async(order.total)
    await send_confirmation_async(order.email)

# Bad - Ambiguous naming
async def fetch_user(user_id: str) -> User:  # Is this async?
    pass

def process_order(order: Order) -> None:  # Or is this?
    pass
```

## Migration Strategy
1. Add Golden Rule validation (completed)
2. Fix violations incrementally by module
3. Update imports and call sites
4. Verify with integration tests

## Related
- ADR-002: Golden Rules Architectural Governance
- ADR-004: Service Layer Architecture