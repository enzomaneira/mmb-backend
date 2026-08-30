from app.core.database import SessionLocal
from app.models import Order, OrderStatusHistory

db = SessionLocal()

# Verificar pedidos recentes (numero > 940)
orders = db.query(Order).filter(Order.number > 940).order_by(Order.number.desc()).limit(10).all()
for o in orders:
    print(f"\nPedido #{o.number}:")
    print(f"  created_at: {o.created_at}")
    print(f"  updated_at: {o.updated_at}")
    print(f"  status: {o.status}")
    print(f"  HistÃ³rico:")
    for h in o.status_history:
        print(f"    {h.status}: {h.changed_at}")

db.close()
