from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from app.models.enums import OrderStatus


class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(ge=1)
    unit_price: Decimal | None = None


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    product_name: str | None = None
    product_number: int | None = None
    quantity: int
    unit_price: Decimal

    @computed_field
    @property
    def subtotal(self) -> Decimal:
        return self.unit_price * self.quantity

    @model_validator(mode="before")
    @classmethod
    def extract_product_fields(cls, data: object) -> object:
        # When building from an ORM object, pull product name/number from the relationship
        product = getattr(data, "product", None)
        if product is not None:
            # Convert ORM object to dict-like for Pydantic, injecting product fields
            return {
                "id": data.id,  # type: ignore[union-attr]
                "product_id": data.product_id,  # type: ignore[union-attr]
                "product_name": product.name,
                "product_number": product.number,
                "quantity": data.quantity,  # type: ignore[union-attr]
                "unit_price": data.unit_price,  # type: ignore[union-attr]
            }
        return data


class OrderStatusHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: OrderStatus
    changed_at: datetime


class OrderBase(BaseModel):
    number: int = Field(ge=1)
    customer_id: int


class OrderCreate(OrderBase):
    items: list[OrderItemCreate] = Field(min_length=1)
    status: OrderStatus = OrderStatus.PENDING

    @field_validator("items")
    @classmethod
    def validate_items(cls, items: list[OrderItemCreate]) -> list[OrderItemCreate]:
        product_ids = [item.product_id for item in items]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("Duplicate products in the same order are not allowed")
        return items


class OrderStatusUpdate(BaseModel):
    status: OrderStatus
    changed_at: datetime | None = None  # optional manual date override


class OrderItemUpdate(BaseModel):
    product_id: int
    quantity: int = Field(ge=1)
    unit_price: Decimal | None = None


class OrderUpdate(BaseModel):
    customer_id: int | None = None
    items: list[OrderItemUpdate] | None = None


class OrderSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    number: int
    customer_id: int
    status: OrderStatus
    total: Decimal
    created_at: datetime


class OrderResponse(OrderSummaryResponse):
    items: list[OrderItemResponse] = []
    status_history: list[OrderStatusHistoryResponse] = []
    updated_at: datetime
