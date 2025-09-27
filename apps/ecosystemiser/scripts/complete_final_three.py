#!/usr/bin/env python3
"""
Quick reference for completing the final 3 water components.
Each needs the same pattern as the others.
"""

print("=" * 70)
print("FINAL 3 COMPONENTS TO UPDATE")
print("=" * 70)

components = [
    {
        'name': 'WaterDemand',
        'file': 'water/water_demand.py',
        'base': 'BaseDemandOptimization',
        'description': 'Similar to PowerDemand and HeatDemand'
    },
    {
        'name': 'WaterStorage',
        'file': 'water/water_storage.py',
        'base': 'BaseStorageOptimization',
        'description': 'Similar to Battery and HeatBuffer'
    },
    {
        'name': 'RainwaterSource',
        'file': 'water/rainwater_source.py',
        'base': 'BaseGenerationOptimization',
        'description': 'Similar to SolarPV'
    }
]

for comp in components:
    print(f"\n{comp['name']}:")
    print(f"  File: {comp['file']}")
    print(f"  Base: {comp['base']}")
    print(f"  Pattern: {comp['description']}")

print("\n" + "=" * 70)
print("Each component needs:")
print("1. Split {Component}Optimization into:")
print("   - {Component}OptimizationSimple")
print("   - {Component}OptimizationStandard (inherits from Simple)")
print("2. Update _get_optimization_strategy() factory method")
print("=" * 70)