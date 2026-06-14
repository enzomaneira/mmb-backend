from datetime import datetime, timezone

from sqlalchemy.orm import Session, joinedload

from app.models import Order, OrderItem, OrderStatus, OrderStatusHistory, Product
from app.schemas.order import OrderCreate, OrderStatusUpdate
from app.services.stats_service import apply_paid_stats, get_paid_timestamp, reverse_paid_stats


class OrderServiceError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def get_order_or_404(db: Session, order_id: int) -> Order:
    order = (
        db.query(Order)
        .options(
            joinedload(Order.items),
            joinedload(Order.status_history),
        )
        .filter(Order.id == order_id)
        .first()
    )
    if order is None:
        raise OrderServiceError("Order not found", status_code=404)
    return order


def create_order(db: Session, data: OrderCreate) -> Order:
    if db.query(Order).filter(Order.number == data.number).first():
        raise OrderServiceError("Order number already exists", status_code=409)

    order = Order(
        number=data.number,
        customer_id=data.customer_id,
        status=data.status,
        total=0,
    )
    db.add(order)
    db.flush()

    total = 0
    for item_data in data.items:
        product = db.get(Product, item_data.product_id)
        if product is None:
            raise OrderServiceError(f"Product {item_data.product_id} not found", status_code=404)

        order_item = OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=item_data.quantity,
            unit_price=product.price,
        )
        db.add(order_item)
        total += product.price * item_data.quantity

    order.total = total
    history = OrderStatusHistory(order_id=order.id, status=data.status)
    db.add(history)

    db.flush()

    if data.status == OrderStatus.PAID:
        paid_at = datetime.now(timezone.utc)
        history.changed_at = paid_at
        order = get_order_or_404(db, order.id)
        apply_paid_stats(db, order, paid_at)

    db.commit()
    db.refresh(order)
    return get_order_or_404(db, order.id)


def update_order_status(db: Session, order_id: int, data: OrderStatusUpdate) -> Order:
    order = get_order_or_404(db, order_id)
    old_status = order.status
    new_status = data.status

    if old_status == new_status:
        return order

    order.status = new_status
    history = OrderStatusHistory(order_id=order.id, status=new_status)
    db.add(history)
    db.flush()

    if old_status == OrderStatus.PAID and new_status != OrderStatus.PAID:
        paid_at = get_paid_timestamp(order)
        if paid_at is not None:
            reverse_paid_stats(db, order, paid_at)

    if new_status == OrderStatus.PAID and old_status != OrderStatus.PAID:
        apply_paid_stats(db, order, history.changed_at)

    db.commit()
    return get_order_or_404(db, order.id)


def delete_order(db: Session, order_id: int) -> None:
    order = get_order_or_404(db, order_id)

    if order.status == OrderStatus.PAID:
        paid_at = get_paid_timestamp(order)
        if paid_at is not None:
            reverse_paid_stats(db, order, paid_at)

    db.delete(order)
    db.commit()
