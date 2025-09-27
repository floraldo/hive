#!/usr/bin/env python
"""
Setup script for EcoSystemiser - Hive ecosystem energy optimization platform.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding='utf-8')

setup(
    name="ecosystemiser",
    version="2.0.0",
    author="Hive Platform Team",
    description="Energy ecosystem optimization and simulation platform",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/hive-platform/ecosystemiser",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.8",
    install_requires=[
        # Core dependencies
        "numpy>=1.20.0",
        "pandas>=1.3.0",
        "xarray>=0.19.0",
        "pydantic>=2.0.0",

        # Optimization
        "cvxpy>=1.2.0",

        # Climate data adapters
        "requests>=2.26.0",
        "tenacity>=8.0.0",

        # API (optional, for API server)
        # "fastapi>=0.70.0",
        # "uvicorn[standard]>=0.15.0",

        # Redis (optional, for distributed job management)
        # "redis>=4.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=3.0.0",
            "pytest-asyncio>=0.18.0",
            "black>=22.0.0",
            "ruff>=0.0.200",
            "mypy>=0.900",
        ],
        "api": [
            "fastapi>=0.70.0",
            "uvicorn[standard]>=0.15.0",
            "redis>=4.0.0",
        ],
        "viz": [
            "matplotlib>=3.5.0",
            "plotly>=5.0.0",
            "dash>=2.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "ecosystemiser=EcoSystemiser.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Physics",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)