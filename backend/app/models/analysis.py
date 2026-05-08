from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class FundAnalysisSnapshot(Base):
    __tablename__ = "fund_analysis_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    fund_code: Mapped[str] = mapped_column(ForeignKey("funds.code"), index=True)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    holding_window: Mapped[str] = mapped_column(String(32), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    technical_score: Mapped[float] = mapped_column(Float, nullable=False)
    news_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    summary_title: Mapped[str] = mapped_column(String(128), nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    reasons_json: Mapped[str] = mapped_column(Text, nullable=False)
    events_json: Mapped[str] = mapped_column(Text, nullable=False)
    risks_json: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)
