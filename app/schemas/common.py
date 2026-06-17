from enum import Enum

from pydantic import BaseModel, Field


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


class MessageResponse(BaseModel):
    message: str


class PaginationParams(BaseModel):
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=10000, ge=1, le=10000)


CustomerSortField = str   # validated via Query pattern in the route
ProductSortField = str    # validated via Query pattern in the route
OrderSortField = str      # validated via Query pattern in the route
