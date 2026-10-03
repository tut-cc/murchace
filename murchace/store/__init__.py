import sqlalchemy
import sqlalchemy.sql.expression as sa_exp
from databases import Database
from sqlalchemy.sql.functions import func as sa_func

from . import category, order, ordered_item, product
from .base import Base
from .order import Order
from .ordered_item import OrderedItem
from .product import Product

DATABASE_URL = "sqlite:///db/app.db"
database = Database(DATABASE_URL)

CategoryTable = category.Table(database)
ProductTable = product.Table(database)
OrderedItemTable = ordered_item.Table(database)
OrderTable = order.Table(database)


async def delete_product(product_id: int):
    async with database.transaction():
        query = sa_exp.delete(Product).where(Product.product_id == product_id)
        await database.execute(query)

        query = sa_exp.delete(OrderedItem).where(OrderedItem.product_id == product_id)
        await database.execute(query)


async def supply_and_complete_order_if_done(order_id: int, product_id: int) -> bool:
    async with database.transaction():
        await OrderedItemTable._supply(order_id, product_id)

        update_query = (
            sa_exp.update(Order)
            .where(
                (Order.order_id == order_id)
                & sa_exp.select(
                    sa_func.count(OrderedItem.item_no)
                    == sa_func.count(OrderedItem.supplied_at)
                )
                .where(OrderedItem.order_id == order_id)
                .scalar_subquery()
            )
            .returning(Order.order_id.isnot(None))
        )

        values = {"completed_at": sa_func.unixepoch()}
        completed: bool | None = await database.fetch_val(update_query, values)

    return completed is not None


async def supply_all_and_complete(order_id: int):
    async with database.transaction():
        await OrderedItemTable._supply_all(order_id)
        await OrderTable._complete(order_id)


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

    await CategoryTable.ainit()
    await ProductTable.ainit()


async def _shutdown_db() -> None:
    await database.disconnect()


startup_and_shutdown_db = (_startup_db, _shutdown_db)
