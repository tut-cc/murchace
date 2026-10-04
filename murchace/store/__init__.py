import sqlalchemy
from databases import Database
from sqlalchemy import sql

from ..env import DATABASE_PATH
from . import category, order, ordered_item, product
from .base import Base
from .order import Order  # noqa: F401
from .ordered_item import OrderedItem
from .product import Product

DATABASE_URL = f"sqlite:///{DATABASE_PATH}"


database = Database(DATABASE_URL)

CategoryTable = category.Table(database)
ProductTable = product.Table(database)
OrderedItemTable = ordered_item.Table(database)
OrderTable = order.Table(database)


async def delete_product(product_id: int):
    async with database.transaction():
        query = sql.delete(Product).where(Product.product_id == product_id)
        await database.execute(query)

        query = sql.delete(OrderedItem).where(OrderedItem.product_id == product_id)
        await database.execute(query)


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
