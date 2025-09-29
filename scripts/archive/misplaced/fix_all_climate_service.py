#!/usr/bin/env python3
"""Fix all remaining syntax errors in climate service.py"""

import re

from hive_logging import get_logger

logger = get_logger(__name__)


def fix_climate_service():
    """Fix all syntax errors in climate service.py"""

    file_path = "src/ecosystemiser/profile_loader/climate/service.py"

    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    # Fix specific issues:

    # 1. Remove commas after raise statements
    content = re.sub(r"(\s+raise),(\s*\n)", r"\1\2", content)

    # 2. Fix missing commas in function calls
    # Fix lines with missing commas between function arguments
    content = content.replace(
        'field="variables"\n                    value=', 'field="variables",\n                    value='
    )
    content = content.replace(
        'field="source"\n                    value=', 'field="source",\n                    value='
    )
    content = content.replace(
        'adapter_name="factory"\n                    details=', 'adapter_name="factory",\n                    details='
    )

    # 3. Fix function calls missing commas
    content = content.replace(
        "                manifest=manifest\n                    path_parquet=",
        "                manifest=manifest,\n                    path_parquet=",
    )
    content = content.replace(
        "                lat=lat\n                lon=lon", "                lat=lat,\n                lon=lon"
    )
    content = content.replace(
        "                variables=req.variables\n                period=",
        "                variables=req.variables,\n                period=",
    )
    content = content.replace(
        "                period=req.period\n                resolution=",
        "                period=req.period,\n                resolution=",
    )

    # 4. Fix build_manifest call
    content = content.replace(
        '                adapter_name="enhanced_service"\n                adapter_version="1.0.0"',
        '                adapter_name="enhanced_service",\n                adapter_version="1.0.0"',
    )
    content = content.replace(
        '                adapter_version="1.0.0"\n                req=',
        '                adapter_version="1.0.0",\n                req=',
    )
    content = content.replace(
        "                qc_report=processing_report\n                source_meta=",
        "                qc_report=processing_report,\n                source_meta=",
    )

    # 5. Fix generator.generate call
    content = content.replace(
        "                historical_data=ds\n                target_year=",
        "                historical_data=ds,\n                target_year=",
    )
    content = content.replace(
        "                target_year=target_year\n                weights=",
        "                target_year=target_year,\n                weights=",
    )
    content = content.replace(
        "                weights=custom_weights\n                min_data_years=",
        "                weights=custom_weights,\n                min_data_years=",
    )

    # 6. Fix copula_synthetic_generation call
    content = content.replace(
        "                ds_hist=ds\n                seed=", "                ds_hist=ds,\n                seed="
    )
    content = content.replace(
        '                target_length=synth_options.get("target_length", "1Y")\n                **',
        '                target_length=synth_options.get("target_length", "1Y"),\n                **',
    )

    # 7. Fix multivariate_block_bootstrap call
    content = content.replace(
        "                ds_hist=ds\n                block=", "                ds_hist=ds,\n                block="
    )

    # 8. Fix ClimateResponse constructor
    content = content.replace(
        "                start_time=start_time\n                end_time=",
        "                start_time=start_time,\n                end_time=",
    )
    content = content.replace(
        "                end_time=end_time\n                variables=",
        "                end_time=end_time,\n                variables=",
    )
    content = content.replace(
        "                variables=variables\n                source=",
        "                variables=variables,\n                source=",
    )
    content = content.replace(
        "                source=req.source\n                shape=",
        "                source=req.source,\n                shape=",
    )
    content = content.replace(
        "                shape=(len(ds.time), len(variables))\n                # Climate-specific fields",
        "                shape=(len(ds.time), len(variables)),\n                # Climate-specific fields",
    )
    content = content.replace(
        "                manifest=manifest\n                path_parquet=cache_path",
        "                manifest=manifest,\n                path_parquet=cache_path",
    )
    content = content.replace(
        "                path_parquet=cache_path\n                stats=",
        "                path_parquet=cache_path,\n                stats=",
    )
    content = content.replace(
        '                stats=describe_stats(ds) if req.mode == "observed" else None\n                # Optional metadata',
        '                stats=describe_stats(ds) if req.mode == "observed" else None,\n                # Optional metadata',
    )
    content = content.replace(
        "                cached=cache_path is not None\n                cache_key=",
        "                cached=cache_path is not None,\n                cache_key=",
    )
    content = content.replace(
        "                cache_key=cache_key if self.config.features.enable_caching else None\n                warnings=",
        "                cache_key=cache_key if self.config.features.enable_caching else None,\n                warnings=",
    )

    # 9. Remove trailing commas from simple statements
    content = re.sub(r"(\s+\w+\s*=\s*[^,\n]+),\s*$", r"\1", content, flags=re.MULTILINE)

    # 10. Remove extra commas after closing braces in dictionaries
    content = content.replace("        },\n\n    def resolve_location", "        }\n\n    def resolve_location")

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info(f"Fixed syntax errors in {file_path}")
    return True


if __name__ == "__main__":
    fix_climate_service()
