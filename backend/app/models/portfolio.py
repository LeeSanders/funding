from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class PortfolioHolding(Base):
    __tablename__ = "portfolio_holdings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    fund_code: Mapped[str] = mapped_column(ForeignKey("funds.code"), index=True)
    shares: Mapped[float] = mapped_column(Float, nullable=False)
    cost_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")


class ValuationSnapshot(Base):
    __tablename__ = "valuation_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    fund_code: Mapped[str] = mapped_column(ForeignKey("funds.code"), index=True)
    estimated_nav: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_change_rate: Mapped[float] = mapped_column(Float, nullable=False)
    valuation_method: Mapped[str] = mapped_column(String(32), nullable=False, default="cached")
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)
