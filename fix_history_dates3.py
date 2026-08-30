from app.core.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

# Primeiro, identificar os IDs dos registros que precisam ser corrigidos
result = db.execute(text("""
    SELECT h.id, h.order_id, o.created_at, h.changed_at
    FROM order_status_history h
    JOIN orders o ON h.order_id = o.id
    WHERE h.changed_at != o.created_at
      AND h.id = (
          SELECT h2.id FROM order_status_history h2
          WHERE h2.order_id = h.order_id
          ORDER BY h2.changed_at ASC
          LIMIT 1
      )
"""))
records = result.fetchall()
print(f"Registros a corrigir: {len(records)}")

for rec in records:
    hist_id, order_id, created_at, old_changed_at = rec
    db.execute(text("UPDATE order_status_history SET changed_at = :ca WHERE id = :id"), {"ca": created_at, "id": hist_id})
    db.commit()
    print(f"  Corrigido registro {hist_id} (pedido {order_id}): {old_changed_at} -> {created_at}")

db.close()
print("ConcluÃ­do!")
