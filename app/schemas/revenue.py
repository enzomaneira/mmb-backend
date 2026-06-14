from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class MonthlyRevenueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    year: int
    month: int
    value: Decimal


class RevenueChartPoint(BaseModel):
    period: str
    value: Decimal


class ProductSalesChartPoint(BaseModel):
    date: str
    quantity: int


class CustomerSalesChartPoint(BaseModel):
    date: str
    value: Decimal


class TopProductChartItem(BaseModel):
    product_id: int
    product_number: int
    product_name: str
    units_sold: int
    revenue: Decimal


class ProductRevenueShareItem(BaseModel):
    product_id: int
    product_number: int
    product_name: str
    revenue: Decimal
    percentage: Decimal
