from typing import List, Optional

from pydantic import BaseModel


class DashboardFundItem(BaseModel):
    code: str
    name: str
    theme: str
    decision: str
    score: float
    technical_score: float
    news_score: float
    risk_score: float
    estimated_change_rate: float
    updated_at: str


class DashboardThemeItem(BaseModel):
    name: str
    value: float
    count: int


class DashboardImpactItem(BaseModel):
    code: str
    name: str
    relation: str
    theme: str


class DashboardMessageItem(BaseModel):
    fund_code: str
    fund_name: str
    title: str
    text: str
    channel: str
    source: str
    published_at: str
    theme: str
    url: Optional[str] = None
    impacts: List[DashboardImpactItem] = []


class DashboardResponse(BaseModel):
    market_heat: float
    market_heat_delta: str
    event_count: int
    pool_count: int
    focus_funds: List[DashboardFundItem]
    themes: List[DashboardThemeItem]
    headlines: List[DashboardMessageItem]
    timeline: List[DashboardMessageItem]
