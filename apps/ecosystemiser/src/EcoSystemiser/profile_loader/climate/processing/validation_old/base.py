"""Base classes and interfaces for climate data validation.

This module defines the core validation infrastructure for climate data quality control.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
import xarray as xr


@dataclass
class QCReport:
    """Quality control report"""

    source: str
    location: Tuple[float, float]
    time_range: Tuple[datetime, datetime]
    variable_coverage: Dict[str, float]  # variable -> coverage fraction
    validation_issues: List[str]
    warnings: List[str]
    metadata: Dict[str, any]
    passed: bool
    summary: str
    timestamp: datetime


class QCProfile(ABC):
    """Base class for source-specific QC profiles"""

    name: str
    description: str
    known_issues: List[str]
    recommended_variables: List[str]
    temporal_resolution_limits: Dict[str, str]  # variable -> minimum resolution
    spatial_accuracy: Optional[str] = None  # Description of spatial accuracy

    @abstractmethod
    def validate_source_specific(self, ds: xr.Dataset, report: QCReport) -> None:
        """Apply source-specific validation rules"""
        pass

    def get_adjusted_bounds(
        self, base_bounds: Dict[str, Tuple[float, float]]
    ) -> Dict[str, Tuple[float, float]]:
        """Get source-specific adjusted bounds"""
        # Default: return base bounds unchanged
        return base_bounds
