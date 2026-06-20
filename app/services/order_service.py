from sqlalchemy.orm import Session, joinedload

from app.models import Order, OrderItem, OrderStatus, OrderStatusHistory, Product
from app.schemas.order import OrderCreate, OrderStatusUpdate, OrderUpdate


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

        unit_price = item_data.unit_price if item_data.unit_price is not None else product.price
        order_item = OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=item_data.quantity,
            unit_price=unit_price,
        )
        db.add(order_item)
        total += unit_price * item_data.quantity

    order.total = total
    history = OrderStatusHistory(order_id=order.id, status=data.status)
    db.add(history)

    db.commit()
    db.refresh(order)
    return get_order_or_404(db, order.id)


def update_order_status(db: Session, order_id: int, data: OrderStatusUpdate) -> Order:
    order = get_order_or_404(db, order_id)

    if order.status == data.status and data.changed_at is None:
        return order

    order.status = data.status
    history = OrderStatusHistory(order_id=order.id, status=data.status)
    if data.changed_at is not None:
        history.changed_at = data.changed_at
    db.add(history)

    db.commit()
    return get_order_or_404(db, order.id)


def update_order(db: Session, order_id: int, data: OrderUpdate) -> Order:
    order = get_order_or_404(db, order_id)

    if data.customer_id is not None:
        from app.models import Customer
        customer = db.get(Customer, data.customer_id)
        if customer is None:
            raise OrderServiceError("Customer not found", status_code=404)
        order.customer_id = data.customer_id

    if data.items is not None:
        # Remove existing items
        for item in list(order.items):
            db.delete(item)
        db.flush()

        # Validate no duplicate products
        product_ids = [i.product_id for i in data.items]
        if len(product_ids) != len(set(product_ids)):
            raise OrderServiceError("Duplicate products in the same order are not allowed")

        total = 0
        for item_data in data.items:
            product = db.get(Product, item_data.product_id)
            if product is None:
                raise OrderServiceError(f"Product {item_data.product_id} not found", status_code=404)
            unit_price = item_data.unit_price if item_data.unit_price is not None else product.price
            order_item = OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=item_data.quantity,
                unit_price=unit_price,
            )
            db.add(order_item)
            total += unit_price * item_data.quantity

        order.total = total

    db.commit()
    return get_order_or_404(db, order.id)


def delete_order(db: Session, order_id: int) -> None:
    order = get_order_or_404(db, order_id)
    db.delete(order)
    db.commit()
