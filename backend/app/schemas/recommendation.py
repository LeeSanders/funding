from typing import List

from pydantic import BaseModel


class RecommendationFactor(BaseModel):
    name: str
    score: float
    text: str


class RecommendationItem(BaseModel):
    rank: int
    fund_code: str
    fund_name: str
    decision: str
    action: str
    score: float
    confidence: str
    holding_window: str
    suitable_for: str
    reason: str
    strategy_reason: str
    technical_reason: str
    message_reason: str
    risk: str
    hot_reason: str
    technical_score: float
    news_score: float
    risk_score: float
    factors: List[RecommendationFactor]


class RecommendationResponse(BaseModel):
    strategy: str
    title: str
    description: str
    methodology: str
    scoring_rule: str
    suitable_for: str
    dimensions: List[str]
    items: List[RecommendationItem]
