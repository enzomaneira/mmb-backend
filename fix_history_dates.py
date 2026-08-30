from app.core.database import SessionLocal
from app.models import Order, OrderStatusHistory
from sqlalchemy import text

db = SessionLocal()

# Para cada pedido, verificar se o primeiro registro de histórico tem changed_at != created_at
# Se sim, corrigir o changed_at do primeiro registro para ser igual a created_at
orders = db.query(Order).all()
fixed = 0
for order in orders:
    first_history = (
        db.query(OrderStatusHistory)
        .filter(OrderStatusHistory.order_id == order.id)
        .order_by(OrderStatusHistory.changed_at.asc())
        .first()
    )
    if first_history and first_history.changed_at != order.created_at:
        print(f"Corrigindo pedido #{order.number}: history changed_at {first_history.changed_at} -> {order.created_at}")
        first_history.changed_at = order.created_at
        fixed += 1

db.commit()
print(f"\nTotal de pedidos corrigidos: {fixed}")
db.close()
