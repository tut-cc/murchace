from datetime import datetime, timezone

import sqlalchemy
import sqlmodel
from databases import Database
from sqlalchemy import orm as sa_orm
from sqlmodel import col

from . import placed_item, placement, product
from ._helper import _colname
from .placed_item import PlacedItem
from .placement import ModifiedFlag, Placement  # noqa: F401
from .product import Product

DATABASE_URL = "sqlite:///db/app.db"
database = Database(DATABASE_URL)

ProductTable = product.Table(database)
PlacedItemTable = placed_item.Table(database)
PlacementTable = placement.Table(database)


async def delete_product(product_id: int):
    async with database.transaction():
        query = sqlmodel.delete(Product).where(col(Product.product_id) == product_id)
        await database.execute(query)

        clause = col(PlacedItem.product_id) == product_id
        query = sqlmodel.delete(PlacedItem).where(clause)
        await database.execute(query)


# TODO: there should be a way to use the unixepoch function without this boiler plate
def unixepoch(attr: sa_orm.Mapped) -> sqlalchemy.Label:
    colname = _colname(attr)
    alias = getattr(attr, "name")
    return sqlalchemy.literal_column(f"unixepoch({colname})").label(alias)


async def supply_and_complete_order_if_done(order_id: int, product_id: int):
    async with database.transaction():
        await PlacedItemTable._supply(order_id, product_id)

        update_query = (
            sqlmodel.update(Placement)
            .where(
                (col(Placement.placement_id) == order_id)
                & sqlmodel.select(
                    sqlmodel.func.count(col(PlacedItem.item_no))
                    == sqlmodel.func.count(col(PlacedItem.supplied_at))
                )
                .where(col(PlacedItem.placement_id) == order_id)
                .scalar_subquery()
            )
            .returning(col(Placement.placement_id).isnot(None))
        )

        values = {"completed_at": datetime.now(timezone.utc)}
        completed: bool | None = await database.fetch_val(update_query, values)

    async with PlacementTable.modified_cond_flag:
        flag = ModifiedFlag.SUPPLIED
        if completed is not None:
            flag |= ModifiedFlag.RESOLVED
        PlacementTable.modified_cond_flag.notify_all(flag)


async def supply_all_and_complete(order_id: int):
    async with database.transaction():
        await PlacedItemTable._supply_all(order_id)
        await PlacementTable._complete(order_id)
    async with PlacementTable.modified_cond_flag:
        FLAG = ModifiedFlag.SUPPLIED | ModifiedFlag.RESOLVED
        PlacementTable.modified_cond_flag.notify_all(FLAG)


async def _startup_db() -> None:
    await database.connect()

    # TODO: we should use a database schema migration tool like Alembic as explained in:
    # https://www.encode.io/databases/database_queries/#creating-tables
    for table in sqlmodel.SQLModel.metadata.tables.values():
        schema = sqlalchemy.schema.CreateTable(table, if_not_exists=True)
        query = str(schema.compile())
        await database.execute(query)

    await ProductTable.ainit()
    await PlacedItemTable.ainit()


async def _shutdown_db() -> None:
    await database.disconnect()


startup_and_shutdown_db = (_startup_db, _shutdown_db)
