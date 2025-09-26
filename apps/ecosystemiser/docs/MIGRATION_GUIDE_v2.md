# Migration Guide: EcoSystemiser v2.0 Architecture

## Breaking Changes

### 1. Hierarchical Technical Parameters (Required)

The flat parameter structure for components has been **removed**. All components now require parameters to be provided through a `technical` block using the hierarchical archetype system.

### 2. No Backward Compatibility

Legacy parameter names (`P_max`, `E_max`, `eta_charge`, etc.) are **no longer supported**. Attempting to use the old format will result in a validation error.

## Migration Steps

### For Battery Components

#### Old Format (No Longer Supported)
```yaml
Battery:
  P_max: 5.0
  E_max: 10.0
  E_init: 5.0
  eta_charge: 0.95
  eta_discharge: 0.95
```

#### New Format (Required)
```yaml
Battery:
  technical:
    # Explicit fidelity control (required)
    fidelity_level: "standard"

    # Core parameters
    capacity_nominal: 10.0  # kWh
    lifetime_years: 20

    # Storage archetype parameters
    efficiency_roundtrip: 0.90  # Replaces eta_charge/discharge
    soc_min: 0.1
    soc_max: 0.9
    initial_soc_pct: 0.5  # Replaces E_init as fraction

    # Battery-specific
    technology: "lithium-ion"
    max_charge_rate: 0.5  # C-rate (replaces P_max)
    max_discharge_rate: 0.5
```

### Parameter Mapping

| Old Parameter | New Parameter | Notes |
|--------------|---------------|-------|
| `E_max` | `technical.capacity_nominal` | Direct mapping |
| `E_init` | `technical.initial_soc_pct` | Now as fraction (0-1) |
| `P_max` | Calculated from `capacity_nominal * max_charge_rate` | Now uses C-rate |
| `eta_charge` | Derived from `sqrt(efficiency_roundtrip)` | Symmetric assumed |
| `eta_discharge` | Derived from `sqrt(efficiency_roundtrip)` | Symmetric assumed |
| `soc_min/max` | `technical.soc_min/max` | Same, but required in technical block |

## Fidelity Levels

### New Explicit Control

Every component must specify its `fidelity_level`:

```yaml
technical:
  fidelity_level: "standard"  # Required field
```

Options:
- `"simple"` - Basic energy balance only (fastest)
- `"standard"` - Normal operation with SOC limits (default)
- `"detailed"` - Includes temperature and degradation effects
- `"research"` - Full physics-based modeling

### Performance Impact

| Fidelity | Constraints | Solve Time (1 year) |
|----------|------------|-------------------|
| SIMPLE | ~N | Minutes |
| STANDARD | ~3N | Hours |
| DETAILED | ~5N | Days |
| RESEARCH | ~10N | Weeks |

## Python API Changes

### Old Code (No Longer Works)
```python
params = {
    'P_max': 5.0,
    'E_max': 10.0,
    'E_init': 5.0,
    'eta_charge': 0.95,
    'eta_discharge': 0.95
}
battery = Battery("my_battery", params, system)
```

### New Code (Required)
```python
from src.EcoSystemiser.system_model.components.energy.battery import (
    Battery,
    BatteryParams,
    BatteryTechnicalParams
)
from src.EcoSystemiser.system_model.components.shared.archetypes import FidelityLevel

params = BatteryParams(
    technical=BatteryTechnicalParams(
        capacity_nominal=10.0,
        efficiency_roundtrip=0.90,
        fidelity_level=FidelityLevel.STANDARD,
        max_charge_rate=0.5,
        technology="lithium-ion"
    )
)
battery = Battery("my_battery", params, system)
```

## Validation

### Checking Your Migration

1. **Pydantic Validation**: The system will immediately raise a `ValidationError` if you use the old format
2. **Type Checking**: Modern IDEs will show errors for old parameter names
3. **Runtime Validation**: Components validate their technical parameters on initialization

### Common Errors and Solutions

#### Error: `ValidationError: unexpected keyword argument 'P_max'`
**Solution**: Update to use `technical.capacity_nominal` and `technical.max_charge_rate`

#### Error: `AttributeError: 'Battery' object has no attribute 'P_max'`
**Solution**: The Battery internally calculates P_max from technical parameters

#### Error: `TypeError: Battery() got an unexpected keyword argument 'eta_charge'`
**Solution**: Use `technical.efficiency_roundtrip` instead

## Benefits of Migration

1. **Explicit Fidelity Control**: Conscious choice of simulation complexity
2. **Type Safety**: Pydantic validation prevents configuration errors
3. **Scalability**: Ready for 250+ components without code bloat
4. **Maintainability**: Clear separation between generic and specific parameters
5. **Performance**: Explicit fidelity prevents accidental high-complexity simulations

## Support

For help with migration:
1. Review example configurations in `config/simulations/`
2. Check component-specific parameter documentation
3. Use IDE autocomplete with the new Pydantic models
4. Run validation tests after migration

## Timeline

- **v2.0**: Legacy support removed completely
- **All new development**: Must use hierarchical parameter system
- **Existing configs**: Must be migrated before upgrading to v2.0