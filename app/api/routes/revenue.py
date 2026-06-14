from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import MonthlyRevenue
from app.schemas.revenue import MonthlyRevenueResponse, RevenueChartPoint

router = APIRouter(prefix="/revenue", tags=["revenue"])


@router.get("", response_model=list[MonthlyRevenueResponse])
def list_monthly_revenue(
    db: Session = Depends(get_db),
    start_year: int | None = Query(default=None),
    start_month: int | None = Query(default=None, ge=1, le=12),
    end_year: int | None = Query(default=None),
    end_month: int | None = Query(default=None, ge=1, le=12),
) -> list[MonthlyRevenue]:
    query = db.query(MonthlyRevenue)

    if start_year is not None and start_month is not None:
        query = query.filter(
            (MonthlyRevenue.year > start_year)
            | ((MonthlyRevenue.year == start_year) & (MonthlyRevenue.month >= start_month))
        )
    if end_year is not None and end_month is not None:
        query = query.filter(
            (MonthlyRevenue.year < end_year)
            | ((MonthlyRevenue.year == end_year) & (MonthlyRevenue.month <= end_month))
        )

    return query.order_by(MonthlyRevenue.year, MonthlyRevenue.month).all()


@router.get("/chart", response_model=list[RevenueChartPoint])
def revenue_chart(
    db: Session = Depends(get_db),
    start_year: int | None = Query(default=None),
    start_month: int | None = Query(default=None, ge=1, le=12),
    end_year: int | None = Query(default=None),
    end_month: int | None = Query(default=None, ge=1, le=12),
) -> list[RevenueChartPoint]:
    rows = list_monthly_revenue(
        db=db,
        start_year=start_year,
        start_month=start_month,
        end_year=end_year,
        end_month=end_month,
    )
    return [
        RevenueChartPoint(period=f"{row.year}-{row.month:02d}", value=row.value)
        for row in rows
    ]
