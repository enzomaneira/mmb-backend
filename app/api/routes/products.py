from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import OrderItem, Product
from app.models.enums import ProductType
from app.schemas.common import ProductSortField, SortOrder
from app.schemas.product import ProductCreate, ProductResponse, ProductStockUpdate, ProductUpdate

router = APIRouter(prefix="/products", tags=["products"])

SORT_COLUMNS = {
    "name": Product.name,
    "price": Product.price,
    "units_sold": Product.units_sold,
    "revenue": Product.revenue,
    "stock_quantity": Product.stock_quantity,
}


@router.get("", response_model=list[ProductResponse])
def list_products(
    db: Session = Depends(get_db),
    search: str | None = Query(default=None),
    product_type: ProductType | None = Query(default=None),
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    min_units_sold: int | None = Query(default=None, ge=0),
    max_units_sold: int | None = Query(default=None, ge=0),
    sort_by: ProductSortField = Query(default="name"),
    sort_order: SortOrder = Query(default=SortOrder.ASC),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10000, ge=1, le=10000),
) -> list[Product]:
    query = db.query(Product)

    if search:
        query = query.filter(Product.name.ilike(f"%{search}%"))
    if product_type:
        query = query.filter(Product.product_type == product_type)
    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)
    if min_units_sold is not None:
        query = query.filter(Product.units_sold >= min_units_sold)
    if max_units_sold is not None:
        query = query.filter(Product.units_sold <= max_units_sold)

    sort_column = SORT_COLUMNS[sort_by]
    ordering = asc(sort_column) if sort_order == SortOrder.ASC else desc(sort_column)
    return query.order_by(ordering).offset(skip).limit(limit).all()


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(data: ProductCreate, db: Session = Depends(get_db)) -> Product:
    if db.query(Product).filter(Product.number == data.number).first():
        raise HTTPException(status_code=409, detail="Product number already exists")

    product = Product(**data.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: int, db: Session = Depends(get_db)) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.get("/by-number/{number}", response_model=ProductResponse)
def get_product_by_number(number: int, db: Session = Depends(get_db)) -> Product:
    product = db.query(Product).filter(Product.number == number).first()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.patch("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: int, data: ProductUpdate, db: Session = Depends(get_db)
) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    updates = data.model_dump(exclude_unset=True)
    if "number" in updates and updates["number"] != product.number:
        existing = db.query(Product).filter(Product.number == updates["number"]).first()
        if existing:
            raise HTTPException(status_code=409, detail="Product number already exists")

    for field, value in updates.items():
        setattr(product, field, value)

    db.commit()
    db.refresh(product)
    return product


@router.patch("/{product_id}/stock", response_model=ProductResponse)
def update_product_stock(
    product_id: int, data: ProductStockUpdate, db: Session = Depends(get_db)
) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    product.stock_quantity = data.stock_quantity
    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: int, db: Session = Depends(get_db)) -> None:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    if db.query(OrderItem).filter(OrderItem.product_id == product_id).count() > 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete product referenced in orders",
        )

    db.delete(product)
    db.commit()
