from app.core.database import SessionLocal
from sqlalchemy import text
import sys

db = SessionLocal()

# Query otimizada: pegar apenas os primeiros registros de historico que precisam correcao
# Usando LATERAL JOIN para evitar subquery por pedido
print("Buscando registros para correcao...", flush=True)

# Primeiro, contar quantos pedidos existem
count_result = db.execute(text("SELECT count(*) FROM orders"))
total_orders = count_result.scalar()
print(f"Total de pedidos: {total_orders}", flush=True)

# Pegar IDs de pedidos em lotes
batch_size = 100
fixed = 0
processed = 0

for offset in range(0, total_orders, batch_size):
    orders_result = db.execute(text("""
        SELECT o.id, o.number, o.created_at
        FROM orders o
        ORDER BY o.id
        OFFSET :offset LIMIT :limit
    """), {"offset": offset, "limit": batch_size})
    
    for order_row in orders_result.fetchall():
        order_id, number, created_at = order_row
        
        # Pegar o primeiro registro de historico
        hist_result = db.execute(text("""
            SELECT id, changed_at FROM order_status_history
            WHERE order_id = :oid
            ORDER BY id ASC LIMIT 1
        """), {"oid": order_id})
        hist = hist_result.fetchone()
        
        if hist and hist[1].date() != created_at.date():
            db.execute(text("UPDATE order_status_history SET changed_at = :ca WHERE id = :id"),
                       {"ca": created_at, "id": hist[0]})
            db.commit()
            fixed += 1
            if fixed % 10 == 0:
                print(f"  Corrigidos: {fixed} (ultimo: #{number})", flush=True)
        
        processed += 1
    
    if processed % 100 == 0:
        print(f"  Processados: {processed}/{total_orders}", flush=True)

print(f"\nProcessados: {processed}")
print(f"Corrigidos: {fixed}")
db.close()
