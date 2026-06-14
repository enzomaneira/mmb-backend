from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.models.enums import OrderStatus


class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(ge=1)


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    quantity: int
    unit_price: Decimal

    @computed_field
    @property
    def subtotal(self) -> Decimal:
        return self.unit_price * self.quantity


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
