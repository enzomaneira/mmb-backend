from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CustomerBase(BaseModel):
    number: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=1000)


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    number: int | None = Field(default=None, ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=1000)


class CustomerResponse(CustomerBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    total_orders: int
    total_spent: Decimal
    total_units: int
    created_at: datetime
    updated_at: datetime


class CustomerWithOrdersResponse(CustomerResponse):
    orders: list["OrderSummaryResponse"] = []


from app.schemas.order import OrderSummaryResponse  # noqa: E402

CustomerWithOrdersResponse.model_rebuild()
