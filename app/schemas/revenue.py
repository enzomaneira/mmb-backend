from decimal import Decimal

from pydantic import BaseModel


class MonthlyRevenueResponse(BaseModel):
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


class TopCustomerChartItem(BaseModel):
    customer_id: int
    customer_number: int
    customer_name: str
    total_spent: Decimal
    total_orders: int


class ProductionTimeItem(BaseModel):
    """Production time for a single order (in days)."""
    order_id: int
    order_number: int
    product_id: int | None
    product_name: str | None
    started_at: str
    completed_at: str
    production_days: float


class AvgProductionTimeItem(BaseModel):
    """Average production time grouped by year."""
    year: int
    avg_days: float
    order_count: int
