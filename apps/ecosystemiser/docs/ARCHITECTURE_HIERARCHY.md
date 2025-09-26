# EcoSystemiser Component Architecture: Hierarchical Pydantic Models

## Overview

The EcoSystemiser architecture follows a clean, hierarchical structure for component parameters that enables:
1. **Configurable Fidelity**: Explicit control over simulation complexity
2. **Co-location Principle**: Specific models live with their components
3. **Scalability**: Ready for 250+ components without file bloat

## Architecture Principles

### 1. Generic Archetypes (archetypes.py)
The `archetypes.py` file contains ONLY generic, category-level parameter models:
- `BaseTechnicalParams` - Universal parameters for all components
- `StorageTechnicalParams` - Common to all storage types
- `GenerationTechnicalParams` - Common to all generators
- `ConversionTechnicalParams` - Common to all converters
- `TransmissionTechnicalParams` - Common to grid connections
- `DemandTechnicalParams` - Common to all demands

### 2. Co-located Specific Models
Each component file contains its own specific Pydantic models that inherit from archetypes:

```python
# In battery.py
class BatteryTechnicalParams(StorageTechnicalParams):
    """Battery-specific parameters extending storage archetype."""
    technology: str = Field("lithium-ion")
    temperature_coefficient_charge: Optional[float] = None
    # ... other battery-specific params

# In solar_pv.py
class SolarPVTechnicalParams(GenerationTechnicalParams):
    """Solar PV-specific parameters extending generation archetype."""
    panel_efficiency: float = Field(0.20)
    temperature_coefficient: float = Field(-0.004)
    # ... other solar-specific params
```

## Explicit Fidelity Control

### Fidelity Levels
```python
class FidelityLevel(str, Enum):
    SIMPLE = "simple"      # Basic energy balance only
    STANDARD = "standard"  # Normal constraints (default)
    DETAILED = "detailed"  # Temperature, degradation effects
    RESEARCH = "research"  # Full physics modeling
```

### Usage in Components
```python
# In set_constraints() method
fidelity = getattr(self, 'fidelity_level', FidelityLevel.STANDARD)

if fidelity >= FidelityLevel.STANDARD:
    # Add SOC limits, self-discharge

if fidelity >= FidelityLevel.DETAILED:
    # Add temperature effects, degradation

if fidelity >= FidelityLevel.RESEARCH:
    # Add electrochemical modeling
```

## Benefits of This Architecture

### 1. Clean Separation of Concerns
- Generic archetypes define category-wide parameters
- Specific models extend archetypes with component details
- Components own their parameter definitions

### 2. Scalability
- Adding a new component doesn't bloat archetypes.py
- Each component file is self-contained
- Clear inheritance hierarchy

### 3. Explicit Complexity Control
- Users consciously choose fidelity level
- Performance impact is predictable
- No accidental high-complexity simulations

### 4. Maintainability
- New developers can find component models easily
- Changes to specific components don't affect others
- Generic improvements benefit all components

## Migration Guide

### For New Components
1. Identify the category archetype (Storage, Generation, etc.)
2. Create specific Pydantic model in component file
3. Inherit from appropriate archetype
4. Add component-specific parameters
5. Use fidelity level to control constraints

### For Existing Components
1. Move specific Pydantic models from archetypes.py to component file
2. Update imports to reference archetype parent class
3. Ensure co-location principle is followed

## Performance Considerations

### Constraint Generation vs Solver Time
- Python constraint generation: ~0.01% of total time
- Mathematical solver: ~99.9% of total time
- Fidelity checks add nanoseconds, not meaningful overhead

### Fidelity Impact
- SIMPLE: Minutes for year-long simulations
- STANDARD: Hours for year-long simulations
- DETAILED: Days for year-long simulations
- RESEARCH: May require rolling horizon or staged approach

## Example: Complete Battery Implementation

```python
# battery.py
from ..shared.archetypes import StorageTechnicalParams, FidelityLevel

class BatteryTechnicalParams(StorageTechnicalParams):
    """Battery-specific parameters."""
    technology: str = Field("lithium-ion")
    # ... specific params

class BatteryParams(ComponentParams):
    technical: BatteryTechnicalParams

@register_component("Battery")
class Battery(Component):
    def set_constraints(self):
        fidelity = self.technical.fidelity_level

        # Basic constraints always applied
        constraints = [...]

        if fidelity >= FidelityLevel.STANDARD:
            # Add standard constraints

        if fidelity >= FidelityLevel.DETAILED:
            # Add detailed constraints

        return constraints
```

## Conclusion

This architecture provides a clean, scalable foundation for the EcoSystemiser platform, enabling complex energy system simulations with explicit control over the accuracy-performance trade-off. The co-location principle ensures maintainability as the component library grows to 250+ components.