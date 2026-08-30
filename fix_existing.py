from app.core.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

# Abordagem simples: pegar todos os IDs de pedidos que precisam correcao
# e corrigir um por um
print("Buscando pedidos com historico inconsistente...")
sys_out = text("""
    SELECT DISTINCT o.id, o.number, o.created_at
    FROM orders o
    JOIN order_status_history h ON h.order_id = o.id
    WHERE h.changed_at::date != o.created_at::date
    ORDER BY o.id
""")

result = db.execute(sys_out)
records = result.fetchall()
print(f"Encontrados {len(records)} pedidos para corrigir")

fixed = 0
for rec in records:
    order_id, number, created_at = rec
    # Pegar o ID do primeiro registro de historico (menor ID)
    first_result = db.execute(text("""
        SELECT id, changed_at FROM order_status_history
        WHERE order_id = :oid
        ORDER BY id ASC LIMIT 1
    """), {"oid": order_id})
    first = first_result.fetchone()
    if first and first[1].date() != created_at.date():
        db.execute(text("UPDATE order_status_history SET changed_at = :ca WHERE id = :id"),
                   {"ca": created_at, "id": first[0]})
        db.commit()
        fixed += 1
        if fixed % 50 == 0:
            print(f"  Corrigidos: {fixed}")

print(f"\nTotal corrigido: {fixed}")
db.close()
