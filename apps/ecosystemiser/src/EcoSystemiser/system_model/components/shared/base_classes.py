"""Strategy Pattern base classes for component physics and optimization."""

from abc import ABC, abstractmethod

from hive_logging import get_logger

logger = get_logger(__name__)

# =============================================================================
# STRATEGY PATTERN BASE CLASSES
# =============================================================================


class BaseStoragePhysics(ABC):
    """Abstract base class for storage physics strategies.

    This defines the interface contract that all storage physics implementations
    must follow. Each fidelity level implements this interface.

    The Strategy Pattern allows us to:
    - Encapsulate physics algorithms
    - Make fidelity levels interchangeable
    - Support easy testing and extension
    """

    def __init__(self, params):
        """Initialize physics strategy with component parameters."""
        self.params = params

    @abstractmethod
    def rule_based_update_state(
        self, t: int, E_old: float, charge_power: float, discharge_power: float
    ) -> float:
        """
        Calculate new energy state based on physics model.

        This is the core physics method that each strategy must implement.

        Args:
            t: Current timestep
            E_old: Energy level at start of timestep (kWh)
            charge_power: Total power charging this storage (kW)
            discharge_power: Total power discharging from this storage (kW)

        Returns:
            float: New energy level after physics update (kWh)
        """
        pass

    @abstractmethod
    def apply_bounds(self, energy_level: float) -> float:
        """
        Apply physical energy bounds (0 <= E <= E_max).

        This method is now abstract - each strategy must implement its own bounds logic.
        This maintains architectural gravity toward implementing logic in strategies, not base classes.

        Args:
            energy_level: Energy level to bound

        Returns:
            float: Bounded energy level
        """
        pass


class BaseStorageOptimization(ABC):
    """Abstract base class for storage optimization strategies.

    This defines the interface contract for MILP optimization implementations.
    Separates optimization logic from physics and data models.
    """

    def __init__(self, params):
        """Initialize optimization strategy with component parameters."""
        self.params = params

    @abstractmethod
    def set_constraints(self) -> list:
        """
        Create CVXPY constraints for this storage component.

        This is the core optimization method that each strategy must implement.
        Should return all constraints needed for MILP solver.

        Returns:
            list: CVXPY constraint objects
        """
        pass


class BaseGenerationPhysics(ABC):
    """Abstract base class for generation physics strategies.

    This defines the interface contract that all generation physics implementations
    must follow. Each fidelity level implements this interface.

    The Strategy Pattern allows us to:
    - Encapsulate generation algorithms
    - Make fidelity levels interchangeable
    - Support easy testing and extension
    """

    def __init__(self, params):
        """Initialize physics strategy with component parameters."""
        self.params = params

    @abstractmethod
    def rule_based_generate(self, t: int, profile_value: float) -> float:
        """
        Calculate generation output based on physics model.

        This is the core physics method that each strategy must implement.

        Args:
            t: Current timestep
            profile_value: Normalized profile value (0-1) for this timestep

        Returns:
            float: Actual generation output in kW
        """
        pass


class BaseGenerationOptimization(ABC):
    """Abstract base class for generation optimization strategies.

    This defines the interface contract for MILP optimization implementations.
    Separates optimization logic from physics and data models.
    """

    def __init__(self, params):
        """Initialize optimization strategy with component parameters."""
        self.params = params

    @abstractmethod
    def set_constraints(self) -> list:
        """
        Create CVXPY constraints for this generation component.

        This is the core optimization method that each strategy must implement.
        Should return all constraints needed for MILP solver.

        Returns:
            list: CVXPY constraint objects
        """
        pass


class BaseConversionPhysics(ABC):
    """Abstract base class for conversion physics strategies.

    This defines the interface contract that all conversion physics implementations
    must follow. Each fidelity level implements this interface.

    The Strategy Pattern allows us to:
    - Encapsulate conversion algorithms
    - Make fidelity levels interchangeable
    - Support easy testing and extension
    """

    def __init__(self, params):
        """Initialize physics strategy with component parameters."""
        self.params = params

    @abstractmethod
    def rule_based_conversion_capacity(
        self, t: int, from_medium: str, to_medium: str
    ) -> dict:
        """
        Calculate conversion capacities for the current timestep.

        This is a core physics method that each strategy must implement.

        Args:
            t: Current timestep
            from_medium: Input energy medium (e.g., 'electricity')
            to_medium: Output energy medium (e.g., 'heat')

        Returns:
            dict: {'max_input': float, 'max_output': float, 'efficiency': float}
        """
        pass

    @abstractmethod
    def rule_based_conversion_dispatch(
        self, t: int, requested_output: float, from_medium: str, to_medium: str
    ) -> dict:
        """
        Calculate actual input/output for a requested output.

        Args:
            t: Current timestep
            requested_output: Desired output power (kW)
            from_medium: Input energy medium
            to_medium: Output energy medium

        Returns:
            dict: {'input_required': float, 'output_delivered': float}
        """
        pass


class BaseConversionOptimization(ABC):
    """Abstract base class for conversion optimization strategies.

    This defines the interface contract for MILP optimization implementations.
    Separates optimization logic from physics and data models.
    """

    def __init__(self, params):
        """Initialize optimization strategy with component parameters."""
        self.params = params

    @abstractmethod
    def set_constraints(self) -> list:
        """
        Create CVXPY constraints for this conversion component.

        This is the core optimization method that each strategy must implement.
        Should return all constraints needed for MILP solver.

        Returns:
            list: CVXPY constraint objects
        """
        pass


class BaseDemandPhysics(ABC):
    """Abstract base class for demand physics strategies.

    This defines the interface contract that all demand physics implementations
    must follow. Each fidelity level implements this interface.

    The Strategy Pattern allows us to:
    - Encapsulate demand algorithms
    - Make fidelity levels interchangeable
    - Support easy testing and extension
    """

    def __init__(self, params):
        """Initialize physics strategy with component parameters."""
        self.params = params

    @abstractmethod
    def rule_based_demand(self, t: int, profile_value: float) -> float:
        """
        Calculate demand requirement based on physics model.

        This is the core physics method that each strategy must implement.

        Args:
            t: Current timestep
            profile_value: Normalized profile value (0-1) for this timestep

        Returns:
            float: Actual demand requirement in kW
        """
        pass


class BaseDemandOptimization(ABC):
    """Abstract base class for demand optimization strategies.

    This defines the interface contract for MILP optimization implementations.
    Separates optimization logic from physics and data models.
    """

    def __init__(self, params):
        """Initialize optimization strategy with component parameters."""
        self.params = params

    @abstractmethod
    def set_constraints(self) -> list:
        """
        Create CVXPY constraints for this demand component.

        This is the core optimization method that each strategy must implement.
        Should return all constraints needed for MILP solver.

        Returns:
            list: CVXPY constraint objects
        """
        pass
