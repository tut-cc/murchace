"""Rename placements and placed_items tables to use the term "order"

Revision ID: b260a0b3e3c6
Revises: 74640061af2b

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b260a0b3e3c6"
down_revision: Union[str, None] = "74640061af2b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename tables
    op.rename_table("placed_items", "ordered_items")
    op.rename_table("placements", "orders")

    # Rename a column
    with op.batch_alter_table("ordered_items") as batch_op:
        batch_op.drop_constraint("pk_placed_items", type_="primary")
        batch_op.create_primary_key("pk_ordered_items", ["id"])

        batch_op.alter_column("placement_id", new_column_name="order_id")

    # Rename columns
    with op.batch_alter_table("orders") as batch_op:
        batch_op.drop_constraint("pk_placements", type_="primary")
        batch_op.create_primary_key("pk_orders", ["id"])

        batch_op.alter_column("placement_id", new_column_name="order_id")
        batch_op.alter_column("placed_at", new_column_name="ordered_at")

    # Rename foreign keys alter renaming columns have finished.
    with op.batch_alter_table("ordered_items") as batch_op:
        batch_op.drop_constraint(
            "fk_placed_items_placement_id_placements", type_="foreignkey"
        )
        batch_op.create_foreign_key(
            "fk_ordered_items_order_id_orders", "orders", ["order_id"], ["order_id"]
        )

        batch_op.drop_constraint(
            "fk_placed_items_product_id_products", type_="foreignkey"
        )
        batch_op.create_foreign_key(
            "fk_ordered_items_product_id_products",
            "products",
            ["product_id"],
            ["product_id"],
        )


def downgrade() -> None:
    # Rename tables
    op.rename_table("orders", "placements")
    op.rename_table("ordered_items", "placed_items")

    # Rename columns
    with op.batch_alter_table("placements") as batch_op:
        batch_op.drop_constraint("pk_orders", type_="primary")
        batch_op.create_primary_key("pk_placements", ["id"])

        batch_op.alter_column("ordered_at", new_column_name="placed_at")
        batch_op.alter_column("order_id", new_column_name="placement_id")

    # Rename a column
    with op.batch_alter_table("placed_items") as batch_op:
        batch_op.drop_constraint("pk_ordered_items", type_="primary")
        batch_op.create_primary_key("pk_placed_items", ["id"])

        batch_op.alter_column("order_id", new_column_name="placement_id")

    # Rename foreign keys alter renaming columns have finished.
    with op.batch_alter_table("placed_items") as batch_op:
        batch_op.drop_constraint("fk_ordered_items_order_id_orders", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_placed_items_placement_id_placements",
            "placements",
            ["placement_id"],
            ["placement_id"],
        )

        batch_op.drop_constraint(
            "fk_ordered_items_product_id_products", type_="foreignkey"
        )
        batch_op.create_foreign_key(
            "fk_placed_items_product_id_products",
            "products",
            ["product_id"],
            ["product_id"],
        )
