from datetime import UTC, datetime

import sqlalchemy
import sqlalchemy.orm as sa_orm
import sqlalchemy.sql.expression as sae
from databases import Database
from sqlalchemy.sql.functions import func as sa_func

from . import order, ordered_item, product
from .base import Base
from .order import ModifiedFlag, Order
from .ordered_item import OrderedItem
from .product import Product

DATABASE_URL = "sqlite:///db/app.db"
database = Database(DATABASE_URL)

ProductTable = product.Table(database)
OrderedItemTable = ordered_item.Table(database)
OrderTable = order.Table(database)


async def delete_product(product_id: int):
    async with database.transaction():
        query = sae.delete(Product).where(Product.product_id == product_id)
        await database.execute(query)

        query = sae.delete(OrderedItem).where(OrderedItem.product_id == product_id)
        await database.execute(query)


# TODO: there should be a way to use the unixepoch function without this boiler plate
def unixepoch(attr: sa_orm.Mapped) -> sqlalchemy.Label:
    colname = attr.label(None)  # Fully resolved name in the `table.field` format
    alias = getattr(attr, "name")  # noqa: B009
    return sae.literal_column(f"unixepoch({colname})").label(alias)


async def supply_and_complete_order_if_done(order_id: int, product_id: int) -> bool:
    async with database.transaction():
        await OrderedItemTable._supply(order_id, product_id)

        update_query = (
            sae.update(Order)
            .where(
                (Order.order_id == order_id)
                & sae.select(
                    sa_func.count(OrderedItem.item_no)
                    == sa_func.count(OrderedItem.supplied_at)
                )
                .where(OrderedItem.order_id == order_id)
                .scalar_subquery()
            )
            .returning(Order.order_id.isnot(None))
        )

        values = {"completed_at": datetime.now(UTC)}
        completed: bool | None = await database.fetch_val(update_query, values)

    flag = ModifiedFlag.SUPPLIED
    if completed is not None:
        flag |= ModifiedFlag.RESOLVED
    OrderTable.modified_flag_bc.send(flag)
    return completed is not None


async def supply_all_and_complete(order_id: int):
    async with database.transaction():
        await OrderedItemTable._supply_all(order_id)
        await OrderTable._complete(order_id)
    OrderTable.modified_flag_bc.send(ModifiedFlag.SUPPLIED | ModifiedFlag.RESOLVED)


async def _startup_db() -> None:
    await database.connect()

    # from alembic.config import Config
    # from alembic import command
    # command.upgrade(Config("alembic.ini"), "head")
    # TODO:instruct the user to generate missing tables by running alembic
    # migrations instead of creating tables through the SQLAlchemy query. Right
    # now, this code won't create an alembic version table.
    # Alternatively, we might want to migrate here in the application code:
    # https://stackoverflow.com/questions/24622170/using-alembic-api-from-inside-application-code
    for table in Base.metadata.tables.values():
        schema = sqlalchemy.schema.CreateTable(table, if_not_exists=True)
        query = str(schema.compile())
        await database.execute(query)

    await ProductTable.ainit()
    await OrderedItemTable.ainit()


async def _shutdown_db() -> None:
    await database.disconnect()


startup_and_shutdown_db = (_startup_db, _shutdown_db)
