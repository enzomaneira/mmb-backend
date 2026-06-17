# MonthlyRevenue table removed — revenue is now computed directly from
# order_items joined with order_status_history (PAID orders only).
# See app/api/routes/revenue.py for the computed queries.
