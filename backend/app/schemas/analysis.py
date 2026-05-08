from typing import Dict, List, Optional

from pydantic import BaseModel

from app.schemas.fund import FundDetail


class AnalysisItem(BaseModel):
    title: str
    text: Optional[str] = None
    meta: Optional[str] = None
    channel: Optional[str] = None
    source: Optional[str] = None
    url: Optional[str] = None
    published_at: Optional[str] = None


class ScoreSummary(BaseModel):
    score: float
    hint: str


class TrendChartPoint(BaseModel):
    date: str
    value: float
    label: Optional[str] = None


class TrendChartEvent(BaseModel):
    date: str
    title: str
    channel: Optional[str] = None
    sentiment: Optional[str] = None


class TrendChartPayload(BaseModel):
    nav_series: List[TrendChartPoint]
    theme_series: List[TrendChartPoint]
    event_points: List[TrendChartEvent]


class FundAnalysisResponse(BaseModel):
    fund: FundDetail
    decision: str
    confidence: str
    action: str
    holding_window: str
    score: float
    technical: ScoreSummary
    news: ScoreSummary
    risk: ScoreSummary
    summary_title: str
    summary_text: str
    reasons: Dict[str, List[AnalysisItem]]
    announcement_events: List[AnalysisItem]
    news_events: List[AnalysisItem]
    events: List[AnalysisItem]
    risks: List[AnalysisItem]
    technical_signals: List[AnalysisItem]
    trade_advices: List[AnalysisItem]
    position_note: Optional[AnalysisItem] = None
    trend_chart: Optional[TrendChartPayload] = None
    updated_at: str
