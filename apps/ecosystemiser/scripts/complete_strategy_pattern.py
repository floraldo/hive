#!/usr/bin/env python3
"""
Script to complete the Strategy Pattern implementation for remaining components.
This will update the optimization classes to have separate Simple and Standard versions.
"""

import re
from pathlib import Path

def refactor_component(component_file_path, component_name, base_class):
    """Refactor a component to have separate Simple and Standard optimization strategies."""

    with open(component_file_path, 'r') as f:
        content = f.read()

    # Check if already refactored
    if f"{component_name}OptimizationSimple" in content:
        print(f"  {component_name} already has separate optimization strategies")
        return False

    # Find the monolithic Optimization class
    opt_class_pattern = rf"class {component_name}Optimization\({base_class}\):.*?(?=\nclass |\n@register_component|\n# =====|\Z)"
    match = re.search(opt_class_pattern, content, re.DOTALL)

    if not match:
        print(f"  Could not find {component_name}Optimization class")
        return False

    old_class = match.group(0)

    # Extract the set_constraints method
    constraints_pattern = r"def set_constraints\(self\) -> list:.*?(?=\n    def |\n\nclass |\n# =====|\Z)"
    constraints_match = re.search(constraints_pattern, old_class, re.DOTALL)

    if not constraints_match:
        print(f"  Could not find set_constraints method in {component_name}Optimization")
        return False

    # Create new Simple and Standard classes
    new_classes = f'''class {component_name}OptimizationSimple({base_class}):
    """Implements the SIMPLE MILP optimization constraints for {component_name.lower()}.

    This is the baseline optimization strategy.
    """

    def __init__(self, params, component_instance):
        """Initialize with both params and component instance for constraint access."""
        super().__init__(params)
        self.component = component_instance

    def set_constraints(self) -> list:
        """
        Create SIMPLE CVXPY constraints for {component_name.lower()} optimization.

        Returns constraints for basic operation without enhancements.
        """
        constraints = []
        comp = self.component

        # TODO: Extract SIMPLE-only constraints from original implementation
        # For now, returning original constraints
        {constraints_match.group(0).replace("def set_constraints(self) -> list:", "").strip()}


class {component_name}OptimizationStandard({component_name}OptimizationSimple):
    """Implements the STANDARD MILP optimization constraints for {component_name.lower()}.

    Inherits from SIMPLE and adds STANDARD-specific enhancements.
    """

    def set_constraints(self) -> list:
        """
        Create STANDARD CVXPY constraints for {component_name.lower()} optimization.

        Adds STANDARD-specific enhancements to the constraints.
        """
        # For now, using same constraints as SIMPLE
        # TODO: Add STANDARD-specific enhancements
        return super().set_constraints()'''

    # Replace the old class with new classes
    content = content.replace(old_class, new_classes)

    # Update the factory method
    old_factory = rf'''def _get_optimization_strategy\(self\):.*?return {component_name}Optimization\(self\.params, self\)'''
    new_factory = f'''def _get_optimization_strategy(self):
        """Factory method: Select optimization strategy based on fidelity level."""
        fidelity = self.technical.fidelity_level

        if fidelity == FidelityLevel.SIMPLE:
            return {component_name}OptimizationSimple(self.params, self)
        elif fidelity == FidelityLevel.STANDARD:
            return {component_name}OptimizationStandard(self.params, self)
        elif fidelity == FidelityLevel.DETAILED:
            # For now, DETAILED uses STANDARD optimization (can be extended later)
            return {component_name}OptimizationStandard(self.params, self)
        elif fidelity == FidelityLevel.RESEARCH:
            # For now, RESEARCH uses STANDARD optimization (can be extended later)
            return {component_name}OptimizationStandard(self.params, self)
        else:
            raise ValueError(f"Unknown fidelity level for {component_name} optimization: {{fidelity}}")'''

    content = re.sub(old_factory, new_factory, content, flags=re.DOTALL)

    # Write back
    with open(component_file_path, 'w') as f:
        f.write(content)

    print(f"  ✅ Refactored {component_name}")
    return True


def main():
    """Main function to refactor all remaining components."""

    components_to_refactor = [
        ('energy/electric_boiler.py', 'ElectricBoiler', 'BaseConversionOptimization'),
        ('energy/heat_demand.py', 'HeatDemand', 'BaseDemandOptimization'),
        ('energy/grid.py', 'Grid', 'BaseTransmissionOptimization'),
        ('water/water_grid.py', 'WaterGrid', 'BaseTransmissionOptimization'),
        ('water/water_demand.py', 'WaterDemand', 'BaseDemandOptimization'),
        ('water/water_storage.py', 'WaterStorage', 'BaseStorageOptimization'),
        ('water/rainwater_source.py', 'RainwaterSource', 'BaseGenerationOptimization'),
    ]

    base_path = Path('/c/git/hive/apps/ecosystemiser/src/EcoSystemiser/system_model/components')

    print("Refactoring remaining components...")
    print("=" * 70)

    success_count = 0
    for rel_path, component_name, base_class in components_to_refactor:
        file_path = base_path / rel_path
        print(f"\nProcessing {component_name} ({rel_path})...")

        if file_path.exists():
            if refactor_component(file_path, component_name, base_class):
                success_count += 1
        else:
            print(f"  ⚠️ File not found: {file_path}")

    print("\n" + "=" * 70)
    print(f"Refactored {success_count}/{len(components_to_refactor)} components")


if __name__ == "__main__":
    main()