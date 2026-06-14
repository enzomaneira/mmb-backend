from fastapi import APIRouter

from app.api.routes import charts, customers, orders, products, revenue

api_router = APIRouter()
api_router.include_router(customers.router)
api_router.include_router(products.router)
api_router.include_router(orders.router)
api_router.include_router(revenue.router)
api_router.include_router(charts.router)
