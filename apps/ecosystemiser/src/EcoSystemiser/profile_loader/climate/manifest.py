"""Manifest generation for climate data provenance"""

import hashlib
import json
from datetime import datetime
from typing import Any, Dict

import numpy as np
import xarray as xr


def build_manifest(
    *,
    adapter_name: str,
    adapter_version: str,
    req: Dict,
    qc_report: Dict,
    source_meta: Dict,
    ds: xr.Dataset = None,
) -> Dict[str, Any]:
    """
    Build manifest for climate data provenance.

    Args:
        adapter_name: Name of data adapter used
        adapter_version: Version of adapter
        req: Request parameters dictionary
        qc_report: Quality control report
        source_meta: Metadata from source
        ds: Optional dataset to hash

    Returns:
        Manifest dictionary
    """
    manifest = {
        "version": "1.0",
        "created_at": datetime.utcnow().isoformat(),
        "adapter": {"name": adapter_name, "version": adapter_version},
        "request": req,
        "source_metadata": source_meta,
        "quality_control": qc_report,
        "variables": {},
        "statistics": {},
    }

    # Add variable metadata if dataset provided
    if ds is not None:
        for var in ds.data_vars:
            manifest["variables"][var] = {
                "units": ds[var].attrs.get("units", "unknown"),
                "type": ds[var].attrs.get("type", "unknown"),
                "shape": ds[var].shape,
                "dtype": str(ds[var].dtype),
            }

        # Add data hash
        manifest["data_hash"] = hash_dataset(ds)

        # Add basic statistics
        manifest["statistics"] = {
            "time_range": {
                "start": str(ds.time.min().values),
                "end": str(ds.time.max().values),
                "n_timesteps": len(ds.time),
            }
        }

    return manifest


def hash_dataset(ds: xr.Dataset) -> str:
    """
    Generate stable hash of dataset content.

    Args:
        ds: Dataset to hash

    Returns:
        SHA256 hash string
    """
    hasher = hashlib.sha256()

    # Hash coordinates
    for coord_name in sorted(ds.coords):
        coord = ds.coords[coord_name]
        hasher.update(coord_name.encode())
        hasher.update(np.array(coord.values).tobytes())

    # Hash data variables
    for var_name in sorted(ds.data_vars):
        var = ds[var_name]
        hasher.update(var_name.encode())

        # Hash data (handle NaN values)
        data = var.values
        if np.issubdtype(data.dtype, np.floating):
            # Replace NaN with sentinel value for consistent hashing
            data_copy = data.copy()
            data_copy[np.isnan(data_copy)] = -999999
            hasher.update(data_copy.tobytes())
        else:
            hasher.update(data.tobytes())

        # Hash attributes
        attrs_str = json.dumps(dict(var.attrs), sort_keys=True)
        hasher.update(attrs_str.encode())

    return hasher.hexdigest()


def validate_manifest(manifest: Dict) -> bool:
    """
    Validate manifest structure.

    Args:
        manifest: Manifest to validate

    Returns:
        True if valid
    """
    required_keys = ["version", "created_at", "adapter", "request"]

    for key in required_keys:
        if key not in manifest:
            return False

    if "name" not in manifest["adapter"] or "version" not in manifest["adapter"]:
        return False

    return True
