"""
Climate data validator implementation.

This module provides the main validator class that applies quality control
profiles to climate datasets.
"""

import xarray as xr
from typing import Optional, Dict, Any
from ecosystemiser.profile_loader.climate.processing.validation.base import QCProfile, QCReport
from ecosystemiser.hive_logging_adapter import get_logger

logger = get_logger(__name__)


class ClimateDataValidator:
    """Validates climate data using quality control profiles."""

    def __init__(self, qc_profile: Optional[QCProfile] = None):
        """
        Initialize the climate data validator.

        Args:
            qc_profile: Quality control profile to apply. If None, uses default.
        """
        self.qc_profile = qc_profile or QCProfile()

    def validate(self, ds: xr.Dataset) -> QCReport:
        """
        Validate a climate dataset.

        Args:
            ds: xarray Dataset to validate

        Returns:
            QCReport with validation results
        """
        if self.qc_profile is None:
            # No validation if no profile
            return QCReport()

        # Apply the QC profile
        report = self.qc_profile.apply(ds)

        # Log any issues found
        if not report.is_valid:
            logger.warning(f"Climate data validation found {len(report.issues)} issues")
            for issue in report.issues[:5]:  # Log first 5 issues
                logger.debug(f"  - {issue['type']}: {issue['message']}")

        return report

    def apply_corrections(self, ds: xr.Dataset, report: QCReport) -> xr.Dataset:
        """
        Apply automatic corrections based on validation report.

        Args:
            ds: Dataset to correct
            report: Validation report with issues

        Returns:
            Corrected dataset
        """
        ds_corrected = ds.copy()

        for issue in report.issues:
            if issue.get('auto_correctable', False):
                correction_type = issue.get('correction_type')

                if correction_type == 'clip_range':
                    # Clip values to valid range
                    var_name = issue.get('variable')
                    min_val = issue.get('min_value')
                    max_val = issue.get('max_value')

                    if var_name in ds_corrected:
                        ds_corrected[var_name] = ds_corrected[var_name].clip(min=min_val, max=max_val)
                        logger.info(f"Clipped {var_name} to range [{min_val}, {max_val}]")

                elif correction_type == 'interpolate_missing':
                    # Interpolate missing values
                    var_name = issue.get('variable')
                    if var_name in ds_corrected:
                        ds_corrected[var_name] = ds_corrected[var_name].interpolate_na(dim='time')
                        logger.info(f"Interpolated missing values in {var_name}")

        return ds_corrected


def apply_quality_control(
    ds: xr.Dataset,
    qc_profile: Optional[QCProfile] = None,
    auto_correct: bool = False
) -> tuple[xr.Dataset, QCReport]:
    """
    Apply quality control to a climate dataset.

    Args:
        ds: Dataset to validate
        qc_profile: Quality control profile to use
        auto_correct: Whether to apply automatic corrections

    Returns:
        Tuple of (possibly corrected dataset, validation report)
    """
    validator = ClimateDataValidator(qc_profile)
    report = validator.validate(ds)

    if auto_correct and not report.is_valid:
        ds = validator.apply_corrections(ds, report)
        # Re-validate after corrections
        report = validator.validate(ds)

    return ds, report