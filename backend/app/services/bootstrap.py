from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.analysis import FundAnalysisSnapshot
from app.models.fund import Fund
from app.models.ocr import OCRExtractionItem, OCRJob
from app.models.portfolio import PortfolioHolding, ValuationSnapshot
from app.models.recommendation import RecommendationSnapshot
from app.services.seed_data import ANALYSES, FUNDS, HOLDINGS, MOCK_OCR, RECOMMENDATIONS, VALUATIONS


def seed_database(db: Session) -> None:
    has_fund = db.scalar(select(Fund.code).limit(1))
    if has_fund:
        return

    db.add_all(Fund(**fund) for fund in FUNDS)
    db.add_all(FundAnalysisSnapshot(**analysis) for analysis in ANALYSES)

    for strategy, payload in RECOMMENDATIONS.items():
        db.add_all(
            RecommendationSnapshot(
                strategy=strategy,
                fund_code=row["fund_code"],
                rank=row["rank"],
                decision=row["decision"],
                score=row["score"],
                reason=row["reason"],
                risk=row["risk"],
            )
            for row in payload["rows"]
        )

    db.add_all(PortfolioHolding(**holding) for holding in HOLDINGS)
    db.add_all(ValuationSnapshot(**item) for item in VALUATIONS)

    ocr_job = OCRJob(
        filename=MOCK_OCR["filename"],
        status=MOCK_OCR["status"],
        created_at=MOCK_OCR["created_at"],
    )
    db.add(ocr_job)
    db.flush()
    db.add_all(
        OCRExtractionItem(job_id=ocr_job.id, **item)
        for item in MOCK_OCR["items"]
    )
    db.commit()
