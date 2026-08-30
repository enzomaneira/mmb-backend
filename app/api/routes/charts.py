from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import Customer, Order, OrderItem, OrderStatus, OrderStatusHistory, Product
from app.models.enums import ProductType
from app.schemas.revenue import (
    AvgProductionTimeItem,
    CustomerSalesChartPoint,
    ProductionTimeItem,
    ProductRevenueShareItem,
    ProductSalesChartPoint,
    TopCustomerChartItem,
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


def _product_stats_subquery(
    db: Session,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> "subquery":
    """Subquery of units_sold and revenue per product from PAID orders.

    Optionally filtered by paid_at date range.
    """
    paid_orders = (
        db.query(
            Order.id.label("order_id"),
            OrderStatusHistory.changed_at.label("paid_at"),
        )
        .join(OrderStatusHistory, OrderStatusHistory.order_id == Order.id)
        .filter(OrderStatusHistory.status == OrderStatus.PAID)
    )
    if start_date is not None:
        paid_orders = paid_orders.filter(OrderStatusHistory.changed_at >= start_date)
    if end_date is not None:
        paid_orders = paid_orders.filter(OrderStatusHistory.changed_at <= end_date)
    paid_subq = paid_orders.subquery()

    return (
        db.query(
            OrderItem.product_id.label("product_id"),
            func.coalesce(func.sum(OrderItem.quantity), 0).label("units_sold"),
            func.coalesce(
                func.sum(OrderItem.unit_price * OrderItem.quantity), Decimal("0")
            ).label("revenue"),
        )
        .join(paid_subq, paid_subq.c.order_id == OrderItem.order_id)
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
    product_type: ProductType | None = Query(default=None),
    product_id: int | None = Query(default=None),
) -> list[CustomerSalesChartPoint]:
    paid_orders = _paid_orders_subquery(db)

    if product_type is not None or product_id is not None:
        # Sum only the matching items' subtotals, not the full order total
        query = (
            db.query(
                func.date(paid_orders.c.paid_at).label("sale_date"),
                func.sum(OrderItem.unit_price * OrderItem.quantity).label("value"),
            )
            .join(paid_orders, paid_orders.c.order_id == OrderItem.order_id)
            .filter(paid_orders.c.customer_id == customer_id)
        )
        if product_type is not None:
            query = query.join(Product, Product.id == OrderItem.product_id).filter(
                Product.product_type == product_type
            )
        if product_id is not None:
            query = query.filter(OrderItem.product_id == product_id)
    else:
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
    product_type: ProductType | None = Query(default=None),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
) -> list[TopProductChartItem]:
    stats_subq = _product_stats_subquery(db, start_date, end_date)

    query = (
        db.query(
            Product.id,
            Product.number,
            Product.name,
            func.coalesce(stats_subq.c.units_sold, 0).label("units_sold"),
            func.coalesce(stats_subq.c.revenue, Decimal("0")).label("revenue"),
        )
        .outerjoin(stats_subq, stats_subq.c.product_id == Product.id)
    )

    if product_type is not None:
        query = query.filter(Product.product_type == product_type)

    rows = (
        query
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
    product_type: ProductType | None = Query(default=None),
    product_id: int | None = Query(default=None),
) -> list[CustomerSalesChartPoint]:
    paid_orders = _paid_orders_subquery(db)

    if product_type is not None or product_id is not None:
        # Sum only the matching items' subtotals, not the full order total
        base_query = (
            db.query(
                paid_orders.c.paid_at.label("paid_at"),
                (OrderItem.unit_price * OrderItem.quantity).label("item_total"),
            )
            .join(paid_orders, paid_orders.c.order_id == OrderItem.order_id)
        )
        if product_type is not None:
            base_query = base_query.join(
                Product, Product.id == OrderItem.product_id
            ).filter(Product.product_type == product_type)
        if product_id is not None:
            base_query = base_query.filter(OrderItem.product_id == product_id)
        filtered_subq = base_query.subquery()

        if granularity == "day":
            period_expr = func.date(filtered_subq.c.paid_at)
        elif granularity == "year":
            period_expr = func.to_char(filtered_subq.c.paid_at, "YYYY")
        else:
            period_expr = func.to_char(filtered_subq.c.paid_at, "YYYY-MM")

        query = db.query(
            period_expr.label("period"),
            func.sum(filtered_subq.c.item_total).label("value"),
        )
    else:
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
        if product_type is not None or product_id is not None:
            query = query.filter(filtered_subq.c.paid_at >= start_date)
        else:
            query = query.filter(paid_orders.c.paid_at >= start_date)
    if end_date is not None:
        if product_type is not None or product_id is not None:
            query = query.filter(filtered_subq.c.paid_at <= end_date)
        else:
            query = query.filter(paid_orders.c.paid_at <= end_date)

    rows = query.group_by("period").order_by("period").all()
    return [
        CustomerSalesChartPoint(date=str(row.period), value=row.value or Decimal("0"))
        for row in rows
    ]


@router.get("/product-revenue-share", response_model=list[ProductRevenueShareItem])
def product_revenue_share(
    db: Session = Depends(get_db),
    product_type: ProductType | None = Query(default=None),
) -> list[ProductRevenueShareItem]:
    stats_subq = _product_stats_subquery(db)

    query = (
        db.query(
            Product.id,
            Product.number,
            Product.name,
            func.coalesce(stats_subq.c.revenue, Decimal("0")).label("revenue"),
        )
        .join(stats_subq, stats_subq.c.product_id == Product.id)
        .filter(stats_subq.c.revenue > 0)
    )

    if product_type is not None:
        query = query.filter(Product.product_type == product_type)

    rows = query.order_by(
        func.coalesce(stats_subq.c.revenue, Decimal("0")).desc()
    ).all()

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


@router.get("/top-customers", response_model=list[TopCustomerChartItem])
def top_customers(
    db: Session = Depends(get_db),
    limit: int = Query(default=10, ge=1, le=50),
    year: int | None = Query(default=None),
) -> list[TopCustomerChartItem]:
    """Top customers by total spent, optionally filtered by year of payment."""
    paid_orders = _paid_orders_subquery(db)

    if year is not None:
        query = (
            db.query(
                Customer.id,
                Customer.number,
                Customer.name,
                func.coalesce(func.sum(paid_orders.c.total), Decimal("0")).label("total_spent"),
                func.count(paid_orders.c.order_id).label("total_orders"),
            )
            .join(paid_orders, paid_orders.c.customer_id == Customer.id)
            .filter(func.extract("year", paid_orders.c.paid_at) == year)
            .group_by(Customer.id, Customer.number, Customer.name)
            .order_by(func.coalesce(func.sum(paid_orders.c.total), Decimal("0")).desc())
            .limit(limit)
        )
    else:
        query = (
            db.query(
                Customer.id,
                Customer.number,
                Customer.name,
                func.coalesce(func.sum(paid_orders.c.total), Decimal("0")).label("total_spent"),
                func.count(paid_orders.c.order_id).label("total_orders"),
            )
            .outerjoin(paid_orders, paid_orders.c.customer_id == Customer.id)
            .group_by(Customer.id, Customer.number, Customer.name)
            .order_by(func.coalesce(func.sum(paid_orders.c.total), Decimal("0")).desc())
            .limit(limit)
        )

    rows = query.all()

    return [
        TopCustomerChartItem(
            customer_id=row.id,
            customer_number=row.number,
            customer_name=row.name,
            total_spent=row.total_spent or Decimal("0"),
            total_orders=row.total_orders,
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Production time: difference between IN_PROGRESS and READY status events.
# ---------------------------------------------------------------------------

def _production_time_subquery(db: Session):
    """Build a subquery pairing each order's IN_PROGRESS and READY timestamps.

    Only orders that have BOTH an IN_PROGRESS and a READY event are included.
    """
    in_progress_events = (
        db.query(
            OrderStatusHistory.order_id.label("order_id"),
            OrderStatusHistory.changed_at.label("started_at"),
        )
        .filter(OrderStatusHistory.status == OrderStatus.IN_PROGRESS)
        .subquery()
    )
    ready_events = (
        db.query(
            OrderStatusHistory.order_id.label("order_id"),
            OrderStatusHistory.changed_at.label("completed_at"),
        )
        .filter(OrderStatusHistory.status == OrderStatus.READY)
        .subquery()
    )

    return (
        db.query(
            Order.id.label("order_id"),
            Order.number.label("order_number"),
            in_progress_events.c.started_at.label("started_at"),
            ready_events.c.completed_at.label("completed_at"),
        )
        .join(in_progress_events, in_progress_events.c.order_id == Order.id)
        .join(ready_events, ready_events.c.order_id == Order.id)
        .filter(ready_events.c.completed_at > in_progress_events.c.started_at)
        .subquery()
    )


@router.get("/production-time", response_model=list[ProductionTimeItem])
def production_time(
    db: Session = Depends(get_db),
    product_id: int | None = Query(default=None),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
) -> list[ProductionTimeItem]:
    """List production times (in days) for orders, optionally filtered by product and/or date range.

    Production time = READY timestamp − IN_PROGRESS timestamp.
    """
    prod_subq = _production_time_subquery(db)

    query = db.query(
        prod_subq.c.order_id,
        prod_subq.c.order_number,
        prod_subq.c.started_at,
        prod_subq.c.completed_at,
        OrderItem.product_id,
        Product.name.label("product_name"),
    ).join(OrderItem, OrderItem.order_id == prod_subq.c.order_id, isouter=True).join(
        Product, Product.id == OrderItem.product_id, isouter=True
    )

    if product_id is not None:
        query = query.filter(OrderItem.product_id == product_id)
    if start_date is not None:
        query = query.filter(prod_subq.c.started_at >= start_date)
    if end_date is not None:
        query = query.filter(prod_subq.c.completed_at <= end_date)

    # Deduplicate: one row per order (take the first product item if multiple)
    rows = query.order_by(prod_subq.c.completed_at.desc()).all()

    seen = set()
    results = []
    for row in rows:
        if row.order_id in seen:
            continue
        seen.add(row.order_id)
        # Calculate days as float
        started = row.started_at
        completed = row.completed_at
        if started and completed:
            delta = completed - started
            days = round(delta.total_seconds() / 86400.0, 1)
        else:
            days = 0.0
        results.append(
            ProductionTimeItem(
                order_id=row.order_id,
                order_number=row.order_number,
                product_id=row.product_id,
                product_name=row.product_name,
                started_at=str(started),
                completed_at=str(completed),
                production_days=days,
            )
        )
    return results


@router.get("/avg-production-time", response_model=list[AvgProductionTimeItem])
def avg_production_time(
    db: Session = Depends(get_db),
) -> list[AvgProductionTimeItem]:
    """Average production time (in days) grouped by year, based on READY completion year."""
    prod_subq = _production_time_subquery(db)

    # Extract year from completed_at and compute average production time in days
    year_expr = func.extract("year", prod_subq.c.completed_at).label("year")
    # Use EXTRACT(EPOCH FROM (completed - started)) / 86400 to get days as float
    epoch_expr = func.extract("epoch", prod_subq.c.completed_at - prod_subq.c.started_at)
    avg_days_expr = (func.avg(epoch_expr) / 86400.0).label("avg_days")
    count_expr = func.count(prod_subq.c.order_id).label("order_count")

    rows = (
        db.query(year_expr, avg_days_expr, count_expr)
        .group_by(year_expr)
        .order_by(year_expr)
        .all()
    )

    return [
        AvgProductionTimeItem(
            year=int(row.year),
            avg_days=round(float(row.avg_days or 0), 1),
            order_count=int(row.order_count),
        )
        for row in rows
    ]
