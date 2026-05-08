from typing import List, Optional

from pydantic import BaseModel


class HoldingCreate(BaseModel):
    fund_code: str
    shares: float
    cost_amount: float = 0.0
    source: str = "manual"


class HoldingItem(BaseModel):
    id: int
    fund_code: str
    fund_name: str
    shares: float
    cost_amount: float
    estimated_nav: float
    estimated_change_rate: float
    estimated_profit: float
    valuation_method: str
    updated_at: str


class HoldingAdjustRequest(BaseModel):
    delta_shares: float
    delta_cost_amount: float = 0.0


class HoldingUpdateRequest(BaseModel):
    fund_code: Optional[str] = None
    shares: Optional[float] = None
    cost_amount: Optional[float] = None


class PortfolioSummaryResponse(BaseModel):
    market_value: float
    daily_profit: float
    daily_profit_rate: float
    holding_count: int
    updated_at: str


class PortfolioResponse(BaseModel):
    summary: PortfolioSummaryResponse
    holdings: List[HoldingItem]
