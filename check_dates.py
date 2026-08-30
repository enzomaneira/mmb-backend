from app.core.database import SessionLocal
from app.models import Order

db = SessionLocal()
orders = db.query(Order).order_by(Order.created_at.desc()).limit(10).all()
for o in orders:
    print(f"#{o.number} created={o.created_at} updated={o.updated_at} status={o.status}")
db.close()
