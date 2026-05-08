from sqlalchemy import Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class RecommendationSnapshot(Base):
    __tablename__ = "recommendation_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    strategy: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    fund_code: Mapped[str] = mapped_column(String(6), index=True, nullable=False)
    rank: Mapped[int] = mapped_column(nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    risk: Mapped[str] = mapped_column(Text, nullable=False)
