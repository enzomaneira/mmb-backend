"""drop legacy denormalized columns from products and customers

The initial schema (001) stored denormalized aggregates directly on the tables.
Migration 002 was supposed to remove them, but the production database was
populated before 002 ever ran, so those columns still exist there.

This migration drops them safely with IF EXISTS so it is idempotent — it can
run on databases where 002 already ran (columns are already gone) as well as
on the production database where they still exist.

Revision ID: 003
Revises: 002
Create Date: 2026-06-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _drop_column_if_exists(table: str, column: str) -> None:
    """Drop a column only if it exists (idempotent)."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = [c["name"] for c in inspector.get_columns(table)]
    if column in cols:
        op.drop_column(table, column)


def upgrade() -> None:
    # products — remove legacy denormalized aggregate columns
    _drop_column_if_exists("products", "units_sold")
    _drop_column_if_exists("products", "revenue")

    # customers — remove legacy denormalized aggregate columns
    _drop_column_if_exists("customers", "total_orders")
    _drop_column_if_exists("customers", "total_spent")
    _drop_column_if_exists("customers", "total_units")


def downgrade() -> None:
    # Restore products columns
    op.add_column(
        "products",
        sa.Column("units_sold", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "products",
        sa.Column("revenue", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )

    # Restore customers columns
    op.add_column(
        "customers",
        sa.Column("total_orders", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "customers",
        sa.Column("total_spent", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "customers",
        sa.Column("total_units", sa.Integer(), nullable=False, server_default="0"),
    )
