from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ProductType


class ProductBase(BaseModel):
    number: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    product_type: ProductType
    price: Decimal = Field(ge=0, decimal_places=2)


class ProductCreate(ProductBase):
    stock_quantity: int = Field(default=0, ge=0)
    created_at: datetime | None = None  # optional manual override


class ProductUpdate(BaseModel):
    number: int | None = Field(default=None, ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    product_type: ProductType | None = None
    price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    stock_quantity: int | None = Field(default=None, ge=0)
    created_at: datetime | None = None  # optional manual override


class ProductResponse(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_quantity: int
    # Computed aggregates — injected by the route, not stored on the model
    units_sold: int = 0
    revenue: Decimal = Decimal("0")
    created_at: datetime
    updated_at: datetime


class ProductStockUpdate(BaseModel):
    stock_quantity: int = Field(ge=0)
