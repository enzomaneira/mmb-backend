from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from app.models.enums import OrderStatus
from app.schemas.order_payment import OrderPaymentResponse


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
    status: OrderStatus = OrderStatus.IN_PROGRESS
    created_at: datetime | None = None  # optional manual override



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
    created_at: datetime | None = None  # optional manual override


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
    payments: list[OrderPaymentResponse] = []
    updated_at: datetime

    @computed_field
    @property
    def paid_amount(self) -> Decimal:
        return sum((p.amount for p in self.payments), Decimal(0))
