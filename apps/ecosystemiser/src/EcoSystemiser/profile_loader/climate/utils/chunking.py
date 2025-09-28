"""
Utilities for chunked data processing to manage memory usage.
"""

from datetime import datetime, timedelta
from typing import Dict, Generator, List, Optional, Tuple

import numpy as np
import pandas as pd
import xarray as xr
from hive_logging import get_logger

logger = get_logger(__name__)


def split_date_range(
    start_date: datetime, end_date: datetime, chunk_days: int = 365
) -> List[Tuple[datetime, datetime]]:
    """
    Split a date range into chunks to prevent memory issues.

    Args:
        start_date: Start of the period
        end_date: End of the period
        chunk_days: Maximum days per chunk (default 365)

    Returns:
        List of (start, end) date tuples for each chunk
    """
    chunks = []
    current_start = start_date

    while current_start < end_date:
        chunk_end = min(current_start + timedelta(days=chunk_days - 1), end_date)
        chunks.append((current_start, chunk_end))
        current_start = chunk_end + timedelta(days=1)

    return chunks


def process_in_chunks(
    ds: xr.Dataset, chunk_size: str = "100MB", time_chunks: int = 365
) -> xr.Dataset:
    """
    Process large dataset in memory-efficient chunks.

    Args:
        ds: Input dataset
        chunk_size: Target chunk size for dask
        time_chunks: Number of time steps per chunk

    Returns:
        Chunked dataset ready for lazy processing
    """
    # Rechunk the dataset for memory efficiency
    if "time" in ds.dims:
        chunks = {"time": min(time_chunks, len(ds.time))}

        # Add chunking for other dimensions if large
        for dim in ds.dims:
            if dim != "time" and len(ds[dim]) > 1000:
                chunks[dim] = 1000

        ds_chunked = ds.chunk(chunks)
        logger.info(f"Dataset chunked with configuration: {chunks}")
        return ds_chunked

    return ds


def concatenate_chunked_results(
    chunks: List[xr.Dataset], dim: str = "time"
) -> xr.Dataset:
    """
    Efficiently concatenate chunked datasets.

    Args:
        chunks: List of dataset chunks
        dim: Dimension to concatenate along

    Returns:
        Combined dataset
    """
    if not chunks:
        raise ValueError("No chunks to concatenate")

    if len(chunks) == 1:
        return chunks[0]

    # Use dask-aware concatenation
    try:
        combined = xr.concat(chunks, dim=dim, data_vars="minimal")
        logger.info(f"Successfully concatenated {len(chunks)} chunks")
        return combined
    except Exception as e:
        logger.error(f"Failed to concatenate chunks: {e}")
        # Fallback to sequential concatenation
        result = chunks[0]
        for chunk in chunks[1:]:
            result = xr.concat([result, chunk], dim=dim)
        return result


def estimate_memory_usage(ds: xr.Dataset) -> float:
    """
    Estimate memory usage of a dataset in MB.

    Args:
        ds: Dataset to estimate

    Returns:
        Estimated memory usage in MB
    """
    total_size = 0

    for var in ds.data_vars:
        # Get the size of the variable's data
        var_data = ds[var].values
        var_size = var_data.nbytes if hasattr(var_data, "nbytes") else 0
        total_size += var_size

    # Convert to MB
    return total_size / (1024 * 1024)


def create_time_chunks_generator(
    ds: xr.Dataset, chunk_days: int = 30
) -> Generator[xr.Dataset, None, None]:
    """
    Generate time chunks from a dataset for streaming processing.

    Args:
        ds: Input dataset
        chunk_days: Days per chunk

    Yields:
        Dataset chunks
    """
    if "time" not in ds.dims:
        yield ds
        return

    time_index = pd.DatetimeIndex(ds.time.values)
    start_date = time_index[0].to_pydatetime()
    end_date = time_index[-1].to_pydatetime()

    for chunk_start, chunk_end in split_date_range(start_date, end_date, chunk_days):
        # Select time slice
        mask = (time_index >= chunk_start) & (time_index <= chunk_end)
        if mask.any():
            chunk = ds.isel(time=mask)
            logger.debug(f"Yielding chunk: {chunk_start} to {chunk_end}")
            yield chunk


def apply_chunked_operation(
    ds: xr.Dataset, operation: callable, chunk_days: int = 30, **kwargs
) -> xr.Dataset:
    """
    Apply an operation to a dataset in chunks and combine results.

    Args:
        ds: Input dataset
        operation: Function to apply to each chunk
        chunk_days: Days per chunk
        **kwargs: Additional arguments for operation

    Returns:
        Processed dataset
    """
    results = []

    for i, chunk in enumerate(create_time_chunks_generator(ds, chunk_days)):
        logger.debug(f"Processing chunk {i+1}")
        result = operation(chunk, **kwargs)
        results.append(result)

    return concatenate_chunked_results(results)
