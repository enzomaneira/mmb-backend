from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CustomerBase(BaseModel):
    number: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None)


class CustomerCreate(CustomerBase):
    created_at: datetime | None = None  # optional manual override


class CustomerUpdate(BaseModel):
    number: int | None = Field(default=None, ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None)
    created_at: datetime | None = None  # optional manual override


class CustomerResponse(CustomerBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    # Computed aggregates — injected by the route, not stored on the model
    total_orders: int = 0
    total_spent: Decimal = Decimal("0")
    total_units: int = 0
    created_at: datetime
    updated_at: datetime


class CustomerWithOrdersResponse(CustomerResponse):
    orders: list["OrderSummaryResponse"] = []


from app.schemas.order import OrderSummaryResponse  # noqa: E402

CustomerWithOrdersResponse.model_rebuild()
