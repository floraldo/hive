# Phase 2: Climate Validation Consolidation Plan

## Current State
The climate data validation logic is duplicated across multiple files:
- `src/ecosystemiser/profile_loader/climate/processing/validation.py` - Contains QCProfile implementations for all adapters (1000+ lines)
- Individual adapter files (era5.py, nasa_power.py, etc.) - Also contain their own QCProfile classes

## Target Architecture
Following the "co-location" principle, each adapter should contain its own validation logic:
- Base classes remain in `validation/base.py`
- Each adapter file contains its specific QCProfile implementation
- Central validation.py becomes a thin module with only shared utilities

## Migration Steps

### Step 1: Extract Base Classes
Move from `validation.py` to `validation/base.py`:
- QCSeverity enum
- QCIssue dataclass
- QCReport dataclass
- Abstract QCProfile base class

### Step 2: Move Adapter-Specific Profiles
For each adapter (nasa_power, meteostat, era5, pvgis, file_epw):
1. Extract the corresponding QCProfile class from validation.py
2. Move it to the adapter's file
3. Ensure all imports are updated
4. Remove duplicate if one exists in adapter file

### Step 3: Create Profile Factory
In `validation/__init__.py`:
```python
def get_qc_profile(source: str):
    """Factory function to get QC profile for a data source."""
    if source == "nasa_power":
        from ..adapters.nasa_power import NASAPowerQCProfile
        return NASAPowerQCProfile()
    elif source == "meteostat":
        from ..adapters.meteostat import MeteostatQCProfile
        return MeteostatQCProfile()
    # etc...
```

### Step 4: Update Imports
Update all files that import from validation.py to use the new structure

### Step 5: Simplify validation.py
Keep only shared validation utilities that don't belong to specific adapters

## Files to Modify
1. `validation/base.py` (create)
2. `validation/__init__.py` (create factory)
3. `validation.py` (simplify)
4. `adapters/nasa_power.py` (add QCProfile)
5. `adapters/meteostat.py` (add QCProfile)
6. `adapters/era5.py` (add QCProfile)
7. `adapters/pvgis.py` (add QCProfile)
8. `adapters/file_epw.py` (add QCProfile)

## Verification
- Run existing tests to ensure no functionality is broken
- Verify imports still work
- Check that validation still functions correctly