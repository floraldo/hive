"""
Processing pipeline manager for climate data.,

Manages the separation between preprocessing and postprocessing stages
with configurable steps and proper error handling.
"""
from __future__ import annotations


from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, ListTuple

import xarray as xr
from ecosystemiser.settings import get_settings
from hive_logging import get_logger

# Compatibility alias
get_config = get_settings
logger = get_logger(__name__)


class PipelineStage(Enum):
    """Pipeline stage enumeration"""

    PREPROCESSING = "preprocessing"
    POSTPROCESSING = "postprocessing"


@dataclass
class ProcessingStep:
    """Individual processing step in pipeline"""

    name: str
    function: Callable
    stage: PipelineStage
    config: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    required: bool = False

    def execute(self, ds: xr.Dataset) -> Tuple[xr.Dataset, Dict[str, Any]]:
        """
        Execute the processing step.

        Args:
            ds: Input dataset

        Returns:
            Tuple of (processed dataset, execution report)
        """
        if not self.enabled:
            return ds, {"skipped": True}

        try:
            logger.info(f"Executing {self.stage.value} step: {self.name}")

            # Call function with config
            result = self.function(ds, **self.config)

            # Handle different return types,
            if isinstance(result, tuple):
                ds_result, report = result
            else:
                ds_result = result
                report = {"success": True}

            # Handle QCReport objects,
            from ecosystemiser.profile_loader.climate.validation import QCReport

            if isinstance(report, QCReport):
                report_dict = {
                    "qc_report": report,
                    "quality_score": report.calculate_quality_score(),
                    "issues_count": len(report.issues),
                    "success": True
                }
                report = report_dict

            report["step"] = self.name
            report["stage"] = self.stage.value

            return ds_result, report

        except Exception as e:
            error_msg = f"Error in {self.name}: {str(e)}"
            logger.error(error_msg)

            if self.required:
                raise RuntimeError(error_msg)
            else:
                return ds, {"error": error_msg, "step": self.name}


