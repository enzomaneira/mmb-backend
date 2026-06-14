from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


class MessageResponse(BaseModel):
    message: str


class PaginationParams(BaseModel):
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=200)


CustomerSortField = Literal["name", "total_orders", "total_spent", "total_units"]
ProductSortField = Literal["name", "price", "units_sold", "revenue", "stock_quantity"]
OrderSortField = Literal["created_at", "total", "number", "status"]
