from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import asc, desc
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db
from app.models import Customer, Order
from app.schemas.common import CustomerSortField, SortOrder
from app.schemas.customer import (
    CustomerCreate,
    CustomerResponse,
    CustomerUpdate,
    CustomerWithOrdersResponse,
)
router = APIRouter(prefix="/customers", tags=["customers"])

SORT_COLUMNS = {
    "name": Customer.name,
    "total_orders": Customer.total_orders,
    "total_spent": Customer.total_spent,
    "total_units": Customer.total_units,
}


@router.get("", response_model=list[CustomerResponse])
def list_customers(
    db: Session = Depends(get_db),
    search: str | None = Query(default=None),
    sort_by: CustomerSortField = Query(default="name"),
    sort_order: SortOrder = Query(default=SortOrder.ASC),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[Customer]:
    query = db.query(Customer)
    if search:
        query = query.filter(Customer.name.ilike(f"%{search}%"))

    sort_column = SORT_COLUMNS[sort_by]
    ordering = asc(sort_column) if sort_order == SortOrder.ASC else desc(sort_column)
    return query.order_by(ordering).offset(skip).limit(limit).all()


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(data: CustomerCreate, db: Session = Depends(get_db)) -> Customer:
    if db.query(Customer).filter(Customer.number == data.number).first():
        raise HTTPException(status_code=409, detail="Customer number already exists")

    customer = Customer(**data.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.get("/{customer_id}", response_model=CustomerWithOrdersResponse)
def get_customer(customer_id: int, db: Session = Depends(get_db)) -> Customer:
    customer = (
        db.query(Customer)
        .options(joinedload(Customer.orders))
        .filter(Customer.id == customer_id)
        .first()
    )
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.get("/by-number/{number}", response_model=CustomerWithOrdersResponse)
def get_customer_by_number(number: int, db: Session = Depends(get_db)) -> Customer:
    customer = (
        db.query(Customer)
        .options(joinedload(Customer.orders))
        .filter(Customer.number == number)
        .first()
    )
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.patch("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: int, data: CustomerUpdate, db: Session = Depends(get_db)
) -> Customer:
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
    return customer


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