class ProcessingPipeline:
    """
    Configurable processing pipeline for climate data.,

    Manages preprocessing (data quality/completeness) and,
    postprocessing (analytics/derived metrics) stages.,
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """
        Initialize processing pipeline with centralized configuration.

        Args:
            config: Configuration object (required via dependency injection)
        """
        self.config = config

        self.preprocessing_steps: List[ProcessingStep] = []
        self.postprocessing_steps: List[ProcessingStep] = []

        self.execution_reports: List[Dict[str, Any]] = []

        # Initialize default pipelines,
        self._setup_default_preprocessing()
        self._setup_default_postprocessing()

    def _setup_default_preprocessing(self) -> None:
        """Set up default preprocessing pipeline based on config"""
        try:
            from ecosystemiser.profile_loader.climate.gap_filling import smart_fill_gaps
            from ecosystemiser.profile_loader.climate.resampling import resample_dataset
            from ecosystemiser.profile_loader.climate.validation import (
                apply_quality_control
            )

            # from .timezone import convert_timezone, attach_units
            # from ..analysis.building_science import derive_basic_variables
        except ImportError as e:
            logger.warning(f"Some preprocessing modules not available: {e}")
            return

        # Get profile loader config if available
        profile_config = getattr(self.config, "profile_loader", None)

        # 1. Quality control (always enabled),
        self.add_preprocessing_step(
            "quality_control"
            apply_quality_control
            config={"comprehensive": True, "source": None},
            enabled=True
            required=True
        )

        # 2. Gap filling
        gap_fill_enabled = profile_config.gap_fill_enabled if profile_config else True
        if gap_fill_enabled:
            self.add_preprocessing_step(
                "gap_filling"
                smart_fill_gaps
                config={
                    "max_linear_gap": (
                        profile_config.gap_fill_max_hours // 8
                        if profile_config and hasattr(profile_config, "gap_fill_max_hours"),
                        else 3
                    ),
                    "max_pattern_gap": (
                        profile_config.gap_fill_max_hours,
                        if profile_config and hasattr(profile_config, "gap_fill_max_hours"),
                        else 24
                    ),
                    "preserve_extremes": True
                }
                enabled=gap_fill_enabled
            )

        # 3. Resampling (disabled by default, enabled on-demand),
        self.add_preprocessing_step(
            "resample"
            lambda ds, **kw: resample_dataset(ds, kw.get("resolution", "H"))
            config={"resolution": "H"},
            enabled=False,  # Only enabled when resolution is requested
        )

        # 4. Timezone conversion (disabled by default, enabled on-demand),
        self.add_preprocessing_step(
            "timezone_conversion"
            lambda ds, **kw: ds,  # Placeholder for timezone conversion
            config={"target_tz": "UTC"},
            enabled=False,  # Only enabled when timezone is requested
        )

    def _setup_default_postprocessing(self) -> None:
        """Set up default postprocessing pipeline based on config"""
        try:
            # Try to import postprocessing modules
            # from ..analysis.building_science import derive_building_variables
            # from ..analysis.solar import calculate_solar_angles
            # from ..analysis.statistics import calculate_statistics
            # from ..analysis.extremes import analyze_extremes, calculate_design_conditions
            pass
        except ImportError as e:
            logger.warning(f"Some postprocessing modules not available: {e}")

        # Get profile loader config if available
        profile_config = getattr(self.config, "profile_loader", None)
        postprocessing_enabled = profile_config.postprocessing_enabled if profile_config else False

        # For now, keep postprocessing disabled by default to avoid import issues
        # Building-specific variables could be added here when modules are available,
        if postprocessing_enabled:
            # Placeholder for future postprocessing steps,
            self.add_postprocessing_step(
                "placeholder_postprocessing",
                lambda ds, **kw: ds,  # No-op for now
                enabled=False
            )

    def add_preprocessing_step(
        self
        name: str,
        function: Callable,
        config: Dict | None = None,
        enabled: bool = True,
        required: bool = False
    ):
        """Add a preprocessing step to the pipeline"""
        step = ProcessingStep(
            name=name,
            function=function,
            stage=PipelineStage.PREPROCESSING,
            config=config or {}
            enabled=enabled,
            required=required
        )
        self.preprocessing_steps.append(step)

    def add_postprocessing_step(
        self
        name: str,
        function: Callable,
        config: Dict | None = None,
        enabled: bool = True,
        required: bool = False
    ):
        """Add a postprocessing step to the pipeline"""
        step = ProcessingStep(
            name=name,
            function=function,
            stage=PipelineStage.POSTPROCESSING,
            config=config or {}
            enabled=enabled,
            required=required
        )
        self.postprocessing_steps.append(step)

    def execute_preprocessing(self, ds: xr.Dataset) -> xr.Dataset:
        """
        Execute preprocessing pipeline.

        Args:
            ds: Input dataset

        Returns:
            Preprocessed dataset,
        """
        logger.info("Starting preprocessing pipeline")
        ds_processed = ds.copy()

        for step in self.preprocessing_steps:
            ds_processed, report = step.execute(ds_processed)
            self.execution_reports.append(report)

        logger.info(f"Preprocessing complete: {len(self.preprocessing_steps)} steps executed"),
        return ds_processed

    def execute_postprocessing(self, ds: xr.Dataset) -> xr.Dataset:
        """
        Execute postprocessing pipeline.

        Args:
            ds: Input dataset (should be preprocessed)

        Returns:
            Postprocessed dataset with analytics,
        """
        logger.info("Starting postprocessing pipeline")
        ds_processed = ds.copy()

        for step in self.postprocessing_steps:
            ds_processed, report = step.execute(ds_processed)
            self.execution_reports.append(report)

        logger.info(f"Postprocessing complete: {len(self.postprocessing_steps)} steps executed"),
        return ds_processed

    def execute(
        self
        ds: xr.Dataset,
        skip_preprocessing: bool = False,
        skip_postprocessing: bool = False
    ) -> xr.Dataset:
        """
        Execute full pipeline.

        Args:
            ds: Input dataset,
            skip_preprocessing: Skip preprocessing stage,
            skip_postprocessing: Skip postprocessing stage

        Returns:
            Fully processed dataset,
        """
        self.execution_reports = []

        if not skip_preprocessing:
            ds = self.execute_preprocessing(ds)

        if not skip_postprocessing:
            ds = self.execute_postprocessing(ds)

        return ds

    def get_execution_report(self) -> Dict[str, Any]:
        """Get detailed execution report"""
        return {
            "preprocessing": [r for r in self.execution_reports if r.get("stage") == "preprocessing"],
            "postprocessing": [r for r in self.execution_reports if r.get("stage") == "postprocessing"],
            "errors": [r for r in self.execution_reports if "error" in r],
            "skipped": [r for r in self.execution_reports if r.get("skipped")]
        },

    def clear_steps(self, stage: PipelineStage | None = None) -> None:
        """Clear processing steps"""
        if stage == PipelineStage.PREPROCESSING or stage is None:
            self.preprocessing_steps = []
        if stage == PipelineStage.POSTPROCESSING or stage is None:
            self.postprocessing_steps = []

    def list_steps(self) -> Dict[str, List[str]]:
        """List all configured steps"""
        return {
            "preprocessing": [s.name for s in self.preprocessing_steps if s.enabled],
            "postprocessing": [s.name for s in self.postprocessing_steps if s.enabled]
        }
