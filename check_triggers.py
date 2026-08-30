from app.core.database import SessionLocal, engine
from app.models import Order, OrderStatusHistory
from sqlalchemy import text

db = SessionLocal()

# Verificar se há algum trigger na tabela orders
result = db.execute(text("""
    SELECT tg.tgname, pg_get_triggerdef(tg.oid)
    FROM pg_trigger tg
    JOIN pg_class t ON tg.tgrelid = t.oid
    WHERE t.relname = 'orders'
"""))
print("Triggers na tabela orders:")
for row in result:
    print(f"  {row[0]}: {row[1]}")

# Verificar um pedido específico e seu histórico
order = db.query(Order).filter(Order.number == 947).first()
print(f"\nPedido #{order.number}:")
print(f"  created_at: {order.created_at}")
print(f"  updated_at: {order.updated_at}")
print(f"  status: {order.status}")
print(f"  Histórico de status:")
for h in order.status_history:
    print(f"    {h.status}: {h.changed_at}")

db.close()
