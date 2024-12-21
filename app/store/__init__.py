from datetime import datetime, timezone

import sqlalchemy
import sqlmodel
from databases import Database
from sqlalchemy import orm as sa_orm
from sqlmodel import col

from . import order, ordered_item, product
from ._helper import _colname
from .order import ModifiedFlag, Order  # noqa: F401
from .ordered_item import OrderedItem
from .product import Product

from .base import TableBase

DATABASE_URL = "sqlite:///db/app.db"
database = Database(DATABASE_URL)

ProductTable = product.Table(database)
OrderedItemTable = ordered_item.Table(database)
OrderTable = order.Table(database)


async def delete_product(product_id: int):
    async with database.transaction():
        query = sqlmodel.delete(Product).where(col(Product.product_id) == product_id)
        await database.execute(query)

        clause = col(OrderedItem.product_id) == product_id
        query = sqlmodel.delete(OrderedItem).where(clause)
        await database.execute(query)


# TODO: there should be a way to use the unixepoch function without this boiler plate
def unixepoch(attr: sa_orm.Mapped) -> sqlalchemy.Label:
    colname = _colname(attr)
    alias = getattr(attr, "name")
    return sqlalchemy.literal_column(f"unixepoch({colname})").label(alias)


async def supply_and_complete_order_if_done(order_id: int, product_id: int):
    async with database.transaction():
        await OrderedItemTable._supply(order_id, product_id)

        update_query = (
            sqlmodel.update(Order)
            .where(
                (col(Order.placement_id) == order_id)
                & sqlmodel.select(
                    sqlmodel.func.count(col(OrderedItem.item_no))
                    == sqlmodel.func.count(col(OrderedItem.supplied_at))
                )
                .where(col(OrderedItem.placement_id) == order_id)
                .scalar_subquery()
            )
            .returning(col(Order.placement_id).isnot(None))
        )

        values = {"completed_at": datetime.now(timezone.utc)}
        completed: bool | None = await database.fetch_val(update_query, values)

    async with OrderTable.modified_cond_flag:
        flag = ModifiedFlag.SUPPLIED
        if completed is not None:
            flag |= ModifiedFlag.RESOLVED
        OrderTable.modified_cond_flag.notify_all(flag)


async def supply_all_and_complete(order_id: int):
    async with database.transaction():
        await OrderedItemTable._supply_all(order_id)
        await OrderTable._complete(order_id)
    async with OrderTable.modified_cond_flag:
        FLAG = ModifiedFlag.SUPPLIED | ModifiedFlag.RESOLVED
        OrderTable.modified_cond_flag.notify_all(FLAG)


async def _startup_db() -> None:
    await database.connect()

    # TODO:instruct the user to generate missing tables by running alembic
    # migrations instead of creating tables through the SQLAlchemy query. Right
    # now, this code won't create an alembic version table.
    # Alternatively, we might want to migrate here in the application code:
    # https://stackoverflow.com/questions/24622170/using-alembic-api-from-inside-application-code
    for table in TableBase.metadata.tables.values():
        schema = sqlalchemy.schema.CreateTable(table, if_not_exists=True)
        query = str(schema.compile())
        await database.execute(query)

    await ProductTable.ainit()
    await OrderedItemTable.ainit()


async def _shutdown_db() -> None:
    await database.disconnect()


startup_and_shutdown_db = (_startup_db, _shutdown_db)
