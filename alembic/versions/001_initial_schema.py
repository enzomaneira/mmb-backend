"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

product_type_enum = sa.Enum(
    "FELT",
    "CLOTH",
    "CHRISTMAS",
    "SCHOOL",
    "DECORATION",
    "KEEPSAKE",
    "COSTUME",
    "EASTER",
    "PUPPETS",
    "MISC",
    "REPAIR",
    "QUIET_BOOK",
    "TOYS",
    "STATIONERY",
    name="product_type_enum",
)

order_status_enum = sa.Enum(
    "PENDING",
    "IN_PROGRESS",
    "READY",
    "DELIVERED",
    "PAID",
    "CANCELED",
    name="order_status_enum",
)


def upgrade() -> None:
    product_type_enum.create(op.get_bind(), checkfirst=True)
    order_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("total_orders", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_spent", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_units", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("number"),
    )
    op.create_index("ix_customers_name", "customers", ["name"])
    op.create_index("ix_customers_number", "customers", ["number"])

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("product_type", product_type_enum, nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("stock_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("units_sold", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("revenue", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("number"),
    )
    op.create_index("ix_products_name", "products", ["name"])
    op.create_index("ix_products_number", "products", ["number"])

    op.create_table(
        "monthly_revenue",
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("value", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("year", "month"),
    )

    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("status", order_status_enum, nullable=False, server_default="PENDING"),
        sa.Column("total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("number"),
    )
    op.create_index("ix_orders_created_at", "orders", ["created_at"])
    op.create_index("ix_orders_customer_id", "orders", ["customer_id"])
    op.create_index("ix_orders_number", "orders", ["number"])
    op.create_index("ix_orders_status", "orders", ["status"])

    op.create_table(
        "order_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_order_items_product_id", "order_items", ["product_id"])

    op.create_table(
        "order_status_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("status", order_status_enum, nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("order_status_history")
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("monthly_revenue")
    op.drop_table("products")
    op.drop_table("customers")
    order_status_enum.drop(op.get_bind(), checkfirst=True)
    product_type_enum.drop(op.get_bind(), checkfirst=True)
