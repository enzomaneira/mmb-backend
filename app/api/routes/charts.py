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
    rows = (
        db.query(Product)
        .order_by(Product.units_sold.desc(), Product.revenue.desc())
        .limit(limit)
        .all()
    )
    return [
        TopProductChartItem(
            product_id=product.id,
            product_number=product.number,
            product_name=product.name,
            units_sold=product.units_sold,
            revenue=product.revenue,
        )
        for product in rows
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
    rows = db.query(Product).filter(Product.revenue > 0).order_by(Product.revenue.desc()).all()
    total_revenue = sum((product.revenue for product in rows), Decimal("0"))

    if total_revenue == 0:
        return []

    return [
        ProductRevenueShareItem(
            product_id=product.id,
            product_number=product.number,
            product_name=product.name,
            revenue=product.revenue,
            percentage=(product.revenue / total_revenue * Decimal("100")).quantize(Decimal("0.01")),
        )
        for product in rows
    ]
