from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import asc, desc
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db
from app.models import Order
from app.schemas.common import OrderSortField, SortOrder
from app.schemas.order import OrderCreate, OrderResponse, OrderStatusUpdate
from app.services.order_service import OrderServiceError, create_order, delete_order, update_order_status

router = APIRouter(prefix="/orders", tags=["orders"])

SORT_COLUMNS = {
    "created_at": Order.created_at,
    "total": Order.total,
    "number": Order.number,
    "status": Order.status,
}


@router.get("", response_model=list[OrderResponse])
def list_orders(
    db: Session = Depends(get_db),
    customer_id: int | None = Query(default=None),
    min_total: Decimal | None = Query(default=None, ge=0),
    max_total: Decimal | None = Query(default=None, ge=0),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    sort_by: OrderSortField = Query(default="created_at"),
    sort_order: SortOrder = Query(default=SortOrder.DESC),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10000, ge=1, le=10000),
) -> list[Order]:
    query = db.query(Order).options(
        joinedload(Order.items),
        joinedload(Order.status_history),
    )

    if customer_id is not None:
        query = query.filter(Order.customer_id == customer_id)
    if min_total is not None:
        query = query.filter(Order.total >= min_total)
    if max_total is not None:
        query = query.filter(Order.total <= max_total)
    if start_date is not None:
        query = query.filter(Order.created_at >= start_date)
    if end_date is not None:
        query = query.filter(Order.created_at <= end_date)

    sort_column = SORT_COLUMNS[sort_by]
    ordering = asc(sort_column) if sort_order == SortOrder.ASC else desc(sort_column)
    return query.order_by(ordering).offset(skip).limit(limit).all()


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order_endpoint(data: OrderCreate, db: Session = Depends(get_db)) -> Order:
    try:
        return create_order(db, data)
    except OrderServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(order_id: int, db: Session = Depends(get_db)) -> Order:
    order = (
        db.query(Order)
        .options(joinedload(Order.items), joinedload(Order.status_history))
        .filter(Order.id == order_id)
        .first()
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.patch("/{order_id}/status", response_model=OrderResponse)
def update_status(
    order_id: int, data: OrderStatusUpdate, db: Session = Depends(get_db)
) -> Order:
    try:
        return update_order_status(db, order_id, data)
    except OrderServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_order_endpoint(order_id: int, db: Session = Depends(get_db)) -> None:
    try:
        delete_order(db, order_id)
    except OrderServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
