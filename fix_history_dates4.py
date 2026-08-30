from app.core.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

# Abordagem simples: para cada pedido, pegar o menor changed_at do historico
# e atualizar para ser igual ao created_at do pedido
# Fazer em lotes para evitar timeout

# Primeiro contar quantos precisam correcao
count_result = db.execute(text("""
    SELECT COUNT(*) FROM (
        SELECT h.id
        FROM order_status_history h
        JOIN orders o ON h.order_id = o.id
        WHERE h.changed_at::date != o.created_at::date
          AND h.id = (
              SELECT min(h2.id) FROM order_status_history h2
              WHERE h2.order_id = h.order_id
          )
    ) AS sub
"""))
count = count_result.scalar()
print(f"Registros a corrigir: {count}")

# Atualizar em lotes de 50
batch_size = 50
fixed = 0
while True:
    # Pegar IDs dos registros que precisam correcao
    result = db.execute(text("""
        SELECT h.id, o.created_at
        FROM order_status_history h
        JOIN orders o ON h.order_id = o.id
        WHERE h.changed_at::date != o.created_at::date
          AND h.id = (
              SELECT min(h2.id) FROM order_status_history h2
              WHERE h2.order_id = h.order_id
          )
        LIMIT :batch
    """), {"batch": batch_size})
    
    records = result.fetchall()
    if not records:
        break
    
    for rec in records:
        hist_id, created_at = rec
        db.execute(text("UPDATE order_status_history SET changed_at = :ca WHERE id = :id"), {"ca": created_at, "id": hist_id})
    
    db.commit()
    fixed += len(records)
    print(f"Corrigidos ate agora: {fixed}")

print(f"\nTotal corrigido: {fixed}")
db.close()
