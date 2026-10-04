"""inline-ordered-item-count

Revision ID: ce4eaddf8cc8
Revises: 85a3fddadd88
Create Date: 2026-10-04 02:42:15.870565

"""

import sys
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "ce4eaddf8cc8"
down_revision: Union[str, None] = "85a3fddadd88"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    print('WARNING: Although upgrading somewhat "works," you should renew your database afresh.', file=sys.stderr)
    with op.batch_alter_table("ordered_items", schema=None) as batch_op:
        batch_op.add_column(sa.Column("count_", sa.Integer(), default=1, nullable=True))
        batch_op.alter_column("count_", new_column_name="count", nullable=False)


def downgrade() -> None:
    print("ERROR: Downgrading is not supported. ordered_items.count is imcompatible with previous version.", file=sys.stderr)
    exit(1)
    # with op.batch_alter_table("ordered_items", schema=None) as batch_op:
    #     batch_op.drop_column("count")
