from typing import List, Optional

from pydantic import BaseModel


class OCRSimulateRequest(BaseModel):
    filename: str = "portfolio_screenshot.png"


class OCRItemResponse(BaseModel):
    id: int
    fund_code: str
    fund_name: str
    shares: float
    amount: float
    profit: float
    confidence: str


class OCRItemUpdateRequest(BaseModel):
    fund_code: str
    fund_name: str = ""
    amount: float
    profit: float = 0.0
    shares: Optional[float] = None


class OCRJobResponse(BaseModel):
    job_id: int
    status: str
    items: List[OCRItemResponse]
