from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class OCRJob(Base):
    __tablename__ = "ocr_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)


class OCRExtractionItem(Base):
    __tablename__ = "ocr_extraction_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("ocr_jobs.id"), index=True)
    fund_code: Mapped[str] = mapped_column(String(6), nullable=False)
    fund_name: Mapped[str] = mapped_column(String(128), nullable=False)
    shares: Mapped[float] = mapped_column(Float, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    profit: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)
