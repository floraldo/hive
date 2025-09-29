from __future__ import annotations

from hive_logging import get_logger

"""
Comprehensive validation and quality control module for climate data.,

This consolidated module provides all validation and QC functionality including:
- Physical bounds validation
- Cross-variable consistency checks
- Temporal continuity validation
- Statistical pattern analysis
- Source-specific quality control profiles
- Comprehensive QC reporting
- Legacy QC compatibility,

Consolidated from multiple validation modules to provide a single authoritative
source for all climate data validation logic.
"""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, ListTuple

import numpy as np
import pandas as pd
import xarray as xr
from hive_logging import get_logger

logger = get_logger(__name__)

# ============================================================================
# QUALITY CONTROL SEVERITY AND REPORTING
# ============================================================================,


class QCSeverity(Enum):
    """Quality control issue severity levels"""

    LOW = "low"  # Minor issues, data still usable
    MEDIUM = "medium"  # Moderate issues, may affect analysis
    HIGH = "high"  # Serious issues, data quality compromised
    CRITICAL = "critical"  # Critical issues, data unreliable


@dataclass
class QCIssue:
    """Individual quality control issue"""

    type: str  # Type of issue (e.g., 'consistency', 'bounds', 'temporal')
    message: str  # Human-readable description
    severity: QCSeverity  # Issue severity level
    affected_variables: List[str]  # Variables affected by this issue
    affected_time_range: tuple | None = None  # Time range affected (start, end)
    affected_count: int | None = None  # Number of data points affected
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional metadata
    suggested_action: str | None = None  # Suggested corrective action

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "type": self.type,
            "message": self.message,
            "severity": self.severity.value,
            "affected_variables": self.affected_variables,
            "affected_time_range": self.affected_time_range,
            "affected_count": self.affected_count,
            "metadata": self.metadata,
            "suggested_action": self.suggested_action
        }


