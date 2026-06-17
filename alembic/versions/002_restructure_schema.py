"""restructure schema — remove denormalized columns, drop monthly_revenue,
add db-level constraints and indexes

Revision ID: 002
Revises: 001
Create Date: 2026-06-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # customers: remove denormalized aggregate columns, change notes to Text
    # ------------------------------------------------------------------
    op.drop_column("customers", "total_orders")
    op.drop_column("customers", "total_spent")
    op.drop_column("customers", "total_units")
    op.alter_column(
        "customers",
        "notes",
        existing_type=sa.String(length=1000),
        type_=sa.Text(),
        existing_nullable=True,
    )

    # ------------------------------------------------------------------
    # products: remove denormalized aggregate columns
    # ------------------------------------------------------------------
    op.drop_column("products", "units_sold")
    op.drop_column("products", "revenue")

    # ------------------------------------------------------------------
    # order_items: add DB-level unique constraint (order_id, product_id)
    #              add index on order_id for faster lookups
    # ------------------------------------------------------------------
    op.create_unique_constraint(
        "uq_order_items_order_product", "order_items", ["order_id", "product_id"]
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"])

    # ------------------------------------------------------------------
    # order_status_history: add index on order_id
    #                        add index on changed_at for time-range queries
    # ------------------------------------------------------------------
    op.create_index("ix_order_status_history_order_id", "order_status_history", ["order_id"])
    op.create_index("ix_order_status_history_changed_at", "order_status_history", ["changed_at"])

    # ------------------------------------------------------------------
    # Drop the monthly_revenue cache table — now computed live from orders
    # ------------------------------------------------------------------
    op.drop_table("monthly_revenue")


def downgrade() -> None:
    # Recreate monthly_revenue
    op.create_table(
        "monthly_revenue",
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("value", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("year", "month"),
    )

    # Remove order_status_history indexes
    op.drop_index("ix_order_status_history_changed_at", "order_status_history")
    op.drop_index("ix_order_status_history_order_id", "order_status_history")

    # Remove order_items constraint and index
    op.drop_index("ix_order_items_order_id", "order_items")
    op.drop_constraint("uq_order_items_order_product", "order_items", type_="unique")

    # Restore products columns
    op.add_column("products", sa.Column("units_sold", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("products", sa.Column("revenue", sa.Numeric(12, 2), nullable=False, server_default="0"))

    # Restore customers columns and revert notes to String(1000)
    op.alter_column(
        "customers",
        "notes",
        existing_type=sa.Text(),
        type_=sa.String(length=1000),
        existing_nullable=True,
    )
    op.add_column("customers", sa.Column("total_units", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("customers", sa.Column("total_spent", sa.Numeric(12, 2), nullable=False, server_default="0"))
    op.add_column("customers", sa.Column("total_orders", sa.Integer(), nullable=False, server_default="0"))
