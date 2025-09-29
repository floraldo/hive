# ADR-006: Defining AI Agentic Frameworks as Core Infrastructure

**Status**: Accepted
**Date**: 2025-09-29
**Authors**: AI Architecture Team
**Supersedes**: Golden Rule 5 (Package vs App Discipline) for AI frameworks

## Context

Golden Rule 5 enforces strict separation between infrastructure packages and business logic applications. The rule currently flags terms like "agent," "workflow," and "task" as potential business logic, causing violations when building AI infrastructure frameworks.

### Current Challenge

The hive-ai package implements:

- **Agent framework**: Abstract base classes and infrastructure for building AI agents
- **Workflow orchestration**: Infrastructure for composing and managing agent workflows
- **Task management**: Framework components for defining and executing AI tasks

These are **infrastructure components** that enable applications to build AI solutions, but they contain keywords that trigger Golden Rule 5 violations.

### Distinction: Framework vs Implementation

**Infrastructure (Packages)**: Provides reusable frameworks, abstractions, and tools

```python
# This is INFRASTRUCTURE - belongs in packages/
class BaseAgent(ABC):
    """Abstract base class for all agents."""
    @abstractmethod
    async def execute_async(self, input_data: Any) -> Any:
        pass

class WorkflowOrchestrator:
    """Framework for orchestrating agent workflows."""
    def add_agent(self, agent: BaseAgent) -> str:
        # Framework method
```

**Business Logic (Apps)**: Implements specific business functionality using frameworks

```python
# This is BUSINESS LOGIC - belongs in apps/
class CustomerServiceAgent(BaseAgent):
    """Specific agent for customer service automation."""
    async def execute_async(self, customer_query: str) -> str:
        # Business-specific implementation
        return await self.handle_customer_query(customer_query)

class EcommerceWorkflow:
    """Specific workflow for e-commerce order processing."""
    # Business-specific workflow implementation
```

## Decision

We **formalize the classification of AI agentic frameworks as legitimate infrastructure** and update Golden Rule 5 to reflect this architectural reality.

### AI Infrastructure Framework Definition

AI frameworks qualify as infrastructure when they provide:

1. **Abstract base classes** for agent/workflow/task implementation
2. **Reusable orchestration** mechanisms across business domains
3. **Provider abstraction** for AI services and models
4. **Common utilities** for AI operations (prompt templates, vector storage, etc.)
5. **No business-specific logic** - purely framework functionality

### Business Logic Classification

AI implementations qualify as business logic when they:

1. **Implement specific business functionality** using AI frameworks
2. **Contain domain-specific knowledge** (customer service, finance, etc.)
3. **Make business decisions** based on AI outputs
4. **Integrate with business systems** (CRM, ERP, etc.)
5. **Serve specific business stakeholders** rather than developers

## Implementation

### Golden Rule 5 Validator Update

The validator will be updated to:

1. **Recognize AI infrastructure packages** by analyzing package structure and content
2. **Apply framework exemptions** for packages that meet infrastructure criteria
3. **Validate business logic separation** within framework packages

### Framework Detection Logic

```python
def is_ai_infrastructure_package(package_path: Path) -> bool:
    """Detect if package provides AI infrastructure frameworks."""

    # Check for abstract base classes
    if has_abstract_agent_classes(package_path):
        return True

    # Check for provider abstraction patterns
    if has_provider_abstraction(package_path):
        return True

    # Check for reusable orchestration
    if has_orchestration_framework(package_path):
        return True

    # Verify no business-specific logic
    if has_business_specific_content(package_path):
        return False

    return False

def validate_ai_framework_purity(package_path: Path) -> ValidationResult:
    """Ensure AI framework contains no business logic."""
    violations = []

    # Check for business-specific terminology
    business_terms = ['customer', 'order', 'payment', 'invoice', 'product']
    # ... validation logic

    return ValidationResult(violations)
```

### Package Structure Validation

#### Valid AI Infrastructure (hive-ai example)

```
packages/hive-ai/
├── src/hive_ai/
│   ├── agents/
│   │   ├── agent.py          # BaseAgent abstract class
│   │   ├── task.py           # Task framework components
│   │   └── workflow.py       # WorkflowOrchestrator framework
│   ├── models/
│   │   └── client.py         # Provider abstraction
│   └── prompts/
│       └── template.py       # Reusable prompt framework
```

#### Business Logic Implementation (would go in apps/)

```
apps/customer-service-ai/
├── src/customer_service_ai/
│   ├── agents/
│   │   ├── support_agent.py      # Specific to customer service
│   │   └── escalation_agent.py   # Business-specific logic
│   ├── workflows/
│   │   └── ticket_workflow.py    # Customer service workflow
│   └── integrations/
│       └── crm_integration.py    # Business system integration
```

