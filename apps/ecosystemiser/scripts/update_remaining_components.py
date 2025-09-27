#!/usr/bin/env python3
"""
Update the remaining 4 components with separate optimization strategies.
"""

# Component update specifications
COMPONENTS = [
    {
        'file': 'energy/heat_demand.py',
        'component': 'HeatDemand',
        'old_class': 'HeatDemandOptimization',
        'base': 'BaseDemandOptimization'
    },
    {
        'file': 'water/water_demand.py',
        'component': 'WaterDemand',
        'old_class': 'WaterDemandOptimization',
        'base': 'BaseDemandOptimization'
    },
    {
        'file': 'water/water_storage.py',
        'component': 'WaterStorage',
        'old_class': 'WaterStorageOptimization',
        'base': 'BaseStorageOptimization'
    },
    {
        'file': 'water/rainwater_source.py',
        'component': 'RainwaterSource',
        'old_class': 'RainwaterSourceOptimization',
        'base': 'BaseGenerationOptimization'
    }
]

print("Components to update:")
for comp in COMPONENTS:
    print(f"  - {comp['component']}: {comp['file']}")

print(f"\nTotal: {len(COMPONENTS)} components remaining")
print("\nEach component needs:")
print("1. Split monolithic Optimization class into Simple and Standard")
print("2. Update factory method to select based on fidelity")
print("3. Ensure Standard inherits from Simple")
print("\nManual update recommended for accuracy.")