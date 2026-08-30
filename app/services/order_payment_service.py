from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Order, OrderPayment
from app.schemas.order_payment import OrderPaymentCreate, OrderPaymentUpdate


class OrderPaymentServiceError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def get_order_or_404(db: Session, order_id: int) -> Order:
    order = db.get(Order, order_id)
    if order is None:
        raise OrderPaymentServiceError("Order not found", status_code=404)
    return order


def list_payments(db: Session, order_id: int) -> list[OrderPayment]:
    get_order_or_404(db, order_id)
    return (
        db.query(OrderPayment)
        .filter(OrderPayment.order_id == order_id)
        .order_by(OrderPayment.paid_at)
        .all()
    )


def create_payment(db: Session, order_id: int, data: OrderPaymentCreate) -> OrderPayment:
    get_order_or_404(db, order_id)
    payment = OrderPayment(
        order_id=order_id,
        amount=data.amount,
        note=data.note,
    )
    if data.paid_at is not None:
        payment.paid_at = data.paid_at
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def update_payment(
    db: Session, order_id: int, payment_id: int, data: OrderPaymentUpdate
) -> OrderPayment:
    get_order_or_404(db, order_id)
    payment = (
        db.query(OrderPayment)
        .filter(
            OrderPayment.id == payment_id,
            OrderPayment.order_id == order_id,
        )
        .first()
    )
    if payment is None:
        raise OrderPaymentServiceError("Payment not found", status_code=404)

    if data.amount is not None:
        payment.amount = data.amount
    if data.paid_at is not None:
        payment.paid_at = data.paid_at
    if data.note is not None:
        payment.note = data.note

    db.commit()
    db.refresh(payment)
    return payment


def delete_payment(db: Session, order_id: int, payment_id: int) -> None:
    get_order_or_404(db, order_id)
    payment = (
        db.query(OrderPayment)
        .filter(
            OrderPayment.id == payment_id,
            OrderPayment.order_id == order_id,
        )
        .first()
    )
    if payment is None:
        raise OrderPaymentServiceError("Payment not found", status_code=404)
    db.delete(payment)
    db.commit()


def get_paid_amount(db: Session, order_id: int) -> Decimal:
    """Return the sum of all payments for an order."""
    get_order_or_404(db, order_id)
    payments = (
        db.query(OrderPayment)
        .filter(OrderPayment.order_id == order_id)
        .all()
    )
    return sum((p.amount for p in payments), Decimal(0))
