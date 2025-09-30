"""
EcoSystemiser Configuration Module

Configuration bridge between EcoSystemiser and Hive platform following
the inherit→extend architectural pattern.
"""

from .bridge import EcoSystemiserConfig, get_ecosystemiser_config, reload_ecosystemiser_config

__all__ = ["EcoSystemiserConfig", "get_ecosystemiser_config", "reload_ecosystemiser_config"]
