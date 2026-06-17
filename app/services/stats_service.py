"""
stats_service.py — computed aggregates via SQL.

All stats (customer totals, product sales, revenue) are derived live from
the source-of-truth tables (order_items + order_status_history) instead of
being stored as redundant denormalized columns that can drift out of sync.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Order, OrderItem, OrderStatus, OrderStatusHistory


# ---------------------------------------------------------------------------
# Helpers used by routes / services
# ---------------------------------------------------------------------------

def get_paid_timestamp(order: Order) -> datetime | None:
    """Return the most recent PAID timestamp from an order's status history."""
    for entry in reversed(order.status_history):
        if entry.status.value == "PAID":
            return entry.changed_at
    return None


def calculate_order_total(items: list[OrderItem]) -> Decimal:
    """Sum unit_price * quantity for a list of OrderItem objects."""
    return sum((item.unit_price * item.quantity for item in items), Decimal("0"))


# ---------------------------------------------------------------------------
# Customer aggregates (computed on demand)
# ---------------------------------------------------------------------------

def get_customer_stats(db: Session, customer_id: int) -> dict:
    """
    Returns total_orders, total_spent, total_units for a customer
    by aggregating only PAID orders directly from the database.
    """
    paid_order_ids = (
        db.query(OrderStatusHistory.order_id)
        .filter(OrderStatusHistory.status == OrderStatus.PAID)
        .subquery()
    )

    result = (
        db.query(
            func.count(func.distinct(Order.id)).label("total_orders"),
            func.coalesce(func.sum(Order.total), Decimal("0")).label("total_spent"),
            func.coalesce(func.sum(OrderItem.quantity), 0).label("total_units"),
        )
        .join(paid_order_ids, paid_order_ids.c.order_id == Order.id)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .filter(Order.customer_id == customer_id)
        .one()
    )

    return {
        "total_orders": result.total_orders or 0,
        "total_spent": result.total_spent or Decimal("0"),
        "total_units": result.total_units or 0,
    }


# ---------------------------------------------------------------------------
# Product aggregates (computed on demand)
# ---------------------------------------------------------------------------

def get_product_stats(db: Session, product_id: int) -> dict:
    """
    Returns units_sold and revenue for a product
    by aggregating only PAID orders directly from the database.
    """
    paid_order_ids = (
        db.query(OrderStatusHistory.order_id)
        .filter(OrderStatusHistory.status == OrderStatus.PAID)
        .subquery()
    )

    result = (
        db.query(
            func.coalesce(func.sum(OrderItem.quantity), 0).label("units_sold"),
            func.coalesce(
                func.sum(OrderItem.unit_price * OrderItem.quantity), Decimal("0")
            ).label("revenue"),
        )
        .join(paid_order_ids, paid_order_ids.c.order_id == OrderItem.order_id)
        .filter(OrderItem.product_id == product_id)
        .one()
    )

    return {
        "units_sold": result.units_sold or 0,
        "revenue": result.revenue or Decimal("0"),
    }


# ---------------------------------------------------------------------------
# Monthly revenue (computed on demand)
# ---------------------------------------------------------------------------

def get_monthly_revenue(
    db: Session,
    start_year: int | None = None,
    start_month: int | None = None,
    end_year: int | None = None,
    end_month: int | None = None,
) -> list[dict]:
    """
    Returns monthly revenue aggregated from PAID orders.
    Each row: { year, month, value }
    """
    paid_subq = (
        db.query(
            Order.total,
            OrderStatusHistory.changed_at.label("paid_at"),
        )
        .join(OrderStatusHistory, OrderStatusHistory.order_id == Order.id)
        .filter(OrderStatusHistory.status == OrderStatus.PAID)
        .subquery()
    )

    query = db.query(
        func.extract("year", paid_subq.c.paid_at).label("year"),
        func.extract("month", paid_subq.c.paid_at).label("month"),
        func.sum(paid_subq.c.total).label("value"),
    )

    if start_year is not None and start_month is not None:
        query = query.filter(
            func.extract("year", paid_subq.c.paid_at) * 100
            + func.extract("month", paid_subq.c.paid_at)
            >= start_year * 100 + start_month
        )
    if end_year is not None and end_month is not None:
        query = query.filter(
            func.extract("year", paid_subq.c.paid_at) * 100
            + func.extract("month", paid_subq.c.paid_at)
            <= end_year * 100 + end_month
        )

    rows = query.group_by("year", "month").order_by("year", "month").all()

    return [
        {
            "year": int(row.year),
            "month": int(row.month),
            "value": row.value or Decimal("0"),
        }
        for row in rows
    ]
