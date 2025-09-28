from hive_logging import get_logger

logger = get_logger(__name__)
#!/usr/bin/env python3
"""
Quick reference for completing the final 3 water components.
Each needs the same pattern as the others.
"""

logger.info("=" * 70)
logger.info("FINAL 3 COMPONENTS TO UPDATE")
logger.info("=" * 70)

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
    logger.info(f"\n{comp['name']}:")
    logger.info(f"  File: {comp['file']}")
    logger.info(f"  Base: {comp['base']}")
    logger.info(f"  Pattern: {comp['description']}")

logger.info("\n" + "=" * 70)
logger.info("Each component needs:")
logger.info("1. Split {Component}Optimization into:")
logger.info("   - {Component}OptimizationSimple")
logger.info("   - {Component}OptimizationStandard (inherits from Simple)")
logger.info("2. Update _get_optimization_strategy() factory method")
logger.info("=" * 70)