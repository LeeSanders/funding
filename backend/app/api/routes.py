from typing import Dict

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.analysis import FundAnalysisResponse
from app.schemas.common import MessageResponse
from app.schemas.dashboard import DashboardResponse
from app.schemas.fund import FundDetail
from app.schemas.ocr import OCRItemUpdateRequest, OCRJobResponse, OCRSimulateRequest
from app.schemas.portfolio import HoldingAdjustRequest, HoldingCreate, HoldingUpdateRequest, PortfolioResponse
from app.schemas.recommendation import RecommendationResponse
from app.services import dashboard_service, fund_service, ocr_service, portfolio_service, recommendation_service

router = APIRouter()


@router.get("/health", response_model=MessageResponse)
def health() -> MessageResponse:
    return MessageResponse(message="ok")


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(db: Session = Depends(get_db)) -> DashboardResponse:
    return dashboard_service.get_dashboard(db)


@router.get("/funds/{code}", response_model=FundDetail)
def get_fund(code: str, db: Session = Depends(get_db)) -> FundDetail:
    try:
        return fund_service.get_fund_detail(db, code)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/analysis/{code}", response_model=FundAnalysisResponse)
def get_analysis(code: str, db: Session = Depends(get_db)) -> FundAnalysisResponse:
    try:
        return fund_service.get_fund_analysis(db, code)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/recommendations", response_model=RecommendationResponse)
def get_recommendations(strategy: str = "steady", db: Session = Depends(get_db)) -> RecommendationResponse:
    return recommendation_service.get_recommendations(db, strategy)


@router.get("/portfolio", response_model=PortfolioResponse)
def get_portfolio(refresh: bool = Query(False), db: Session = Depends(get_db)) -> PortfolioResponse:
    return portfolio_service.get_portfolio(db, refresh=refresh)


@router.post("/portfolio/holdings", response_model=PortfolioResponse)
def create_holding(payload: HoldingCreate, db: Session = Depends(get_db)) -> PortfolioResponse:
    return portfolio_service.create_holding(db, payload)


@router.patch("/portfolio/holdings/{holding_id}/adjust", response_model=PortfolioResponse)
def adjust_holding(holding_id: int, payload: HoldingAdjustRequest, db: Session = Depends(get_db)) -> PortfolioResponse:
    try:
        return portfolio_service.adjust_holding(db, holding_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/portfolio/holdings/{holding_id}", response_model=PortfolioResponse)
def update_holding(holding_id: int, payload: HoldingUpdateRequest, db: Session = Depends(get_db)) -> PortfolioResponse:
    try:
        return portfolio_service.update_holding(db, holding_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/portfolio/holdings/{holding_id}", response_model=PortfolioResponse)
def delete_holding(holding_id: int, db: Session = Depends(get_db)) -> PortfolioResponse:
    try:
        return portfolio_service.delete_holding(db, holding_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/ocr/simulate", response_model=OCRJobResponse)
def simulate_ocr(payload: OCRSimulateRequest, db: Session = Depends(get_db)) -> OCRJobResponse:
    return ocr_service.simulate_ocr(db, payload)


@router.post("/ocr/upload", response_model=OCRJobResponse)
async def upload_ocr_image(file: UploadFile = File(...), db: Session = Depends(get_db)) -> OCRJobResponse:
    try:
        content = await file.read()
        return ocr_service.upload_ocr_image(db, file.filename or "ocr_upload.png", content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/ocr/{job_id}", response_model=OCRJobResponse)
def get_ocr(job_id: int, db: Session = Depends(get_db)) -> OCRJobResponse:
    try:
        return ocr_service.get_ocr_job(db, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/ocr/{job_id}/items/{item_id}", response_model=OCRJobResponse)
def update_ocr_item(job_id: int, item_id: int, payload: OCRItemUpdateRequest, db: Session = Depends(get_db)) -> OCRJobResponse:
    try:
        return ocr_service.update_ocr_item(db, job_id, item_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/ocr/{job_id}/confirm", response_model=Dict[str, int])
def confirm_ocr(job_id: int, db: Session = Depends(get_db)) -> Dict[str, int]:
    return ocr_service.confirm_ocr_to_portfolio(db, job_id)
