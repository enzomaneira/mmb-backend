from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import asc, desc, func
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db
from app.models import Customer, Order, OrderItem, OrderStatus, OrderStatusHistory
from app.schemas.common import SortOrder
from app.schemas.customer import (
    CustomerCreate,
    CustomerResponse,
    CustomerUpdate,
    CustomerWithOrdersResponse,
)

router = APIRouter(prefix="/customers", tags=["customers"])

# ---------------------------------------------------------------------------
# Aggregate helper — returns { customer_id -> {total_orders, total_spent, total_units} }
#
# Strategy:
#   • total_orders + total_spent  → aggregate on Order directly (no OrderItem join)
#     This avoids multiplying Order.total by the number of items in each order.
#   • total_units                 → aggregate on OrderItem separately.
#
# Only orders that have ever reached the PAID status are counted.
# ---------------------------------------------------------------------------

def _build_stats_map(db: Session, customer_ids: list[int]) -> dict:
    if not customer_ids:
        return {}

    # Sub-select of all PAID order ids
    paid_order_ids = (
        db.query(OrderStatusHistory.order_id)
        .filter(OrderStatusHistory.status == OrderStatus.PAID)
        .subquery()
    )

    # --- 1) orders count + total_spent (aggregate on Order, no OrderItem) ---
    order_rows = (
        db.query(
            Order.customer_id,
            func.count(Order.id).label("total_orders"),
            func.coalesce(func.sum(Order.total), Decimal("0")).label("total_spent"),
        )
        .join(paid_order_ids, paid_order_ids.c.order_id == Order.id)
        .filter(Order.customer_id.in_(customer_ids))
        .group_by(Order.customer_id)
        .all()
    )

    stats: dict = {}
    for row in order_rows:
        stats[row.customer_id] = {
            "total_orders": row.total_orders,
            "total_spent": row.total_spent,
            "total_units": 0,
        }

    # --- 2) total_units (aggregate on OrderItem, joined to PAID orders) ---
    units_rows = (
        db.query(
            Order.customer_id,
            func.coalesce(func.sum(OrderItem.quantity), 0).label("total_units"),
        )
        .join(paid_order_ids, paid_order_ids.c.order_id == Order.id)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .filter(Order.customer_id.in_(customer_ids))
        .group_by(Order.customer_id)
        .all()
    )

    for row in units_rows:
        if row.customer_id in stats:
            stats[row.customer_id]["total_units"] = row.total_units
        else:
            stats[row.customer_id] = {
                "total_orders": 0,
                "total_spent": Decimal("0"),
                "total_units": row.total_units,
            }

    return stats


def _enrich_customer(customer: Customer, stats_map: dict) -> CustomerResponse:
    stats = stats_map.get(customer.id, {"total_orders": 0, "total_spent": Decimal("0"), "total_units": 0})
    data = CustomerResponse.model_validate(customer)
    data.total_orders = stats["total_orders"]
    data.total_spent = stats["total_spent"]
    data.total_units = stats["total_units"]
    return data


def _enrich_customer_with_orders(customer: Customer, stats_map: dict) -> CustomerWithOrdersResponse:
    stats = stats_map.get(customer.id, {"total_orders": 0, "total_spent": Decimal("0"), "total_units": 0})
    data = CustomerWithOrdersResponse.model_validate(customer)
    data.total_orders = stats["total_orders"]
    data.total_spent = stats["total_spent"]
    data.total_units = stats["total_units"]
    return data


# ---------------------------------------------------------------------------
# Subquery used only for sorting by aggregate columns in list_customers
# ---------------------------------------------------------------------------

def _build_sort_subquery(db: Session):
    paid_order_ids = (
        db.query(OrderStatusHistory.order_id)
        .filter(OrderStatusHistory.status == OrderStatus.PAID)
        .subquery()
    )

    # For sorting we join Order → paid_order_ids only (no OrderItem).
    # total_units sort is approximate (based on order count * avg) but acceptable;
    # for exact total_units sorting we'd need a separate subquery — done below.
    orders_subq = (
        db.query(
            Order.customer_id.label("customer_id"),
            func.count(Order.id).label("total_orders"),
            func.coalesce(func.sum(Order.total), Decimal("0")).label("total_spent"),
        )
        .join(paid_order_ids, paid_order_ids.c.order_id == Order.id)
        .group_by(Order.customer_id)
        .subquery()
    )

    units_subq = (
        db.query(
            Order.customer_id.label("customer_id"),
            func.coalesce(func.sum(OrderItem.quantity), 0).label("total_units"),
        )
        .join(paid_order_ids, paid_order_ids.c.order_id == Order.id)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .group_by(Order.customer_id)
        .subquery()
    )

    return orders_subq, units_subq


