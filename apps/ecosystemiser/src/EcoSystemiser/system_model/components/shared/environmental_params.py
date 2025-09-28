"""Environmental parameters for system components."""

from typing import Optional

from pydantic import BaseModel, Field


class EnvironmentalParamsModel(BaseModel):
    """Environmental parameters for system components."""

    co2_embodied: float = Field(0.0, description="Embodied CO2 (kg CO2)")
    co2_operational: float = Field(0.0, description="Operational CO2 emissions (kg CO2/kWh)")
    recycling_rate: float = Field(0.0, description="Recyclability (0-1)")
    toxicity_score: float = Field(0.0, description="Environmental toxicity score")
    water_usage: float = Field(0.0, description="Water usage (L/kWh)")

    class Config:
        extra = "allow"  # Allow additional fields for component-specific params
