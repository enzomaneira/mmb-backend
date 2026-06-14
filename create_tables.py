from app.core.database import engine
from app.models.customer import Customer
from app.models.product import Product
from app.models.order import Order
from app.models.revenue import MonthlyRevenue
from sqlalchemy import text

# Importar o Base de algum dos models
from app.core.database import Base

# Dropar enums que possam estar presos
with engine.connect() as conn:
    conn.execute(text("DROP TYPE IF EXISTS product_type_enum CASCADE"))
    conn.execute(text("DROP TYPE IF EXISTS order_status_enum CASCADE"))
    conn.execute(text("DROP TYPE IF EXISTS product_status_enum CASCADE"))
    conn.commit()

# Criar todas as tabelas
Base.metadata.create_all(bind=engine)
print("Tabelas criadas com sucesso!")