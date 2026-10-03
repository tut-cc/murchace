"""replace-datetime-with-integer-timestamp

Revision ID: 85a3fddadd88
Revises: 94b444537abb
Create Date: 2026-10-03 20:58:40.874801

"""

from datetime import datetime 
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import func


# revision identifiers, used by Alembic.
revision: str = "85a3fddadd88"
down_revision: Union[str, None] = "94b444537abb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("ordered_items", schema=None) as batch_op:
        batch_op.add_column(sa.Column("supplied_at_", sa.Integer(), nullable=True))
    op.execute(
        sa.update(sa.table("ordered_items", sa.column("supplied_at_")))
        .values(supplied_at_=func.unixepoch(sa.column("supplied_at")))
    )
    with op.batch_alter_table("ordered_items", schema=None) as batch_op:
        batch_op.drop_column("supplied_at")
        batch_op.alter_column("supplied_at_", new_column_name="supplied_at")

    with op.batch_alter_table("orders", schema=None) as batch_op:
        batch_op.add_column(sa.Column("ordered_at_", sa.Integer(), nullable=False, server_default=sa.Grouping(func.unixepoch())))
        batch_op.add_column(sa.Column("canceled_at_", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("completed_at_", sa.Integer(), nullable=True))
    batch_op.execute(
        sa.update(sa.table("orders", sa.column("ordered_at_"), sa.column("canceled_at_"), sa.column("completed_at_")))
        .values(ordered_at_=func.unixepoch(sa.column("ordered_at")))
        .values(canceled_at_=func.unixepoch(sa.column("canceled_at")))
        .values(completed_at_=func.unixepoch(sa.column("completed_at")))
    )
    with op.batch_alter_table("orders", schema=None) as batch_op:
        batch_op.drop_column("ordered_at")
        batch_op.alter_column("ordered_at_", new_column_name="ordered_at")
        batch_op.drop_column("canceled_at")
        batch_op.alter_column("canceled_at_", new_column_name="canceled_at")
        batch_op.drop_column("completed_at")
        batch_op.alter_column("completed_at_", new_column_name="completed_at")


def downgrade() -> None:
    with op.batch_alter_table("orders", schema=None) as batch_op:
        batch_op.add_column(sa.Column("completed_at_", sa.DATETIME(), nullable=True))
        batch_op.add_column(sa.Column("canceled_at_", sa.DATETIME(), nullable=True))
        batch_op.add_column(sa.Column("ordered_at_", sa.DATETIME(), nullable=False, server_default=func.current_timestamp()))
    batch_op.execute(
        sa.update(sa.table("orders", sa.column("completed_at_"), sa.column("canceled_at_"), sa.column("ordered_at_")))
        .values(completed_at_=func.datetime(sa.column("completed_at"), "unixepoch"))
        .values(canceled_at_=func.datetime(sa.column("canceled_at"), "unixepoch"))
        .values(ordered_at_=func.datetime(sa.column("ordered_at"), "unixepoch"))
    )
    with op.batch_alter_table("orders", schema=None) as batch_op:
        batch_op.drop_column("completed_at")
        batch_op.alter_column("completed_at_", new_column_name="completed_at")
        batch_op.drop_column("canceled_at")
        batch_op.alter_column("canceled_at_", new_column_name="canceled_at")
        batch_op.drop_column("ordered_at")
        batch_op.alter_column("ordered_at_", new_column_name="ordered_at", nullable=False)

    with op.batch_alter_table("ordered_items", schema=None) as batch_op:
        batch_op.add_column(sa.Column("supplied_at_", sa.DATETIME(), nullable=True))
    op.execute(
        sa.update(sa.table("ordered_items", sa.column("supplied_at_")))
        .values(supplied_at_=func.datetime(sa.column("supplied_at"), "unixepoch"))
    )
    with op.batch_alter_table("ordered_items", schema=None) as batch_op:
        batch_op.drop_column("supplied_at")
        batch_op.alter_column("supplied_at_", new_column_name="supplied_at")
