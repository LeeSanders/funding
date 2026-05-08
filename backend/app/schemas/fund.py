from typing import Optional

from pydantic import BaseModel


class FundBase(BaseModel):
    code: str
    name: str
    fund_type: str
    risk_level: str
    theme: str
    latest_nav: float
    estimated_nav: float
    estimated_change_rate: float


class FundDetail(FundBase):
    company: Optional[str] = None
