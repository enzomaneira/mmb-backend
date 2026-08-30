from app.core.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

# Corrigir com uma única query SQL: atualizar o primeiro registro de histórico
# de cada pedido para ter changed_at = orders.created_at
result = db.execute(text("""
    UPDATE order_status_history h
    SET changed_at = o.created_at
    FROM orders o
    WHERE h.order_id = o.id
      AND h.changed_at != o.created_at
      AND h.id = (
          SELECT h2.id FROM order_status_history h2
          WHERE h2.order_id = h.order_id
          ORDER BY h2.changed_at ASC
          LIMIT 1
      )
"""))
db.commit()
print(f"Registros corrigidos: {result.rowcount}")
db.close()
