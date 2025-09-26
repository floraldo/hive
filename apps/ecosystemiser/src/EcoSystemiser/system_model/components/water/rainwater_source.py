"""Rainwater harvesting source component with MILP optimization support."""
import cvxpy as cp
import numpy as np
from pydantic import BaseModel, Field
from typing import Optional, List, Union
import logging

from ..shared.registry import register_component
from ..shared.component import Component

logger = logging.getLogger(__name__)


class RainwaterSourceParams(BaseModel):
    """Rainwater harvesting system parameters."""
    catchment_area_m2: float = Field(100.0, description="Roof/catchment area [m²]")
    runoff_coefficient: float = Field(0.85, description="Runoff coefficient (0-1)")
    first_flush_mm: float = Field(2.0, description="First flush diversion [mm]")
    collection_efficiency: float = Field(0.90, description="Collection system efficiency")
    filtration_efficiency: float = Field(0.95, description="Filtration efficiency")
    max_collection_rate_m3h: float = Field(5.0, description="Maximum collection rate [m³/h]")
    water_quality_index: float = Field(0.80, description="Rainwater quality index (0-1)")
    seasonal_factor: Optional[List[float]] = Field(None, description="Monthly rainfall factors")


@register_component("RainwaterSource")
class RainwaterSource(Component):
    """Rainwater harvesting source for sustainable water supply."""

    PARAMS_MODEL = RainwaterSourceParams

    def _post_init(self):
        """Initialize rainwater source-specific attributes after DRY parameter unpacking."""
        self.type = "generation"
        self.medium = "water"

        # Create default seasonal factors if not provided (temperate climate pattern)
        if not hasattr(self, 'seasonal_factor') or self.seasonal_factor is None:
            # Monthly factors: Jan-Dec (Northern Hemisphere temperate)
            self.seasonal_factor = [
                0.8, 0.9, 1.0, 1.2, 1.3, 1.1,  # Jan-Jun
                0.9, 0.8, 1.0, 1.1, 0.9, 0.8   # Jul-Dec
            ]

        # CVXPY variables (created later by add_optimization_vars)
        self.Q_collected = None     # Water collected at each timestep
        self.Q_available = None     # Water available for use
        self.Q_overflow = None      # Overflow water

        # For rule-based operation
        self.rainfall_profile = None  # mm/h rainfall data
        self.water_collected = np.zeros(self.N)
        self.water_available = np.zeros(self.N)

    def add_optimization_vars(self):
        """Create CVXPY optimization variables."""
        self.Q_collected = cp.Variable(self.N, name=f'{self.name}_collected', nonneg=True)
        self.Q_available = cp.Variable(self.N, name=f'{self.name}_available', nonneg=True)
        self.Q_overflow = cp.Variable(self.N, name=f'{self.name}_overflow', nonneg=True)

        # Add flows
        self.flows['output']['Q_available'] = {
            'type': 'water',
            'value': self.Q_available,
            'quality': self.water_quality_index
        }
        self.flows['source']['Q_collected'] = {
            'type': 'water',
            'value': self.Q_collected,
            'is_renewable': True
        }
        self.flows['sink']['Q_overflow'] = {
            'type': 'water',
            'value': self.Q_overflow
        }

    def set_constraints(self) -> List:
        """Set CVXPY constraints for rainwater collection."""
        constraints = []

        if self.Q_collected is not None and self.rainfall_profile is not None:
            for t in range(self.N):
                # Calculate potential collection based on rainfall
                rainfall_mm = self.rainfall_profile[t]

                # Account for first flush diversion
                effective_rainfall = max(0, rainfall_mm - self.first_flush_mm / 24)  # Hourly rate

                # Potential collection [m³/h]
                potential_collection = (
                    self.catchment_area_m2 *
                    effective_rainfall / 1000 *  # Convert mm to m
                    self.runoff_coefficient *
                    self.collection_efficiency
                )

                # Collection limited by system capacity
                constraints.append(
                    self.Q_collected[t] <= min(potential_collection,
                                              self.max_collection_rate_m3h)
                )

                # Available water after filtration
                constraints.append(
                    self.Q_available[t] == self.Q_collected[t] * self.filtration_efficiency
                )

                # Overflow if collection exceeds capacity
                if potential_collection > self.max_collection_rate_m3h:
                    constraints.append(
                        self.Q_overflow[t] == potential_collection - self.max_collection_rate_m3h
                    )

        return constraints

    def set_rainfall_profile(self, profile: Optional[Union[np.ndarray, List[float]]] = None):
        """Set or generate rainfall profile.

        Args:
            profile: Optional rainfall data [mm/h]. If None, generates synthetic profile.
        """
        if profile is not None:
            self.rainfall_profile = np.array(profile[:self.N])
        else:
            # Generate synthetic rainfall profile
            self.rainfall_profile = self.generate_synthetic_rainfall()

    def generate_synthetic_rainfall(self) -> np.ndarray:
        """Generate synthetic rainfall profile based on seasonal patterns.

        Returns:
            Hourly rainfall profile [mm/h]
        """
        rainfall = np.zeros(self.N)

        for t in range(self.N):
            hour_of_day = t % 24
            day_of_year = (t // 24) % 365
            month = min(11, day_of_year // 30)  # Approximate month

            # Base rainfall probability and intensity
            rainfall_prob = 0.1  # 10% chance of rain in any hour
            base_intensity = 2.0  # mm/h when raining

            # Apply seasonal factor
            seasonal_mult = self.seasonal_factor[month]

            # Simulate rainfall (stochastic in real implementation)
            # For deterministic testing, use a pattern
            if (t // 24) % 7 == 0:  # Rain every 7th day
                if 6 <= hour_of_day <= 18:  # Daytime rain
                    rainfall[t] = base_intensity * seasonal_mult * (0.5 + 0.5 * np.sin(hour_of_day / 24 * np.pi))

        return rainfall

    def rule_based_operation(self, t: int) -> float:
        """Rule-based rainwater collection.

        Args:
            t: Current timestep

        Returns:
            Water available from rainwater [m³/h]
        """
        if t >= self.N or self.rainfall_profile is None:
            return 0.0

        # Current rainfall
        rainfall_mm = self.rainfall_profile[t]

        # Account for first flush
        effective_rainfall = max(0, rainfall_mm - self.first_flush_mm / 24)

        # Calculate collection
        collected = (
            self.catchment_area_m2 *
            effective_rainfall / 1000 *
            self.runoff_coefficient *
            self.collection_efficiency
        )

        # Apply system capacity limit
        collected = min(collected, self.max_collection_rate_m3h)

        # Apply filtration
        available = collected * self.filtration_efficiency

        # Store results
        self.water_collected[t] = collected
        self.water_available[t] = available

        return available

    def get_total_collected(self) -> float:
        """Get total water collected.

        Returns:
            Total water collected [m³]
        """
        return float(np.sum(self.water_collected))

    def get_collection_efficiency_overall(self) -> float:
        """Calculate overall collection efficiency.

        Returns:
            Overall efficiency considering all losses (0-1)
        """
        return (self.runoff_coefficient *
                self.collection_efficiency *
                self.filtration_efficiency)

    def get_water_quality(self) -> float:
        """Get water quality index.

        Returns:
            Water quality index (0-1)
        """
        return self.water_quality_index

    def estimate_annual_yield(self, annual_rainfall_mm: float) -> float:
        """Estimate annual water yield.

        Args:
            annual_rainfall_mm: Annual rainfall [mm]

        Returns:
            Estimated annual yield [m³]
        """
        # Account for first flush losses
        effective_rainfall = max(0, annual_rainfall_mm - self.first_flush_mm * 365)

        return (self.catchment_area_m2 *
                effective_rainfall / 1000 *
                self.get_collection_efficiency_overall())

    def reset(self):
        """Reset component state."""
        self.water_collected[:] = 0
        self.water_available[:] = 0
        if self.rainfall_profile is None:
            self.set_rainfall_profile()

    def __repr__(self):
        """String representation."""
        return (f"RainwaterSource(name='{self.name}', "
                f"catchment_area={self.catchment_area_m2}m², "
                f"efficiency={self.get_collection_efficiency_overall():.1%})")