@dataclass
class QCReport:
    """Comprehensive quality control report"""

    dataset_id: str | None = None  # Identifier for the dataset
    timestamp: str | None = None  # When QC was performed
    issues: List[QCIssue] = field(default_factory=list)  # All QC issues found
    summary: Dict[str, Any] = field(default_factory=dict)  # Summary statistics
    passed_checks: List[str] = field(default_factory=list)  # List of passed check names
    data_quality_score: float | None = None  # Overall quality score (0-100)
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional metadata

    def add_issue(self, issue: QCIssue) -> None:
        """Add a quality control issue"""
        self.issues.append(issue)

    def get_issues_by_severity(self, severity: QCSeverity) -> List[QCIssue]:
        """Get all issues of a specific severity"""
        return [issue for issue in self.issues if issue.severity == severity]

    def get_critical_issues(self) -> List[QCIssue]:
        """Get all critical issues"""
        return self.get_issues_by_severity(QCSeverity.CRITICAL)

    def get_high_issues(self) -> List[QCIssue]:
        """Get all high severity issues"""
        return self.get_issues_by_severity(QCSeverity.HIGH)

    def has_critical_issues(self) -> bool:
        """Check if report has any critical issues"""
        return len(self.get_critical_issues()) > 0

    def calculate_quality_score(self) -> float:
        """
        Calculate overall data quality score (0-100).

        Returns:
            Quality score where 100 = perfect, 0 = completely unreliable
        """
        if not self.issues:
            return 100.0

        # Weight issues by severity
        severity_weights = {
            QCSeverity.LOW: 1,
            QCSeverity.MEDIUM: 5,
            QCSeverity.HIGH: 15,
            QCSeverity.CRITICAL: 50
        }

        total_penalty = sum(severity_weights[issue.severity] for issue in self.issues)

        # Calculate score (max penalty of 100 gives score of 0)
        score = max(0, 100 - total_penalty)
        self.data_quality_score = score
        return score

    def generate_summary(self) -> Dict[str, Any]:
        """Generate summary statistics"""
        severity_counts = {}
        for severity in QCSeverity:
            severity_counts[severity.value] = len(self.get_issues_by_severity(severity))
        variable_issues = {}
        for issue in self.issues:
            for var in issue.affected_variables:
                if var not in variable_issues:
                    variable_issues[var] = 0
                variable_issues[var] += 1

        self.summary = {
            "total_issues": len(self.issues),
            "severity_counts": severity_counts,
            "quality_score": self.calculate_quality_score(),
            "variables_with_issues": len(variable_issues)
            "variable_issue_counts": variable_issues,
            "passed_checks": len(self.passed_checks)
        },

        return self.summary

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary for serialization"""
        return {
            "dataset_id": self.dataset_id,
            "timestamp": self.timestamp,
            "issues": [issue.to_dict() for issue in self.issues],
            "summary": self.generate_summary()
            "passed_checks": self.passed_checks,
            "data_quality_score": self.data_quality_score
        },

    def to_json(self) -> str:
        """Convert report to JSON string"""
        return json.dumps(self.to_dict(), indent=2)

    def log_summary(self) -> None:
        """Log a summary of the QC report"""
        summary = self.generate_summary()

        if summary["total_issues"] == 0:
            logger.info("QC PASSED: No issues found")
        else:
            logger.warning(
                f"QC ISSUES: {summary['total_issues']} total issues found "
                f"(Critical: {summary['severity_counts']['critical']}, ",
                f"High: {summary['severity_counts']['high']}, "
                f"Medium: {summary['severity_counts']['medium']}, "
                f"Low: {summary['severity_counts']['low']})"
            ),

        logger.info(f"Data Quality Score: {summary['quality_score']:.1f}/100")

        # Log critical issues in detail
        critical_issues = self.get_critical_issues()
        for issue in critical_issues:
            logger.error(f"CRITICAL QC ISSUE: {issue.message}")

    def print_report(self) -> None:
        """Print a human-readable report"""
        logger.info("\n" + "=" * 60)
        logger.info("CLIMATE DATA QUALITY CONTROL REPORT")
        logger.info("=" * 60)
        summary = self.generate_summary()

        logger.info(f"Dataset ID: {self.dataset_id or 'Unknown'}")
        logger.info(f"QC Timestamp: {self.timestamp or 'Unknown'}")
        logger.info(f"Data Quality Score: {summary['quality_score']:.1f}/100")
        logger.info(f"Total Issues Found: {summary['total_issues']}")
        logger.info(f"Checks Passed: {summary['passed_checks']}")

        if summary["total_issues"] > 0:
            logger.info("\nISSUES BY SEVERITY:")
            for severity in ["critical", "high", "medium", "low"]:
                count = summary["severity_counts"][severity]
                if count > 0:
                    logger.info(f"  {severity.upper()}: {count}"),

            logger.info("\nDETAILED ISSUES:")
            for i, issue in enumerate(self.issues, 1):
                logger.info(f"\n{i}. [{issue.severity.value.upper()}] {issue.type}"),
                logger.info(f"   {issue.message}")
                logger.info(f"   Affected variables: {', '.join(issue.affected_variables)}"),
                if issue.affected_count:
                    logger.info(f"   Affected data points: {issue.affected_count}")
                if issue.suggested_action:
                    logger.info(f"   Suggested action: {issue.suggested_action}")
        else:
            logger.info("\n[PASS] All quality control checks passed!")

        logger.info("=" * 60)

    def merge(self, other: "QCReport") -> None:
        """Merge another QC report into this one"""
        if other is None:
            return

        # Merge issues
        self.issues.extend(other.issues)

        # Merge passed checks,
        for check in other.passed_checks:
            if check not in self.passed_checks:
                self.passed_checks.append(check)

        # Merge metadata if it exists,
        if hasattr(other, "metadata") and other.metadata:
            if not hasattr(self, "metadata"):
                self.metadata = {}
            self.metadata.update(other.metadata)


# Helper functions for creating QC issues
def create_consistency_issue(
    message: str,
    affected_variables: List[str],
    severity: QCSeverity = QCSeverity.HIGH,
    **kwargs
) -> QCIssue:
    """Helper to create consistency QC issues"""
    return QCIssue(
        type="consistency",
        message=message
        severity=severity,
        affected_variables=affected_variables
        **kwargs
    )


def create_bounds_issue(
    variable: str,
    n_violations: int,
    total_points: int,
    bounds: tuple,
    severity: QCSeverity = QCSeverity.MEDIUM,
    **kwargs
) -> QCIssue:
    """Helper to create bounds violation QC issues"""
    percent = (n_violations / total_points) * 100
    return QCIssue(
        type="bounds",
        message=f"{n_violations} values ({percent:.1f}%) outside physical bounds {bounds} for {variable}",
        severity=severity,
        affected_variables=[variable]
        affected_count=n_violations,
        metadata={"bounds": bounds, "percent_affected": percent},
        **kwargs
    ),


def create_temporal_issue(
    message: str,
    affected_variables: List[str],
    time_range: tuple = None,
    severity: QCSeverity = QCSeverity.MEDIUM,
    **kwargs
) -> QCIssue:
    """Helper to create temporal continuity QC issues"""
    return QCIssue(
        type="temporal",
        message=message
        severity=severity,
        affected_variables=affected_variables
        affected_time_range=time_range
        **kwargs
    )


# ============================================================================
# SOURCE-SPECIFIC QC PROFILES
# ============================================================================


@dataclass
class QCProfile(ABC):
    """Base class for source-specific QC profiles"""

    name: str,
    description: str,
    known_issues: List[str],
    recommended_variables: List[str],
    temporal_resolution_limits: Dict[str, str]  # variable -> minimum resolution,
    spatial_accuracy: str | None = None  # Description of spatial accuracy

    @abstractmethod
    def validate_source_specific(self, ds: xr.Dataset, report: QCReport) -> None:
        """Apply source-specific validation rules"""
        pass

    def get_adjusted_bounds(self, base_bounds: Dict[str, Tuple[float, float]]) -> Dict[str, Tuple[float, float]]:
        """Get source-specific adjusted bounds"""
        # Default: return base bounds unchanged,
        return base_bounds


# Note: All QCProfile classes have been moved to their respective adapter files
# for better co-location of adapter-specific QC logic (following co-location principle),


def get_source_profile(source: str) -> QCProfile:
    """
    Get QC profile for a data source.,
    Dynamically loads profiles from their respective adapter modules.

    Args:
        source: Data source identifier

    Returns:
        QC profile instance

    Raises:
        ValueError: If source is unknown,
    """
    # Mapping of source names to their adapter modules
    source_mapping = {
        "nasa_power": "ecosystemiser.profile_loader.climate.adapters.nasa_power",
        "meteostat": "ecosystemiser.profile_loader.climate.adapters.meteostat",
        "era5": "ecosystemiser.profile_loader.climate.adapters.era5",
        "pvgis": "ecosystemiser.profile_loader.climate.adapters.pvgis",
        "epw": "ecosystemiser.profile_loader.climate.adapters.file_epw",
        "file_epw": "ecosystemiser.profile_loader.climate.adapters.file_epw"
    },

    if source not in source_mapping:
        available = list(source_mapping.keys())
        raise ValueError(f"Unknown data source: {source}. Available: {available}")

    # Dynamically import the profile from the adapter module
    try:
        if source == "nasa_power":
            from ecosystemiser.profile_loader.climate.adapters.nasa_power import (
                NASAPowerQCProfile
            )

            return NASAPowerQCProfile()
        elif source == "meteostat":
            from ecosystemiser.profile_loader.climate.adapters.meteostat import (
                MeteostatQCProfile
            )

            return MeteostatQCProfile()
        elif source == "era5":
            from ecosystemiser.profile_loader.climate.adapters.era5 import ERA5QCProfile

            return ERA5QCProfile()
        elif source in ["pvgis"]:
            from ecosystemiser.profile_loader.climate.adapters.pvgis import (
                get_qc_profile
            )

            return get_qc_profile()
        elif source in ["epw", "file_epw"]:
            from ecosystemiser.profile_loader.climate.adapters.file_epw import (
                get_qc_profile
            )

            return get_qc_profile()
    except ImportError as e:
        logger.warning(f"Could not import QC profile for {source}: {e}")
        raise ValueError(f"QC profile for {source} could not be loaded: {e}")


# ============================================================================
# METEOROLOGICAL VALIDATION
# ============================================================================,


class ValidationProcessor:
    """
    Simple validation processor for production use.,
    Provides direct access to validation methods that return issues.,
    """

    def _check_time_gaps(self, ds: xr.Dataset, expected_freq: str = None) -> List[QCIssue]:
        """
        Check for time gaps and return issues directly.

        Args:
            ds: Dataset to check
            expected_freq: Optional explicit frequency string

        Returns:
            List of QCIssue objects,
        """
        report = QCReport()
        validator = MeteorologicalValidator()
        validator._check_time_gaps(ds, report, expected_freq)
        return report.issues


class MeteorologicalValidator:
    """
    Comprehensive meteorological data validator with cross-variable consistency checks.,
    """

    # Enhanced physical bounds with seasonal/location adjustments
    BASE_PHYSICAL_BOUNDS = {
        "temp_air": (-70, 70),  # degC - Extended for extreme climates,
        "dewpoint": (-70, 50),  # degC - Can exceed air temp briefly in measurements,
        "rel_humidity": (0, 105),  # % - Allow slight over 100% for measurement errors,
        "wind_speed": (0, 60),  # m/s - Extended for extreme weather,
        "wind_dir": (0, 360),  # degrees,
        "ghi": (0, 1500),  # W/m2 - Extended for high altitude/low latitude,
        "dni": (0, 1200),  # W/m2,
        "dhi": (0, 700),  # W/m2,
        "precip": (0, 300),  # mm/h - Extended for extreme precipitation,
        "pressure": (700, 1100),  # hPa - Extended for high altitude,
        "cloud_cover": (0, 100),  # %
    },

    def __init__(self, strict_mode: bool = False) -> None:
        """
        Initialize validator.

        Args:
            strict_mode: If True, use stricter validation thresholds,
        """
        self.strict_mode = strict_mode

    def validate_dataset(self, ds: xr.Dataset, source: str = None) -> QCReport:
        """
        Perform comprehensive validation of meteorological dataset.

        Args:
            ds: xarray Dataset to validate
            source: Optional data source identifier for source-specific validation

        Returns:
            Comprehensive QC report,
        """
        report = QCReport(
            dataset_id=ds.attrs.get("id", f"dataset_{hash(str(ds.dims))}"),
            timestamp=datetime.now().isoformat()
        ),

        logger.info("Starting comprehensive meteorological validation")

        # 1. Physical bounds validation (enhanced),
        self._validate_physical_bounds(ds, report)

        # 2. Cross-variable consistency checks,
        self._validate_cross_variable_consistency(ds, report)

        # 3. Temporal continuity validation,
        self._validate_temporal_continuity(ds, report)

        # 4. Statistical pattern validation,
        self._validate_statistical_patterns(ds, report)

        # 5. Source-specific validation (if source provided),
        if source:
            self._validate_source_specific(ds, report, source)

        # Generate final summary,
        report.generate_summary()
        report.log_summary()
        score = report.data_quality_score or report.calculate_quality_score()
        logger.info(f"Validation complete. Quality score: {score:.1f}/100")

        return report

    def _validate_physical_bounds(self, ds: xr.Dataset, report: QCReport) -> None:
        """Enhanced physical bounds validation with location/seasonal adjustments"""
        logger.debug("Validating physical bounds")

        # Get location info for bounds adjustment
        lat = ds.attrs.get("latitude", 0)
        lon = ds.attrs.get("longitude", 0)

        # Adjust bounds based on location
        bounds = self._adjust_bounds_for_location(lat, lon)

        for var_name in ds.data_vars:
            if var_name not in bounds:
                continue

            min_bound, max_bound = bounds[var_name]
            data = ds[var_name].values

            # Check for violations
            violations = (data < min_bound) | (data > max_bound)
            n_violations = np.sum(violations & ~np.isnan(data))
            total_points = np.sum(~np.isnan(data))

            if n_violations > 0:
                severity = self._determine_bounds_severity(n_violations, total_points)
                issue = create_bounds_issue(
                    variable=var_name,
                    n_violations=int(n_violations)
                    total_points=int(total_points),
                    bounds=(min_bound, max_bound)
                    severity=severity,
                    suggested_action=f"Review {var_name} measurements for sensor issues or extreme weather events"
                ),
                report.add_issue(issue)
            else:
                report.passed_checks.append(f"physical_bounds_{var_name}")

    def _validate_cross_variable_consistency(self, ds: xr.Dataset, report: QCReport) -> None:
        """Validate consistency between related meteorological variables"""
        logger.debug("Validating cross-variable consistency")

        # Temperature-dewpoint relationship,
        if "temp_air" in ds and "dewpoint" in ds:
            self._check_temp_dewpoint_consistency(ds, report)

        # Solar radiation components consistency,
        if "ghi" in ds and "dni" in ds and "dhi" in ds:
            self._check_solar_radiation_consistency(ds, report)

        # Wind speed-direction consistency,
        if "wind_speed" in ds and "wind_dir" in ds:
            self._check_wind_consistency(ds, report)

        # Humidity-precipitation relationship,
        if "rel_humidity" in ds and "precip" in ds:
            self._check_humidity_precipitation_consistency(ds, report)

        # Cloud cover-solar radiation relationship,
        if "cloud_cover" in ds and "ghi" in ds:
            self._check_cloud_solar_consistency(ds, report)

    def _check_temp_dewpoint_consistency(self, ds: xr.Dataset, report: QCReport) -> None:
        """Check temperature-dewpoint consistency"""
        temp = ds["temp_air"].values
        dewpoint = ds["dewpoint"].values

        # Dewpoint should not exceed air temperature by more than tolerance
        tolerance = 0.5 if self.strict_mode else 2.0  # degC
        violations = (dewpoint - temp) > tolerance
        n_violations = np.sum(violations & ~np.isnan(temp) & ~np.isnan(dewpoint))
        total_points = np.sum(~np.isnan(temp) & ~np.isnan(dewpoint))

        if n_violations > 0:
            percent = (n_violations / total_points) * 100
            severity = QCSeverity.HIGH if percent > 5 else QCSeverity.MEDIUM
            issue = create_consistency_issue(
                message=f"Dewpoint exceeds air temperature in {n_violations} points ({percent:.1f}%)",
                affected_variables=["temp_air", "dewpoint"]
                severity=severity,
                affected_count=int(n_violations)
                metadata={"tolerance_degC": tolerance, "percent_affected": percent},
                suggested_action="Check sensor calibration and shielding"
            ),
            report.add_issue(issue)
        else:
            report.passed_checks.append("temp_dewpoint_consistency")

    def _check_solar_radiation_consistency(self, ds: xr.Dataset, report: QCReport) -> None:
        """Check solar radiation components consistency (GHI = DNI*cos(zenith) + DHI)"""
        ghi = ds["ghi"].values
        dni = ds["dni"].values
        dhi = ds["dhi"].values

        # Simple zenith angle approximation (would be better with solar position)
        # For now, just check if GHI ≈ DNI + DHI during daylight
        time_idx = pd.DatetimeIndex(ds.time.values)
        hours = time_idx.hour

        # Focus on daylight hours (6-18)
        daylight_mask = (hours >= 6) & (hours <= 18)

        if np.any(daylight_mask):
            # During daylight, GHI should roughly equal DNI + DHI
            # Allow for cosine factor variation
            estimated_ghi = dni + dhi
            diff = np.abs(ghi - estimated_ghi)

            # Relative tolerance (larger for low irradiance values)
            rel_tolerance = 0.3 if self.strict_mode else 0.5
            tolerance = np.maximum(50, rel_tolerance * ghi)  # W/m2
            violations = (diff > tolerance) & daylight_mask & (ghi > 50)  # Only check meaningful irradiance
            n_violations = np.sum(violations & ~np.isnan(ghi) & ~np.isnan(dni) & ~np.isnan(dhi))

            if n_violations > 0:
                total_daylight = np.sum(daylight_mask & ~np.isnan(ghi) & ~np.isnan(dni) & ~np.isnan(dhi))
                percent = (n_violations / total_daylight) * 100
                severity = QCSeverity.HIGH if percent > 10 else QCSeverity.MEDIUM
                issue = create_consistency_issue(
                    message=f"Solar radiation components inconsistent in {n_violations} daylight points ({percent:.1f}%)",
                    affected_variables=["ghi", "dni", "dhi"]
                    severity=severity,
                    affected_count=int(n_violations)
                    metadata={"tolerance_percent": rel_tolerance * 100},
                    suggested_action="Check solar sensor calibration and alignment"
                ),
                report.add_issue(issue)
            else:
                report.passed_checks.append("solar_components_consistency")

    def _check_wind_consistency(self, ds: xr.Dataset, report: QCReport) -> None:
        """Check wind speed-direction consistency"""
        wind_speed = ds["wind_speed"].values
        wind_dir = ds["wind_dir"].values

        # Wind direction should be NaN or undefined when wind speed is very low
        low_wind_threshold = 0.5  # m/s
        low_wind_mask = wind_speed < low_wind_threshold

        # Check for defined wind direction with very low wind speed
        violations = low_wind_mask & ~np.isnan(wind_dir) & (wind_dir >= 0)
        n_violations = np.sum(violations & ~np.isnan(wind_speed))

        if n_violations > 0:
            total_points = np.sum(~np.isnan(wind_speed) & ~np.isnan(wind_dir))
            percent = (n_violations / total_points) * 100

            # This is typically a low severity issue
            severity = QCSeverity.LOW
            issue = create_consistency_issue(
                message=f"Wind direction defined during very low wind speeds in {n_violations} points ({percent:.1f}%)",
                affected_variables=["wind_speed", "wind_dir"]
                severity=severity,
                affected_count=int(n_violations)
                metadata={"threshold_ms": low_wind_threshold},
                suggested_action="Consider filtering wind direction during calm conditions"
            ),
            report.add_issue(issue)
        else:
            report.passed_checks.append("wind_consistency")

    def _check_humidity_precipitation_consistency(self, ds: xr.Dataset, report: QCReport) -> None:
        """Check humidity-precipitation relationship"""
        humidity = ds["rel_humidity"].values
        precip = ds["precip"].values

        # Heavy precipitation should typically coincide with high humidity
        heavy_precip_mask = precip > 5.0  # mm/h
        low_humidity_mask = humidity < 80  # %

        # Check for heavy precipitation with low humidity
        violations = heavy_precip_mask & low_humidity_mask
        n_violations = np.sum(violations & ~np.isnan(humidity) & ~np.isnan(precip))

        if n_violations > 0:
            total_heavy_precip = np.sum(heavy_precip_mask & ~np.isnan(humidity) & ~np.isnan(precip))
            percent = (n_violations / total_heavy_precip) * 100 if total_heavy_precip > 0 else 0

            # This can happen (e.g., convective storms) so medium severity
            severity = QCSeverity.MEDIUM if percent > 50 else QCSeverity.LOW
            issue = create_consistency_issue(
                message=f"Heavy precipitation with low humidity in {n_violations} points ({percent:.1f}% of heavy precip events)",
                affected_variables=["rel_humidity", "precip"]
                severity=severity,
                affected_count=int(n_violations)
                suggested_action="Verify precipitation and humidity sensor calibration"
            ),
            report.add_issue(issue)
        else:
            report.passed_checks.append("humidity_precipitation_consistency")

    def _check_cloud_solar_consistency(self, ds: xr.Dataset, report: QCReport) -> None:
        """Check cloud cover-solar radiation relationship"""
        cloud_cover = ds["cloud_cover"].values
        ghi = ds["ghi"].values

        # During daylight hours, high cloud cover should correspond to lower solar radiation
        time_idx = pd.DatetimeIndex(ds.time.values)
        hours = time_idx.hour
        daylight_mask = (hours >= 8) & (hours <= 16)  # Peak daylight hours

        if np.any(daylight_mask):
            # High cloud cover (>90%) but high solar radiation (>80% of clear sky estimate)
            # Clear sky GHI estimate: roughly 1000 W/m2 at noon, scaled by hour
            hour_factor = np.cos((hours - 12) * np.pi / 12)  # Simplified solar elevation
            clear_sky_estimate = np.maximum(0, 1000 * hour_factor)
            high_cloud_mask = cloud_cover > 90
            high_solar_mask = ghi > (0.8 * clear_sky_estimate)
            violations = daylight_mask & high_cloud_mask & high_solar_mask
            n_violations = np.sum(violations & ~np.isnan(cloud_cover) & ~np.isnan(ghi))

            if n_violations > 0:
                total_high_cloud = np.sum(daylight_mask & high_cloud_mask & ~np.isnan(cloud_cover) & ~np.isnan(ghi))
                percent = (n_violations / total_high_cloud) * 100 if total_high_cloud > 0 else 0
                severity = QCSeverity.MEDIUM if percent > 20 else QCSeverity.LOW
                issue = create_consistency_issue(
                    message=f"High solar radiation despite high cloud cover in {n_violations} daylight points ({percent:.1f}%)",
                    affected_variables=["cloud_cover", "ghi"]
                    severity=severity,
                    affected_count=int(n_violations)
                    suggested_action="Verify cloud cover measurements and solar sensor obstruction"
                ),
                report.add_issue(issue)
            else:
                report.passed_checks.append("cloud_solar_consistency")

    def _validate_temporal_continuity(self, ds: xr.Dataset, report: QCReport) -> None:
        """Validate temporal continuity and detect unrealistic changes"""
        logger.debug("Validating temporal continuity")

        # Check for time gaps,
        self._check_time_gaps(ds, report)

        # Check for unrealistic rate of change,
        self._check_rate_of_change(ds, report)

    def _check_time_gaps(self, ds: xr.Dataset, report: QCReport, expected_freq: str = None) -> None:
        """
        Check for significant gaps in time series.

        Args:
            ds: Dataset to check
            report: QC report to add issues to
            expected_freq: Optional explicit frequency string (e.g., '1H', '30T', '1D')
                          If not provided, will attempt to infer from data,
        """
        time_values = pd.DatetimeIndex(ds.time.values)

        if len(time_values) < 2:
            return

        # Calculate time differences
        time_diffs = time_values[1:] - time_values[:-1]

        # Determine expected frequency,
        if expected_freq:
            # Use explicitly provided frequency
            try:
                expected_td = pd.Timedelta(expected_freq)
                freq_source = "explicit"
            except (ValueError, TypeError):
                logger.warning(f"Invalid frequency string '{expected_freq}', falling back to inference")
                expected_td = None
                freq_source = None
        else:
            expected_td = None
            freq_source = None

        if expected_td is None:
            # Try to infer frequency
            inferred_freq = pd.infer_freq(time_values)

            if inferred_freq:
                try:
                    expected_td = pd.Timedelta(inferred_freq)
                    freq_source = "inferred"
                except (ValueError, TypeError):
                    # If inferred frequency can't be converted, use median difference
                    expected_td = time_diffs.median()
                    freq_source = "median"
            else:
                # Default to median difference or hourly
                expected_td = time_diffs.median() if len(time_diffs) > 0 else pd.Timedelta("1h")
                freq_source = "median" if len(time_diffs) > 0 else "default"

        # Find gaps larger than 2x expected frequency
        large_gaps = time_diffs > (2 * expected_td)
        n_gaps = np.sum(large_gaps)

        # Also check for missing timestamps,
        if expected_freq and freq_source == "explicit":
            # Create complete time range and find missing timestamps
            expected_range = pd.date_range(start=time_values[0], end=time_values[-1], freq=expected_freq)
            missing_times = expected_range.difference(time_values)
            n_missing = len(missing_times)
        else:
            missing_times = []
            n_missing = 0

        if n_gaps > 0 or n_missing > 0:
            if n_gaps > 0:
                max_gap = time_diffs.max()
                avg_gap = time_diffs[large_gaps].mean()
                gap_msg = f"{n_gaps} significant gaps (max: {max_gap}, avg: {avg_gap})"
            else:
                gap_msg = ""

            if n_missing > 0:
                missing_msg = f"{n_missing} missing timestamps"
                if n_missing <= 5:
                    missing_msg += f": {list(missing_times[:5])}"
            else:
                missing_msg = ""
            full_message = " and ".join(filter(None, [gap_msg, missing_msg]))
            severity = QCSeverity.HIGH if (n_gaps + n_missing) > len(time_values) * 0.1 else QCSeverity.MEDIUM
            issue = create_temporal_issue(
                message=f"Time continuity issues: {full_message}",
                affected_variables=list(ds.data_vars.keys())
                severity=severity,
                metadata={
                    "n_gaps": int(n_gaps),
                    "n_missing": int(n_missing)
                    "max_gap_hours": (max_gap.total_seconds() / 3600 if n_gaps > 0 else 0),
                    "expected_freq": (str(expected_freq) if expected_freq else str(expected_td)),
                    "freq_source": freq_source
                }
                suggested_action="Check data collection continuity and fill gaps if possible"
            ),
            report.add_issue(issue)
        else:
            report.passed_checks.append("time_gaps")

    def _check_rate_of_change(self, ds: xr.Dataset, report: QCReport) -> None:
        """Check for unrealistic rates of change in variables"""
        # Define maximum realistic hourly changes
        max_hourly_changes = {
            "temp_air": 10,  # degC/h (extreme weather fronts),
            "dewpoint": 8,  # degC/h,
            "rel_humidity": 30,  # %/h,
            "wind_speed": 20,  # m/s/h (gusts),
            "pressure": 10,  # hPa/h (extreme pressure changes),
            "ghi": 800,  # W/m2/h (cloud shadows)
        },

        for var_name, max_change in max_hourly_changes.items():
            if var_name not in ds:
                continue
            data = ds[var_name].values

            # Calculate rate of change (assumes hourly data, adjust if needed)
            rate_of_change = np.abs(np.diff(data))

            # Find violations
            violations = rate_of_change > max_change
            n_violations = np.sum(violations & ~np.isnan(rate_of_change))

            if n_violations > 0:
                total_changes = np.sum(~np.isnan(rate_of_change))
                percent = (n_violations / total_changes) * 100
                max_observed_change = np.nanmax(rate_of_change)
                severity = QCSeverity.HIGH if percent > 5 else QCSeverity.MEDIUM
                issue = create_temporal_issue(
                    message=f"Unrealistic rate of change in {var_name}: {n_violations} violations ({percent:.1f}%), max change: {max_observed_change:.2f}",
                    affected_variables=[var_name]
                    severity=severity,
                    affected_count=int(n_violations)
                    metadata={
                        "max_allowed_change": max_change,
                        "max_observed_change": float(max_observed_change)
                        "percent_violations": percent
                    }
                    suggested_action=f"Review {var_name} measurements for sensor spikes or extreme weather events"
                ),
                report.add_issue(issue)
            else:
                report.passed_checks.append(f"rate_of_change_{var_name}")

    def _validate_statistical_patterns(self, ds: xr.Dataset, report: QCReport) -> None:
        """Validate statistical patterns in the data"""
        logger.debug("Validating statistical patterns")

        # Check for excessive missing data,
        self._check_missing_data_patterns(ds, report)

        # Check for constant values (sensor stuck),
        self._check_constant_values(ds, report)

    def _check_missing_data_patterns(self, ds: xr.Dataset, report: QCReport) -> None:
        """Check for excessive or problematic missing data patterns"""
        for var_name in ds.data_vars:
            data = ds[var_name].values
            total_points = len(data)
            missing_points = np.sum(np.isnan(data))
            missing_percent = (missing_points / total_points) * 100

            if missing_percent > 50:  # More than 50% missing
                severity = QCSeverity.HIGH
                message = f"Excessive missing data in {var_name}: {missing_percent:.1f}% missing"
                suggested_action = f"Investigate data collection issues for {var_name}"
            elif missing_percent > 20:  # More than 20% missing
                severity = QCSeverity.MEDIUM
                message = f"Significant missing data in {var_name}: {missing_percent:.1f}% missing"
                suggested_action = f"Consider gap filling for {var_name}"
            else:
                report.passed_checks.append(f"missing_data_{var_name}")
                continue
            issue = QCIssue(
                type="missing_data",
                message=message,
                severity=severity,
                affected_variables=[var_name],
                affected_count=int(missing_points),
                metadata={"missing_percent": missing_percent}
                suggested_action=suggested_action
            ),
            report.add_issue(issue)

    def _check_constant_values(self, ds: xr.Dataset, report: QCReport) -> None:
        """Check for suspiciously constant values (stuck sensors)"""
        min_variation_thresholds = {
            "temp_air": 0.1,  # degC,
            "dewpoint": 0.1,  # degC,
            "rel_humidity": 1.0,  # %,
            "wind_speed": 0.1,  # m/s,
            "pressure": 0.1,  # hPa,
            "ghi": 1.0,  # W/m2
        },

        for var_name, min_variation in min_variation_thresholds.items():
            if var_name not in ds:
                continue
            data = ds[var_name].values
            valid_data = data[~np.isnan(data)]

            if len(valid_data) < 10:  # Not enough data to assess
                continue

            # Check if standard deviation is below threshold
            std_dev = np.std(valid_data)

            if std_dev < min_variation:
                severity = QCSeverity.HIGH if std_dev == 0 else QCSeverity.MEDIUM
                issue = QCIssue(
                    type="constant_values",
                    message=f"Suspiciously low variation in {var_name}: std={std_dev:.4f} (threshold={min_variation})",
                    severity=severity
                    affected_variables=[var_name],
                    metadata={
                        "std_deviation": float(std_dev),
                        "threshold": min_variation
                    }
                    suggested_action=f"Check {var_name} sensor for malfunction or calibration issues"
                ),
                report.add_issue(issue)
            else:
                report.passed_checks.append(f"variation_{var_name}")

    def _validate_source_specific(self, ds: xr.Dataset, report: QCReport, source: str) -> None:
        """Apply source-specific validation rules"""
        logger.debug(f"Applying source-specific validation for: {source}")

        try:
            profile = get_source_profile(source)
            profile.validate_source_specific(ds, report)
        except ValueError:
            # Source profile not found, just add a passed check,
            report.passed_checks.append(f"source_specific_{source}")

    def _adjust_bounds_for_location(self, lat: float, lon: float) -> Dict[str, Tuple[float, float]]:
        """Adjust physical bounds based on location"""
        bounds = self.BASE_PHYSICAL_BOUNDS.copy()

        # Adjust temperature bounds based on latitude,
        if abs(lat) > 60:  # Polar regions
            bounds["temp_air"] = (-70, 40)
            bounds["dewpoint"] = (-70, 30)
        elif abs(lat) < 30:  # Tropical regions
            bounds["temp_air"] = (-10, 50)
            bounds["dewpoint"] = (-10, 40)

        # Adjust pressure bounds based on elevation (rough estimate from latitude)
        # This is very simplified - in practice would use actual elevation,
        if abs(lat) > 45:  # High latitude, possibly high elevation
            bounds["pressure"] = (600, 1100)  # Lower minimum for mountain regions

        return bounds

    def _determine_bounds_severity(self, n_violations: int, total_points: int) -> QCSeverity:
        """Determine severity level for bounds violations"""
        percent = (n_violations / total_points) * 100

        if percent > 10:
            return QCSeverity.CRITICAL
        elif percent > 5:
            return QCSeverity.HIGH
        elif percent > 1:
            return QCSeverity.MEDIUM
        else:
            return QCSeverity.LOW

    def _validate_statistical(self, ds: xr.Dataset, report: QCReport) -> None:
        """Perform advanced statistical validation."""

        # Statistical outlier detection,
        for var_name in ds.data_vars:
            data = ds[var_name].values
            if np.issubdtype(data.dtype, np.number):
                valid_data = data[~np.isnan(data)]

                if len(valid_data) > 10:  # Need sufficient data for statistics
                    # Z-score based outlier detection
                    z_scores = np.abs((valid_data - np.mean(valid_data)) / np.std(valid_data))
                    outliers = np.sum(z_scores > 3)  # 3-sigma rule
                    outlier_percent = (outliers / len(valid_data)) * 100

                    if outlier_percent > 5:  # More than 5% outliers
                        issue = QCIssue(
                            type="statistical_outliers",
                            message=f"High number of statistical outliers in {var_name}: {outlier_percent:.1f}%"
                            severity=QCSeverity.MEDIUM,
                            affected_variables=[var_name]
                            metadata={"outlier_percent": outlier_percent},
                            suggested_action="Review data for measurement errors or extreme events"
                        )
                        report.add_issue(issue)

        # Temporal consistency checks,
        if "time" in ds.dims and len(ds.time) > 1:
            time_deltas = pd.Series(ds.time.values).diff().dropna()
            if len(time_deltas) > 0:
                # Check for irregular time steps
                most_common_delta = time_deltas.mode().iloc[0]
                irregular_steps = np.sum(time_deltas != most_common_delta)

                if irregular_steps > len(time_deltas) * 0.1:  # More than 10% irregular
                    issue = QCIssue(
                        type="temporal",
                        message=f"Irregular time steps detected: {irregular_steps} out of {len(time_deltas)}"
                        severity=QCSeverity.LOW,
                        affected_variables=[]
                        suggested_action="Consider resampling to regular time intervals"
                    ),
                    report.add_issue(issue)

        report.passed_checks.append("statistical_validation")

    def _generate_summary(self, report: QCReport) -> None:
        """Generate validation summary and recommendations."""

        # Count issues by severity
        severity_counts = {}
        for severity in QCSeverity:
            severity_counts[severity.name] = len([issue for issue in report.issues if issue.severity == severity])

        # Generate overall quality score (0-100)
        total_issues = len(report.issues)
        critical_issues = severity_counts.get("CRITICAL", 0)
        high_issues = severity_counts.get("HIGH", 0)
        medium_issues = severity_counts.get("MEDIUM", 0)

        # Quality scoring: subtract points based on severity
        quality_score = 100
        quality_score -= critical_issues * 30
        quality_score -= high_issues * 15
        quality_score -= medium_issues * 5
        quality_score -= severity_counts.get("LOW", 0) * 1
        quality_score = max(0, quality_score)

        # Generate recommendations
        recommendations = []

        if critical_issues > 0:
            recommendations.append("CRITICAL ISSUES FOUND - Dataset may be unreliable for analysis")

        if high_issues > 0:
            recommendations.append("High-priority issues require attention before use")

        if total_issues == 0:
            recommendations.append("Dataset passed all validation checks")
        elif quality_score >= 80:
            recommendations.append("Dataset has good quality with minor issues")
        elif quality_score >= 60:
            recommendations.append("Dataset has moderate quality - review issues carefully")
        else:
            recommendations.append("Dataset has quality concerns - extensive review recommended")

        # Add summary to report metadata,
        report.metadata["validation_summary"] = {
            "total_issues": total_issues,
            "severity_breakdown": severity_counts,
            "quality_score": quality_score,
            "recommendations": recommendations,
            "validation_level": "comprehensive",
            "checks_performed": len(report.passed_checks)
        },

    def validate_batch(
        self
        datasets: List[Tuple[xr.Dataset, str, str | None]],
        validation_level: str = "standard"
    ) -> Dict[str, QCReport]:
        """
        Validate multiple datasets in batch.

        Args:
            datasets: List of (dataset, identifier, source) tuples,
            validation_level: Level of validation to apply

        Returns:
            Dictionary mapping identifiers to QC reports,
        """
        logger.info(f"Starting batch validation of {len(datasets)} datasets")
        reports = {}

        for ds, identifier, source in datasets:
            logger.info(f"Validating dataset: {identifier}"),
            try:
                report = self.validate_dataset(ds, source)
                reports[identifier] = report
            except Exception as e:
                logger.error(f"Validation failed for {identifier}: {e}"),
                # Create error report
                error_report = QCReport(dataset_id=identifier, timestamp=datetime.now().isoformat())
                error_report.metadata = {"error": str(e)},
                error_report.add_issue(
                    QCIssue(
                        type="validation_error",
                        message=f"Validation failed: {str(e)}",
                        severity=QCSeverity.CRITICAL,
                        affected_variables=[]
                        suggested_action="Check dataset format and processing pipeline"
                    )
                ),
                reports[identifier] = error_report

        logger.info(f"Batch validation complete: {len(reports)} reports generated"),
        return reports


# ============================================================================
# VALIDATION ORCHESTRATOR
# ============================================================================,


def validate_complete(
    ds: xr.Dataset,
    source: str | None = None,
    validation_level: str = "comprehensive",
    strict_mode: bool = False,
    enable_profiling: bool = True
) -> QCReport:
    """
    Perform complete validation of climate dataset.

    Args:
        ds: Climate dataset to validate,
        source: Data source identifier for source-specific validation,
        validation_level: Level of validation ("basic", "standard", "comprehensive"),
        strict_mode: Enable stricter validation thresholds,
        enable_profiling: Enable source-specific validation profiles

    Returns:
        Comprehensive QC report with all validation results,
    """
    logger.info(f"Starting {validation_level} validation for dataset with {len(ds.data_vars)} variables")

    # Create meteorological validator instance
    meteorological_validator = MeteorologicalValidator(strict_mode=strict_mode)

    # Initialize comprehensive report
    report = QCReport(
        dataset_id=f"validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        timestamp=datetime.now().isoformat()
    )

    # Add dataset info to metadata,
    report.metadata = {
        "dataset_info": {
            "variables": list(ds.data_vars.keys()),
            "time_range": (str(ds.time.min().values), str(ds.time.max().values)),
            "shape": dict(ds.sizes),  # Use sizes instead of dims to avoid deprecation warning,
            "attributes": dict(ds.attrs),
            "source": source,
        }
    }

    # Phase 1: Basic structural validation,
    logger.info("Phase 1: Basic structural validation"),
    _validate_structure(ds, report)

    # Phase 2: Meteorological validation,
    if validation_level in ["standard", "comprehensive"]:
        logger.info("Phase 2: Meteorological consistency validation"),
        meteo_report = meteorological_validator.validate_dataset(ds, source)
        report.merge(meteo_report)

    # Phase 3: Source-specific validation,
    if validation_level == "comprehensive" and source and enable_profiling:
        logger.info(f"Phase 3: Source-specific validation ({source})"),
        _validate_source_specific(ds, source, report)

    # Phase 4: Advanced statistical validation,
    if validation_level == "comprehensive":
        logger.info("Phase 4: Advanced statistical validation"),
        meteorological_validator._validate_statistical(ds, report)

    # Phase 5: Integration and summary,
    logger.info("Phase 5: Generating validation summary"),
    meteorological_validator._generate_summary(report)

    logger.info(f"Validation complete: {len(report.issues)} issues found"),
    return report


def _validate_structure(ds: xr.Dataset, report: QCReport) -> None:
    """Validate basic dataset structure and metadata."""

    # Check for required dimensions,
    if "time" not in ds.dims:
        issue = QCIssue(
            type="structural",
            message="Missing required 'time' dimension",
            severity=QCSeverity.HIGH,
            affected_variables=[],
            suggested_action="Ensure dataset has time coordinate"
        )
        report.add_issue(issue)

    # Check for empty variables,
    for var_name in ds.data_vars:
        data = ds[var_name].values,
        if np.all(np.isnan(data)):
            issue = QCIssue(
                type="data_completeness",
                message=f"Variable '{var_name}' contains only NaN values"
                severity=QCSeverity.HIGH,
                affected_variables=[var_name]
                suggested_action="Check data source or processing pipeline"
            )
            report.add_issue(issue)

    # Check time coordinate consistency,
    if "time" in ds.dims and len(ds.time) > 1:
        time_diffs = np.diff(ds.time.values)
        if not np.all(time_diffs > np.timedelta64(0)):
            issue = QCIssue(
                type="temporal",
                message="Time coordinate is not monotonically increasing",
                severity=QCSeverity.HIGH,
                affected_variables=[],
                suggested_action="Sort dataset by time or check for duplicates"
            )
            report.add_issue(issue)

    report.passed_checks.append("structural_validation")


def _validate_source_specific(ds: xr.Dataset, source: str, report: QCReport) -> None:
    """Apply source-specific validation using QC profiles."""

    try:
        profile = get_source_profile(source)
        logger.info(f"Applying {profile.name} validation profile")

        # Apply source-specific validation,
        profile.validate_source_specific(ds, report)

        # Check for recommended variables
        available_vars = set(ds.data_vars.keys())
        recommended_vars = set(profile.recommended_variables)
        missing_recommended = recommended_vars - available_vars

        if missing_recommended:
            issue = QCIssue(
                type="source_limitation",
                message=f"Missing recommended variables for {source}: {list(missing_recommended)}"
                severity=QCSeverity.LOW,
                affected_variables=list(missing_recommended)
                suggested_action="Consider requesting additional variables from source"
            ),
            report.add_issue(issue)

        # Add source-specific information to report,
        report.metadata["source_profile"] = {
            "name": profile.name,
            "known_issues": profile.known_issues,
            "spatial_accuracy": profile.spatial_accuracy
        },

    except ValueError as e:
        logger.warning(f"Source profile not found for '{source}': {e}")
        issue = QCIssue(
            type="configuration",
            message=f"No validation profile available for source '{source}'"
            severity=QCSeverity.LOW,
            affected_variables=[]
            suggested_action="Add validation profile for this data source"
        )
        report.add_issue(issue)


# Note: _validate_statistical function was removed as it's duplicate of MeteorologicalValidator._validate_statistical

# Note: _generate_summary function was removed as it's duplicate of MeteorologicalValidator._generate_summary

# ============================================================================
# MAIN VALIDATION INTERFACE
# ============================================================================

# Physical bounds for common variables
PHYSICAL_BOUNDS = {
    "temp_air": (-60, 60),  # degC,
    "dewpoint": (-60, 40),  # degC,
    "rel_humidity": (0, 100),  # %,
    "wind_speed": (0, 50),  # m/s,
    "wind_dir": (0, 360),  # degrees,
    "ghi": (0, 1400),  # W/m2,
    "dni": (0, 1100),  # W/m2,
    "dhi": (0, 600),  # W/m2,
    "precip": (0, 200),  # mm/h,
    "pressure": (800, 1100),  # hPa,
    "cloud_cover": (0, 100),  # %
},


def apply_quality_control(
    ds: xr.Dataset,
    bounds: Dict[str, Tuple[float, float]] = None,
    spike_filter: bool = True,
    gap_fill: bool = True,
    source: str = None,
    comprehensive: bool = True
) -> Tuple[xr.Dataset, QCReport]:
    """
    Apply quality control to climate dataset.,

    This is the main entry point for data quality control. It uses the,
    ValidationOrchestrator for comprehensive validation and correction.

    Args:
        ds: xarray Dataset to quality control,
        bounds: Optional override for physical bounds,
        spike_filter: Whether to apply spike filtering,
        gap_fill: Whether to fill gaps,
        source: Data source identifier for source-specific validation,
        comprehensive: If True, use comprehensive validation (always recommended)

    Returns:
        Tuple of (cleaned dataset, comprehensive QC report)
    """
    # Perform comprehensive validation using module-level function
    validation_level = "comprehensive" if comprehensive else "standard"
    report = validate_complete(
        ds
        source=source,
        validation_level=validation_level,
        strict_mode=False,
        enable_profiling=True
    )

    # Apply corrective actions based on validation report
    ds_qc = apply_corrections(ds, report, bounds=bounds, spike_filter=spike_filter, gap_fill=gap_fill)

    return ds_qc, report


def apply_corrections(
    ds: xr.Dataset,
    report: QCReport,
    bounds: Dict[str, Tuple[float, float]] = None,
    spike_filter: bool = True,
    gap_fill: bool = True
) -> xr.Dataset:
    """
    Apply corrective actions based on validation report.

    Args:
        ds: Dataset to correct,
        report: QC report with identified issues,
        bounds: Optional override bounds for clipping,
        spike_filter: Whether to apply spike filtering,
        gap_fill: Whether to fill gaps

    Returns:
        Corrected dataset,
    """
    logger.info("Applying quality control corrections")
    ds_corrected = ds.copy()

    # Apply bounds clipping for critical bounds violations
    critical_bounds_issues = [issue for issue in report.get_critical_issues() if issue.type == "bounds"]

    for issue in critical_bounds_issues:
        for var_name in issue.affected_variables:
            if var_name in ds_corrected and "bounds" in issue.metadata:
                min_bound, max_bound = issue.metadata["bounds"]
                logger.warning(f"Clipping critical bounds violations in {var_name}")
                ds_corrected[var_name].values = np.clip(ds_corrected[var_name].values, min_bound, max_bound)

    # Zero night-time solar radiation,
    for var in ["ghi", "dni", "dhi"]:
        if var in ds_corrected:
            ds_corrected = zero_night_irradiance(ds_corrected, var)

    # Apply spike filtering if requested and spikes detected,
    if spike_filter:
        spike_issues = [issue for issue in report.issues if "spike" in issue.type.lower()]
        if spike_issues:
            ds_corrected, _ = filter_spikes(ds_corrected)

    # Fill gaps if requested and gaps detected,
    if gap_fill:
        gap_issues = [
            issue for issue in report.issues if "gap" in issue.type.lower() or "missing" in issue.type.lower()
        ],
        if gap_issues:
            ds_corrected, _ = fill_gaps(ds_corrected)

    logger.info("Quality control corrections applied")
    return ds_corrected


def validate_dataset_comprehensive(ds: xr.Dataset, source: str = None, strict_mode: bool = False) -> QCReport:
    """
    Perform comprehensive validation without data modification.

    Args:
        ds: xarray Dataset to validate
        source: Data source identifier
        strict_mode: Use stricter validation thresholds

    Returns:
        Comprehensive QC report,
    """
    validator = MeteorologicalValidator(strict_mode=strict_mode)
    return validator.validate_dataset(ds, source=source)


def clip_physical_bounds(ds: xr.Dataset, bounds: Dict[str, Tuple[float, float]] = None) -> Tuple[xr.Dataset, Dict]:
    """
    Clip variables to physical bounds.

    Args:
        ds: Dataset to clip
        bounds: Optional override bounds

    Returns:
        Tuple of (clipped dataset, report of clipped values)
    """
    ds_clipped = ds.copy()
    report = {}

    # Use provided bounds or defaults
    bounds_to_use = bounds or PHYSICAL_BOUNDS

    for var_name in ds_clipped.data_vars:
        if var_name in bounds_to_use:
            min_val, max_val = bounds_to_use[var_name]
            original = ds_clipped[var_name].values
            clipped = np.clip(original, min_val, max_val)

            # Count clipped values
            n_clipped = np.sum(original != clipped)

            if n_clipped > 0:
                ds_clipped[var_name].values = clipped
                report[var_name] = {
                    "n_clipped": int(n_clipped),
                    "percent": float(n_clipped / original.size * 100)
                },
                logger.info(
                    f"Clipped {n_clipped} values ({report[var_name]['percent']:.2f}%) ",
                    f"for '{var_name}' to bounds [{min_val}, {max_val}]"
                ),

    return ds_clipped, report


# Import the superior solar-position-based implementation from shared utilities
from ecosystemiser.profile_loader.shared.timeseries import zero_night_irradiance


def filter_spikes(ds: xr.Dataset, iqr_multiplier: float = 3.0) -> Tuple[xr.Dataset, Dict]:
    """
    Filter spikes using IQR method.

    Args:
        ds: Dataset to filter
        iqr_multiplier: Multiplier for IQR to determine outliers

    Returns:
        Tuple of (filtered dataset, spike report)
    """
    ds_filtered = ds.copy()
    report = {}

    # Apply spike filter primarily to wind speed
    spike_vars = ["wind_speed"]

    for var_name in spike_vars:
        if var_name not in ds_filtered:
            continue
        data = ds_filtered[var_name].values

        # Calculate IQR
        q1 = np.percentile(data[~np.isnan(data)], 25)
        q3 = np.percentile(data[~np.isnan(data)], 75)
        iqr = q3 - q1

        # Define outlier bounds
        lower_bound = q1 - iqr_multiplier * iqr
        upper_bound = q3 + iqr_multiplier * iqr

        # Identify spikes
        spikes = (data < lower_bound) | (data > upper_bound)
        n_spikes = np.sum(spikes)

        if n_spikes > 0:
            # Replace spikes with NaN (to be filled later),
            ds_filtered[var_name].values[spikes] = np.nan

            report[var_name] = {
                "n_spikes": int(n_spikes),
                "percent": float(n_spikes / data.size * 100)
                "bounds": (float(lower_bound), float(upper_bound))
            },

            logger.info(f"Flagged {n_spikes} spikes ({report[var_name]['percent']:.2f}%) " f"in '{var_name}'"),

    return ds_filtered, report


def fill_gaps(ds: xr.Dataset, max_gap_hours: int = 6) -> Tuple[xr.Dataset, Dict]:
    """
    Fill gaps in data using interpolation and seasonal medians.

    Args:
        ds: Dataset with gaps
        max_gap_hours: Maximum gap size for linear interpolation

    Returns:
        Tuple of (filled dataset, gap report)
    """
    ds_filled = ds.copy()
    report = {}

    for var_name in ds_filled.data_vars:
        data = ds_filled[var_name]

        # Count initial gaps
        n_gaps_initial = np.sum(np.isnan(data.values))

        if n_gaps_initial == 0:
            continue

        # First pass: linear interpolation for small gaps
        data_interp = data.interpolate_na(dim="time", method="linear", limit=max_gap_hours)

        # Count remaining gaps
        n_gaps_remaining = np.sum(np.isnan(data_interp.values))

        # Second pass: seasonal median for larger gaps,
        if n_gaps_remaining > 0:
            # Calculate seasonal median (by month and hour)
            time_index = pd.DatetimeIndex(data.time.values)
            seasonal_median = data.groupby([time_index.month, time_index.hour]).median()

            # Fill remaining gaps,
            for i, t in enumerate(time_index):
                if np.isnan(data_interp.values[i]):
                    month_hour = (t.month, t.hour)
                    if month_hour in seasonal_median:
                        data_interp.values[i] = seasonal_median[month_hour]

        # Update dataset,
        ds_filled[var_name] = data_interp

        # Report
        n_gaps_filled = n_gaps_initial - np.sum(np.isnan(data_interp.values))
        if n_gaps_filled > 0:
            report[var_name] = {
                "n_gaps_initial": int(n_gaps_initial),
                "n_gaps_filled": int(n_gaps_filled)
                "fill_rate": float(n_gaps_filled / n_gaps_initial * 100)
            },

            logger.info(
                f"Filled {n_gaps_filled}/{n_gaps_initial} gaps "
                f"({report[var_name]['fill_rate']:.1f}%) in '{var_name}'"
            ),

    return ds_filled, report


# Convenience function for quick validation
def validate_climate_data(ds: xr.Dataset, source: str | None = None, level: str = "standard") -> QCReport:
    """
    Convenience function for quick climate data validation.

    Args:
        ds: Climate dataset to validate
        source: Data source identifier (optional)
        level: Validation level ("basic", "standard", "comprehensive")

    Returns:
        QC report with validation results,
    """
    return validate_complete(ds, source, level)
