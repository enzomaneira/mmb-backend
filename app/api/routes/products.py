from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import asc, desc, func
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import OrderItem, OrderStatus, OrderStatusHistory, Product
from app.models.enums import ProductType
from app.schemas.common import SortOrder
from app.schemas.product import ProductCreate, ProductResponse, ProductStockUpdate, ProductUpdate

router = APIRouter(prefix="/products", tags=["products"])


# ---------------------------------------------------------------------------
# Helper: build a stats map { product_id -> {units_sold, revenue} }
# for a list of product IDs — only counting PAID orders.
# ---------------------------------------------------------------------------

def _get_stats_map(db: Session, product_ids: list[int]) -> dict:
    if not product_ids:
        return {}

    paid_order_ids = (
        db.query(OrderStatusHistory.order_id)
        .filter(OrderStatusHistory.status == OrderStatus.PAID)
        .subquery()
    )

    rows = (
        db.query(
            OrderItem.product_id,
            func.coalesce(func.sum(OrderItem.quantity), 0).label("units_sold"),
            func.coalesce(
                func.sum(OrderItem.unit_price * OrderItem.quantity), Decimal("0")
            ).label("revenue"),
        )
        .join(paid_order_ids, paid_order_ids.c.order_id == OrderItem.order_id)
        .filter(OrderItem.product_id.in_(product_ids))
        .group_by(OrderItem.product_id)
        .all()
    )

    return {
        row.product_id: {
            "units_sold": row.units_sold or 0,
            "revenue": row.revenue or Decimal("0"),
        }
        for row in rows
    }


def _enrich(product: Product, stats_map: dict) -> ProductResponse:
    stats = stats_map.get(product.id, {"units_sold": 0, "revenue": Decimal("0")})
    data = ProductResponse.model_validate(product)
    data.units_sold = stats["units_sold"]
    data.revenue = stats["revenue"]
    return data


@router.get("", response_model=list[ProductResponse])
def list_products(
    db: Session = Depends(get_db),
    search: str | None = Query(default=None),
    product_type: ProductType | None = Query(default=None),
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    min_units_sold: int | None = Query(default=None, ge=0),
    max_units_sold: int | None = Query(default=None, ge=0),
    sort_by: str = Query(default="name", pattern="^(name|number|price|units_sold|revenue|stock_quantity)$"),
    sort_order: SortOrder = Query(default=SortOrder.ASC),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10000, ge=1, le=10000),
) -> list[ProductResponse]:
    # Build stats subquery for joining/sorting
    paid_order_ids = (
        db.query(OrderStatusHistory.order_id)
        .filter(OrderStatusHistory.status == OrderStatus.PAID)
        .subquery()
    )
    stats_subq = (
        db.query(
            OrderItem.product_id.label("product_id"),
            func.coalesce(func.sum(OrderItem.quantity), 0).label("units_sold"),
            func.coalesce(
                func.sum(OrderItem.unit_price * OrderItem.quantity), Decimal("0")
            ).label("revenue"),
        )
        .join(paid_order_ids, paid_order_ids.c.order_id == OrderItem.order_id)
        .group_by(OrderItem.product_id)
        .subquery()
    )

    query = db.query(Product).outerjoin(stats_subq, stats_subq.c.product_id == Product.id)

    if search:
        query = query.filter(Product.name.ilike(f"%{search}%"))
    if product_type:
        query = query.filter(Product.product_type == product_type)
    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)
    if min_units_sold is not None:
        query = query.filter(func.coalesce(stats_subq.c.units_sold, 0) >= min_units_sold)
    if max_units_sold is not None:
        query = query.filter(func.coalesce(stats_subq.c.units_sold, 0) <= max_units_sold)

    sort_col_map = {
        "name": Product.name,
        "number": Product.number,
        "price": Product.price,
        "stock_quantity": Product.stock_quantity,
        "units_sold": func.coalesce(stats_subq.c.units_sold, 0),
        "revenue": func.coalesce(stats_subq.c.revenue, Decimal("0")),
    }
    sort_col = sort_col_map[sort_by]
    ordering = asc(sort_col) if sort_order == SortOrder.ASC else desc(sort_col)
    products = query.order_by(ordering).offset(skip).limit(limit).all()

    ids = [p.id for p in products]
    stats_map = _get_stats_map(db, ids)
    return [_enrich(p, stats_map) for p in products]


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(data: ProductCreate, db: Session = Depends(get_db)) -> ProductResponse:
    if db.query(Product).filter(Product.number == data.number).first():
        raise HTTPException(status_code=409, detail="Product number already exists")

    dump = data.model_dump(exclude={"created_at"})
    product = Product(**dump)
    if data.created_at is not None:
        product.created_at = data.created_at
    db.add(product)
    db.commit()
    db.refresh(product)
    return _enrich(product, {})


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: int, db: Session = Depends(get_db)) -> ProductResponse:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return _enrich(product, _get_stats_map(db, [product_id]))


@router.get("/by-number/{number}", response_model=ProductResponse)
def get_product_by_number(number: int, db: Session = Depends(get_db)) -> ProductResponse:
    product = db.query(Product).filter(Product.number == number).first()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return _enrich(product, _get_stats_map(db, [product.id]))


@router.patch("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: int, data: ProductUpdate, db: Session = Depends(get_db)
) -> ProductResponse:
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
    return _enrich(product, _get_stats_map(db, [product_id]))


@router.patch("/{product_id}/stock", response_model=ProductResponse)
def update_product_stock(
    product_id: int, data: ProductStockUpdate, db: Session = Depends(get_db)
) -> ProductResponse:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    product.stock_quantity = data.stock_quantity
    db.commit()
    db.refresh(product)
    return _enrich(product, _get_stats_map(db, [product_id]))


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