## Framework Exemption Criteria

### Automatic Exemption

Packages automatically qualify for AI framework exemption if they:

1. **Contain only abstract base classes** with no concrete implementations
2. **Provide provider abstraction** without business-specific integrations
3. **Implement infrastructure patterns** (circuit breakers, retry logic, etc.)
4. **Offer reusable utilities** that work across business domains

### Manual Review Required

Packages require manual review if they:

1. **Mix framework and implementation** code
2. **Contain some business-specific functionality**
3. **Implement concrete agents** that could be business-focused
4. **Bridge infrastructure and business concerns**

### Disqualification

Packages are disqualified from exemption if they:

1. **Implement specific business processes** using AI
2. **Contain domain-specific knowledge** or business rules
3. **Integrate directly with business systems**
4. **Serve end users** rather than developers

## Examples

### Qualified Infrastructure: hive-ai

**Valid Components**:

- `BaseAgent` - Abstract class for agent implementation
- `WorkflowOrchestrator` - Generic workflow management
- `PromptTemplate` - Reusable prompt framework
- `ModelClient` - Provider abstraction
- `VectorStore` - Data storage abstraction

**Why it qualifies**: Provides reusable frameworks without business logic

### Business Logic: customer-service-ai (hypothetical app)

**Business Components**:

- `CustomerSupportAgent` - Specific to customer service domain
- `TicketClassificationWorkflow` - Business process implementation
- `CRMIntegration` - Business system connectivity
- `CustomerDataProcessor` - Domain-specific data handling

**Why it's business logic**: Implements specific business functionality

### Edge Case: ai-sales-tools (would need review)

**Mixed Components**:

- `SalesAgent` - Could be framework or implementation
- `LeadQualificationWorkflow` - Specific but potentially reusable
- `CRMConnector` - Business integration

**Review needed**: Determine if reusable across domains or business-specific

## Benefits

### Architectural Clarity

- **Clear distinction** between infrastructure and business logic
- **Consistent classification** across AI packages
- **Proper separation of concerns** in AI architecture

### Development Velocity

- **Framework packages** can focus on reusable infrastructure
- **Business applications** can build on stable foundations
- **No false violations** for legitimate infrastructure

### Platform Evolution

- **Enable AI infrastructure** development within packages
- **Support framework innovation** without rule violations
- **Maintain business logic discipline** in applications

## Migration Strategy

### Phase 1: Validator Update (Week 1)

- Update Golden Rule 5 validator with AI framework detection
- Implement framework exemption logic
- Add business logic validation for exempted packages

### Phase 2: Package Classification (Week 2)

- Classify existing AI-related packages
- Document framework vs business logic boundaries
- Create guidelines for future AI package development

### Phase 3: Validation and Compliance (Week 3)

- Run updated validator against all packages
- Address any validation failures
- Establish ongoing compliance monitoring

## Quality Gates

### For AI Framework Packages

- **Abstract base classes**: Must provide abstract interfaces
- **Provider abstraction**: Must support multiple AI providers
- **Business logic prohibition**: No domain-specific functionality
- **Reusability validation**: Must work across business domains

### For AI Business Applications

- **Framework usage**: Must build on infrastructure packages
- **Business focus**: Must implement specific business functionality
- **Domain specificity**: Should serve particular business needs
- **Integration patterns**: Should connect to business systems

## Risks and Mitigations

### Risk: Framework Scope Creep

**Mitigation**: Strict validation of business logic prohibition in framework packages

### Risk: Blurred Boundaries

**Mitigation**: Clear criteria and examples for classification decisions

### Risk: Excessive Exemptions

**Mitigation**: Conservative exemption criteria with manual review requirements

## Success Metrics

- **Compliance**: 100% of AI packages correctly classified
- **Clarity**: Zero ambiguity in framework vs business logic classification
- **Innovation**: AI infrastructure development proceeds without rule violations
- **Discipline**: Business logic remains properly separated in applications

## Conclusion

This ADR formalizes the legitimate place of AI frameworks within the infrastructure layer while maintaining strict discipline around business logic separation. The hive-ai package serves as the exemplar of proper AI infrastructure design.

By updating Golden Rule 5 to recognize AI frameworks as valid infrastructure, we enable the platform to support sophisticated AI capabilities while preserving the architectural discipline that makes the platform unassailable.

This change reflects the **evolution of infrastructure needs** as the platform grows to support AI-first applications, while maintaining the **core principle** of keeping business logic in applications.
