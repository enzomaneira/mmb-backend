from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class OrderPaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    paid_at: datetime | None = None  # optional manual override
    note: str | None = None


class OrderPaymentUpdate(BaseModel):
    amount: Decimal | None = Field(default=None, gt=0)
    paid_at: datetime | None = None
    note: str | None = None


class OrderPaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    amount: Decimal
    paid_at: datetime
    note: str | None
    created_at: datetime
