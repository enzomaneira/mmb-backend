import sys
from app.core.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

# Atualizar diretamente: para cada registro de historico, se o changed_at 
# for diferente do created_at do pedido, e for o primeiro registro, atualizar
# Vamos fazer de forma muito simples: pegar todos os pedidos e seus primeiros historicos

try:
    # Query simples: pegar IDs e datas
    result = db.execute(text("""
        SELECT o.id as order_id, o.number, o.created_at,
               (SELECT min(h.id) FROM order_status_history h WHERE h.order_id = o.id) as first_hist_id,
               (SELECT min(h.changed_at) FROM order_status_history h WHERE h.order_id = o.id) as first_hist_date
        FROM orders o
        WHERE EXISTS (
            SELECT 1 FROM order_status_history h 
            WHERE h.order_id = o.id 
              AND h.changed_at::date != o.created_at::date
        )
        LIMIT 500
    """))
    records = result.fetchall()
    print(f"Encontrados {len(records)} pedidos para corrigir")
    sys.stdout.flush()
    
    for rec in records:
        order_id, number, created_at, hist_id, hist_date = rec
        if hist_id and created_at:
            db.execute(text("UPDATE order_status_history SET changed_at = :ca WHERE id = :id"), 
                       {"ca": created_at, "id": hist_id})
            db.commit()
            print(f"  #{number}: {hist_date} -> {created_at}")
            sys.stdout.flush()
    
    print("Concluido!")
except Exception as e:
    print(f"Erro: {e}")
    db.rollback()
finally:
    db.close()
