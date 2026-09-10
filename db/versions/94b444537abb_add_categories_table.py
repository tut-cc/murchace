"""add_categories_table

Revision ID: 94b444537abb
Revises: b260a0b3e3c6
Create Date: 2026-09-18 13:02:14.151867

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "94b444537abb"
down_revision: Union[str, None] = "b260a0b3e3c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
