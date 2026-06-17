from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import Order, OrderItem, OrderStatus, OrderStatusHistory, Product
from app.schemas.revenue import (
    CustomerSalesChartPoint,
    ProductRevenueShareItem,
    ProductSalesChartPoint,
    TopProductChartItem,
)

router = APIRouter(prefix="/charts", tags=["charts"])


def _paid_orders_subquery(db: Session):
    """Subquery of all PAID order events with their paid_at timestamp."""
    return (
        db.query(
            Order.id.label("order_id"),
            Order.customer_id,
            Order.total,
            OrderStatusHistory.changed_at.label("paid_at"),
        )
        .join(OrderStatusHistory, OrderStatusHistory.order_id == Order.id)
        .filter(OrderStatusHistory.status == OrderStatus.PAID)
        .subquery()
    )


def _product_stats_subquery(db: Session):
    """Subquery of units_sold and revenue per product from PAID orders."""
    paid_order_ids = (
        db.query(OrderStatusHistory.order_id)
        .filter(OrderStatusHistory.status == OrderStatus.PAID)
        .subquery()
    )
    return (
        db.query(
            OrderItem.product_id.label("product_id"),
            func.coalesce(func.sum(OrderItem.quantity), 0).label("units_sold"),
            func.coalesce(
                func.sum(OrderItem.unit_price * OrderItem.quantity), Decimal("0")
            ).label("revenue"),
        )
        .join(paid_order_ids, paid_order_ids.c.order_id == OrderItem.order_id)
        .group_by(OrderItem.product_id)
        .subquery()
    )


@router.get("/sales-by-product", response_model=list[ProductSalesChartPoint])
def sales_by_product(
    db: Session = Depends(get_db),
    product_id: int = Query(...),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
) -> list[ProductSalesChartPoint]:
    paid_orders = _paid_orders_subquery(db)

    query = (
        db.query(
            func.date(paid_orders.c.paid_at).label("sale_date"),
            func.sum(OrderItem.quantity).label("quantity"),
        )
        .join(paid_orders, paid_orders.c.order_id == OrderItem.order_id)
        .filter(OrderItem.product_id == product_id)
    )

    if start_date is not None:
        query = query.filter(paid_orders.c.paid_at >= start_date)
    if end_date is not None:
        query = query.filter(paid_orders.c.paid_at <= end_date)

    rows = query.group_by(func.date(paid_orders.c.paid_at)).order_by("sale_date").all()
    return [
        ProductSalesChartPoint(date=str(row.sale_date), quantity=int(row.quantity or 0))
        for row in rows
    ]


@router.get("/sales-by-customer", response_model=list[CustomerSalesChartPoint])
def sales_by_customer(
    db: Session = Depends(get_db),
    customer_id: int = Query(...),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
) -> list[CustomerSalesChartPoint]:
    paid_orders = _paid_orders_subquery(db)

    query = db.query(
        func.date(paid_orders.c.paid_at).label("sale_date"),
        func.sum(paid_orders.c.total).label("value"),
    ).filter(paid_orders.c.customer_id == customer_id)

    if start_date is not None:
        query = query.filter(paid_orders.c.paid_at >= start_date)
    if end_date is not None:
        query = query.filter(paid_orders.c.paid_at <= end_date)

    rows = query.group_by(func.date(paid_orders.c.paid_at)).order_by("sale_date").all()
    return [
        CustomerSalesChartPoint(date=str(row.sale_date), value=row.value or Decimal("0"))
        for row in rows
    ]


@router.get("/top-products", response_model=list[TopProductChartItem])
def top_products(
    db: Session = Depends(get_db),
    limit: int = Query(default=10, ge=1, le=50),
) -> list[TopProductChartItem]:
    stats_subq = _product_stats_subquery(db)

    rows = (
        db.query(
            Product.id,
            Product.number,
            Product.name,
            func.coalesce(stats_subq.c.units_sold, 0).label("units_sold"),
            func.coalesce(stats_subq.c.revenue, Decimal("0")).label("revenue"),
        )
        .outerjoin(stats_subq, stats_subq.c.product_id == Product.id)
        .order_by(
            func.coalesce(stats_subq.c.units_sold, 0).desc(),
            func.coalesce(stats_subq.c.revenue, Decimal("0")).desc(),
        )
        .limit(limit)
        .all()
    )

    return [
        TopProductChartItem(
            product_id=row.id,
            product_number=row.number,
            product_name=row.name,
            units_sold=row.units_sold,
            revenue=row.revenue,
        )
        for row in rows
    ]


@router.get("/total-sales", response_model=list[CustomerSalesChartPoint])
def total_sales_over_time(
    db: Session = Depends(get_db),
    granularity: str = Query(default="month", pattern="^(day|month|year)$"),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
) -> list[CustomerSalesChartPoint]:
    paid_orders = _paid_orders_subquery(db)

    if granularity == "day":
        period_expr = func.date(paid_orders.c.paid_at)
    elif granularity == "year":
        period_expr = func.to_char(paid_orders.c.paid_at, "YYYY")
    else:
        period_expr = func.to_char(paid_orders.c.paid_at, "YYYY-MM")

    query = db.query(
        period_expr.label("period"),
        func.sum(paid_orders.c.total).label("value"),
    )

    if start_date is not None:
        query = query.filter(paid_orders.c.paid_at >= start_date)
    if end_date is not None:
        query = query.filter(paid_orders.c.paid_at <= end_date)

    rows = query.group_by("period").order_by("period").all()
    return [
        CustomerSalesChartPoint(date=str(row.period), value=row.value or Decimal("0"))
        for row in rows
    ]


@router.get("/product-revenue-share", response_model=list[ProductRevenueShareItem])
def product_revenue_share(db: Session = Depends(get_db)) -> list[ProductRevenueShareItem]:
    stats_subq = _product_stats_subquery(db)

    rows = (
        db.query(
            Product.id,
            Product.number,
            Product.name,
            func.coalesce(stats_subq.c.revenue, Decimal("0")).label("revenue"),
        )
        .join(stats_subq, stats_subq.c.product_id == Product.id)
        .filter(stats_subq.c.revenue > 0)
        .order_by(func.coalesce(stats_subq.c.revenue, Decimal("0")).desc())
        .all()
    )

    total_revenue = sum((row.revenue for row in rows), Decimal("0"))
    if total_revenue == 0:
        return []

    return [
        ProductRevenueShareItem(
            product_id=row.id,
            product_number=row.number,
            product_name=row.name,
            revenue=row.revenue,
            percentage=(row.revenue / total_revenue * Decimal("100")).quantize(Decimal("0.01")),
        )
        for row in rows
    ]
