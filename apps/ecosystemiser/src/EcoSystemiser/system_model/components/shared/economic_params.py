"""Economic parameters for system components."""

from typing import Optional

from pydantic import BaseModel, Field


class EconomicParamsModel(BaseModel):
    """Economic parameters for system components."""

    capex: float = Field(0.0, description="Capital expenditure (€)")
    opex_fix: float = Field(0.0, description="Fixed operational expenditure (€/year)")
    opex_var: float = Field(
        0.0, description="Variable operational expenditure (€/kWh or €/m³)"
    )
    lifetime: float = Field(20.0, description="Component lifetime (years)")
    discount_rate: float = Field(0.05, description="Discount rate for NPV calculations")
    salvage_value: float = Field(0.0, description="Salvage value at end of life (€)")

    class Config:
        extra = "allow"  # Allow additional fields for component-specific params
