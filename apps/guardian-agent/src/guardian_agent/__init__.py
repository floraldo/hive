"""
Hive Guardian Agent - AI-powered code review automation and platform intelligence.

This package provides intelligent code review capabilities and strategic
platform intelligence leveraging the Hive platform's AI infrastructure.

The Guardian Agent has evolved into the Oracle - providing not just code review,
but comprehensive platform intelligence, predictive analytics, and strategic
recommendations for the entire Hive ecosystem.
"""

from guardian_agent.core.config import GuardianConfig
from guardian_agent.core.interfaces import ReviewResult, Violation
from guardian_agent.genesis.genesis_agent import GenesisAgent, GenesisConfig
from guardian_agent.intelligence.oracle_service import OracleConfig, OracleService
from guardian_agent.review.engine import ReviewEngine

__version__ = "0.2.0"  # Upgraded to reflect Oracle capabilities

__all__ = [
    "GuardianConfig",
    "ReviewEngine",
    "ReviewResult",
    "Violation",
    "OracleService",
    "OracleConfig",
    "GenesisAgent",
    "GenesisConfig",
]
