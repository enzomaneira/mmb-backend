from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import Order, OrderItem, OrderStatus, OrderStatusHistory, Product
from app.models.enums import ProductType
from app.schemas.revenue import MonthlyRevenueResponse, RevenueChartPoint

router = APIRouter(prefix="/revenue", tags=["revenue"])


def _query_monthly_revenue(
    db: Session,
    start_year: int | None,
    start_month: int | None,
    end_year: int | None,
    end_month: int | None,
    product_type: ProductType | None = None,
    product_id: int | None = None,
) -> list[dict]:
    """
    Aggregate revenue from PAID orders grouped by year + month.
    No cached table — always fresh from source data.
    """
    if product_type is not None or product_id is not None:
        # Sum only matching items' subtotals
        base = (
            db.query(
                OrderStatusHistory.changed_at.label("paid_at"),
                (OrderItem.unit_price * OrderItem.quantity).label("item_total"),
            )
            .join(OrderStatusHistory, OrderStatusHistory.order_id == OrderItem.order_id)
            .filter(OrderStatusHistory.status == OrderStatus.PAID)
        )
        if product_type is not None:
            base = base.join(Product, Product.id == OrderItem.product_id).filter(
                Product.product_type == product_type
            )
        if product_id is not None:
            base = base.filter(OrderItem.product_id == product_id)
        paid_subq = base.subquery()
        value_expr = func.sum(paid_subq.c.item_total)
    else:
        paid_subq = (
            db.query(
                Order.total,
                OrderStatusHistory.changed_at.label("paid_at"),
            )
            .join(OrderStatusHistory, OrderStatusHistory.order_id == Order.id)
            .filter(OrderStatusHistory.status == OrderStatus.PAID)
            .subquery()
        )
        value_expr = func.sum(paid_subq.c.total)

    year_expr = func.extract("year", paid_subq.c.paid_at)
    month_expr = func.extract("month", paid_subq.c.paid_at)
    period_num = year_expr * 100 + month_expr

    query = db.query(
        year_expr.label("year"),
        month_expr.label("month"),
        value_expr.label("value"),
    )

    if start_year is not None and start_month is not None:
        query = query.filter(period_num >= start_year * 100 + start_month)
    if end_year is not None and end_month is not None:
        query = query.filter(period_num <= end_year * 100 + end_month)

    rows = query.group_by("year", "month").order_by("year", "month").all()
    return [
        {
            "year": int(row.year),
            "month": int(row.month),
            "value": row.value or Decimal("0"),
        }
        for row in rows
    ]


@router.get("", response_model=list[MonthlyRevenueResponse])
def list_monthly_revenue(
    db: Session = Depends(get_db),
    start_year: int | None = Query(default=None),
    start_month: int | None = Query(default=None, ge=1, le=12),
    end_year: int | None = Query(default=None),
    end_month: int | None = Query(default=None, ge=1, le=12),
    product_type: ProductType | None = Query(default=None),
    product_id: int | None = Query(default=None),
) -> list[MonthlyRevenueResponse]:
    rows = _query_monthly_revenue(
        db, start_year, start_month, end_year, end_month,
        product_type=product_type, product_id=product_id,
    )
    return [MonthlyRevenueResponse(**row) for row in rows]


@router.get("/chart", response_model=list[RevenueChartPoint])
def revenue_chart(
    db: Session = Depends(get_db),
    start_year: int | None = Query(default=None),
    start_month: int | None = Query(default=None, ge=1, le=12),
    end_year: int | None = Query(default=None),
    end_month: int | None = Query(default=None, ge=1, le=12),
    product_type: ProductType | None = Query(default=None),
    product_id: int | None = Query(default=None),
) -> list[RevenueChartPoint]:
    rows = _query_monthly_revenue(
        db, start_year, start_month, end_year, end_month,
        product_type=product_type, product_id=product_id,
    )
    return [
        RevenueChartPoint(period=f"{row['year']}-{row['month']:02d}", value=row["value"])
        for row in rows
    ]
