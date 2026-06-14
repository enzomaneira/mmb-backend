from decimal import Decimal

from sqlalchemy import Integer, Numeric, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MonthlyRevenue(Base):
    __tablename__ = "monthly_revenue"
    __table_args__ = (PrimaryKeyConstraint("year", "month"),)

    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
