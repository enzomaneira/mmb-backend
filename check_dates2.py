from app.core.database import SessionLocal
from app.models import Order, OrderStatusHistory
from sqlalchemy import text

db = SessionLocal()

# Verificar pedidos onde created_at difere do primeiro changed_at do histórico
result = db.execute(text("""
    SELECT o.number, o.created_at, o.updated_at, o.status,
           h.changed_at as first_history_date, h.status as first_history_status
    FROM orders o
    LEFT JOIN (
        SELECT DISTINCT ON (order_id) order_id, changed_at, status
        FROM order_status_history
        ORDER BY order_id, changed_at ASC
    ) h ON h.order_id = o.id
    ORDER BY o.created_at DESC
    LIMIT 20
"""))
print(f"{'Num':>5} | {'created_at':>28} | {'updated_at':>28} | {'status':>12} | {'first_history':>28} | {'first_status':>12}")
print("-" * 130)
for row in result:
    print(f"{row[0]:>5} | {str(row[1]):>28} | {str(row[2]):>28} | {str(row[3]):>12} | {str(row[4]):>28} | {str(row[5]):>12}")

db.close()
