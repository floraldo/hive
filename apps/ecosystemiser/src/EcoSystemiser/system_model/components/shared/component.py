"""Base component class for all system components."""
import cvxpy as cp
import numpy as np
from typing import Dict, Any, Optional
from pydantic import BaseModel
from EcoSystemiser.system_model.components.economic_params import EconomicParamsModel
from EcoSystemiser.system_model.components.environmental_params import EnvironmentalParamsModel

class ComponentParams(BaseModel):
    """Base parameters for all components."""
    economic: Optional[EconomicParamsModel] = EconomicParamsModel()
    environmental: Optional[EnvironmentalParamsModel] = EnvironmentalParamsModel()

    class Config:
        extra = "allow"  # Allow additional fields for component-specific params

class Component:
    """Base class for all system components with enhanced parameter handling."""

    def __init__(self, name: str, params: BaseModel, n: int = 24):
        """Initialize component with automatic parameter extraction.

        Args:
            name: Component identifier
            params: Pydantic BaseModel containing all parameters
            n: Number of timesteps
        """
        self.name = name
        self.params = params  # Store full params object
        self.N = n

        # Component type and medium (override in subclasses)
        self.type = "base"
        self.medium = "electricity"

        # Flow dictionaries for system connections
        self.flows = {
            'input': {},
            'output': {},
            'source': {},
            'sink': {}
        }

        # Constraints list for optimization
        self.constraints = []

        # DRY PATTERN: Auto-unpack all Pydantic parameters as direct attributes
        # This eliminates repetitive self.param = params.param in every component
        for field_name, value in params.dict().items():
            if value is not None:
                setattr(self, field_name, value)

        # Make nested parameters directly accessible (for backwards compatibility)
        # This allows self.technical.P_max instead of self.params.technical.P_max
        self.technical = getattr(params, 'technical', None)
        self.economic = getattr(params, 'economic', None)
        self.environmental = getattr(params, 'environmental', None)

        # Profile placeholder (set by SystemBuilder if needed)
        self.profile = None

        # Call component-specific initialization
        self._post_init()

    def _post_init(self):
        """Component-specific initialization after parameter unpacking.

        Override this method in subclasses for component-specific setup.
        This is called automatically after parameter unpacking is complete.
        """
        pass

    def add_optimization_vars(self):
        """Placeholder for future cvxpy variable initialization.

        This method will be called by OptimizationSolver before solving.
        Subclasses can override to add their specific optimization variables.
        This supports future refactoring to separate cvxpy from component logic.
        """
        pass

    def set_constraints(self):
        """Define component constraints for optimization.

        Returns:
            List of cvxpy constraints

        Note:
            Override in subclasses to define component-specific constraints.
        """
        return []

    def get_state_at_timestep(self, t: int) -> Dict[str, float]:
        """Get component state at specific timestep.

        Args:
            t: Timestep index

        Returns:
            Dictionary with state information

        Note:
            Override in subclasses for component-specific state.
        """
        state = {
            'name': self.name,
            'type': self.type,
            'medium': self.medium
        }

        # Add profile value if available
        if self.profile is not None and t < len(self.profile):
            state['profile_value'] = float(self.profile[t])

        return state

    def validate_parameters(self) -> bool:
        """Validate component parameters.

        Returns:
            True if parameters are valid

        Note:
            The Pydantic model handles most validation, but subclasses
            can override for additional checks.
        """
        return True

    def print_info(self):
        """Print component information for debugging."""
        print(f"\n=== Component: {self.name} ===")
        print(f"Type: {self.type}")
        print(f"Medium: {self.medium}")

        if self.technical:
            print(f"Technical params: {self.technical}")
        if self.economic:
            print(f"Economic params: {self.economic}")
        if self.environmental:
            print(f"Environmental params: {self.environmental}")

    def __repr__(self):
        """String representation of component."""
        return f"{self.__class__.__name__}(name='{self.name}', type='{self.type}', medium='{self.medium}')"