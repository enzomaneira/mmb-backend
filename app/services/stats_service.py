from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Customer, MonthlyRevenue, Order, OrderItem, Product


def apply_paid_stats(db: Session, order: Order, paid_at: datetime) -> None:
    customer = db.get(Customer, order.customer_id)
    if customer is None:
        raise ValueError("Customer not found")

    customer.total_orders += 1
    customer.total_spent += order.total

    for item in order.items:
        product = db.get(Product, item.product_id)
        if product is None:
            raise ValueError(f"Product {item.product_id} not found")

        subtotal = item.unit_price * item.quantity
        customer.total_units += item.quantity
        product.units_sold += item.quantity
        product.revenue += subtotal

    _update_monthly_revenue(db, paid_at.year, paid_at.month, order.total)


def reverse_paid_stats(db: Session, order: Order, paid_at: datetime) -> None:
    customer = db.get(Customer, order.customer_id)
    if customer is None:
        raise ValueError("Customer not found")

    customer.total_orders = max(0, customer.total_orders - 1)
    customer.total_spent = max(Decimal("0"), customer.total_spent - order.total)

    for item in order.items:
        product = db.get(Product, item.product_id)
        if product is None:
            raise ValueError(f"Product {item.product_id} not found")

        subtotal = item.unit_price * item.quantity
        customer.total_units = max(0, customer.total_units - item.quantity)
        product.units_sold = max(0, product.units_sold - item.quantity)
        product.revenue = max(Decimal("0"), product.revenue - subtotal)

    _update_monthly_revenue(db, paid_at.year, paid_at.month, -order.total)


def _update_monthly_revenue(db: Session, year: int, month: int, delta: Decimal) -> None:
    revenue = db.get(MonthlyRevenue, (year, month))
    if revenue is None:
        revenue = MonthlyRevenue(year=year, month=month, value=max(Decimal("0"), delta))
        db.add(revenue)
        return

    revenue.value = max(Decimal("0"), revenue.value + delta)


def get_paid_timestamp(order: Order) -> datetime | None:
    for entry in reversed(order.status_history):
        if entry.status.value == "PAID":
            return entry.changed_at
    return None


def calculate_order_total(items: list[OrderItem]) -> Decimal:
    return sum((item.unit_price * item.quantity for item in items), Decimal("0"))