@router.get("", response_model=list[CustomerResponse])
def list_customers(
    db: Session = Depends(get_db),
    search: str | None = Query(default=None),
    sort_by: str = Query(default="name", pattern="^(name|number|total_orders|total_spent|total_units)$"),
    sort_order: SortOrder = Query(default=SortOrder.ASC),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10000, ge=1, le=10000),
) -> list[CustomerResponse]:
    orders_subq, units_subq = _build_sort_subquery(db)

    query = (
        db.query(Customer)
        .outerjoin(orders_subq, orders_subq.c.customer_id == Customer.id)
        .outerjoin(units_subq, units_subq.c.customer_id == Customer.id)
    )

    if search:
        query = query.filter(Customer.name.ilike(f"%{search}%"))

    sort_col_map = {
        "name": Customer.name,
        "number": Customer.number,
        "total_orders": func.coalesce(orders_subq.c.total_orders, 0),
        "total_spent": func.coalesce(orders_subq.c.total_spent, Decimal("0")),
        "total_units": func.coalesce(units_subq.c.total_units, 0),
    }
    sort_col = sort_col_map[sort_by]
    ordering = asc(sort_col) if sort_order == SortOrder.ASC else desc(sort_col)
    customers = query.order_by(ordering).offset(skip).limit(limit).all()

    ids = [c.id for c in customers]
    stats_map = _build_stats_map(db, ids)
    return [_enrich_customer(c, stats_map) for c in customers]


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(data: CustomerCreate, db: Session = Depends(get_db)) -> CustomerResponse:
    if db.query(Customer).filter(Customer.number == data.number).first():
        raise HTTPException(status_code=409, detail="Customer number already exists")

    dump = data.model_dump(exclude={"created_at"})
    customer = Customer(**dump)
    if data.created_at is not None:
        customer.created_at = data.created_at
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return _enrich_customer(customer, {})


@router.get("/{customer_id}", response_model=CustomerWithOrdersResponse)
def get_customer(customer_id: int, db: Session = Depends(get_db)) -> CustomerWithOrdersResponse:
    customer = (
        db.query(Customer)
        .options(joinedload(Customer.orders))
        .filter(Customer.id == customer_id)
        .first()
    )
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    stats_map = _build_stats_map(db, [customer_id])
    return _enrich_customer_with_orders(customer, stats_map)


@router.get("/by-number/{number}", response_model=CustomerWithOrdersResponse)
def get_customer_by_number(number: int, db: Session = Depends(get_db)) -> CustomerWithOrdersResponse:
    customer = (
        db.query(Customer)
        .options(joinedload(Customer.orders))
        .filter(Customer.number == number)
        .first()
    )
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    stats_map = _build_stats_map(db, [customer.id])
    return _enrich_customer_with_orders(customer, stats_map)


@router.patch("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: int, data: CustomerUpdate, db: Session = Depends(get_db)
) -> CustomerResponse:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    updates = data.model_dump(exclude_unset=True)
    if "number" in updates and updates["number"] != customer.number:
        existing = db.query(Customer).filter(Customer.number == updates["number"]).first()
        if existing:
            raise HTTPException(status_code=409, detail="Customer number already exists")

    for field, value in updates.items():
        setattr(customer, field, value)

    db.commit()
    db.refresh(customer)
    # Return with real stats (not an empty map)
    stats_map = _build_stats_map(db, [customer_id])
    return _enrich_customer(customer, stats_map)


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(customer_id: int, db: Session = Depends(get_db)) -> None:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    order_count = db.query(Order).filter(Order.customer_id == customer_id).count()
    if order_count > 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete customer with existing orders",
        )

    db.delete(customer)
    db.commit()
