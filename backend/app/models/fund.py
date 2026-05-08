from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Fund(Base):
    __tablename__ = "funds"

    code: Mapped[str] = mapped_column(String(6), primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    fund_type: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False)
    theme: Mapped[str] = mapped_column(String(64), nullable=False)
    company: Mapped[str] = mapped_column(String(64), nullable=True)
    latest_nav: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    estimated_nav: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    estimated_change_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    latest_volume_rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
