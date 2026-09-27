import asyncio
import logging
import os
import sqlite3
from contextlib import suppress
from datetime import UTC, datetime

import sqlalchemy
import sqlalchemy.orm as sa_orm
import sqlalchemy.sql.expression as sa_exp
from databases import Database
from sqlalchemy.sql.functions import func as sa_func

from . import broadcast_event, category, order, ordered_item, product
from .base import Base
from .order import ModifiedFlag, Order
from .ordered_item import OrderedItem
from .product import Product

DATABASE_URL = "sqlite:///db/app.db"
database = Database(DATABASE_URL)

CategoryTable = category.Table(database)
ProductTable = product.Table(database)
OrderedItemTable = ordered_item.Table(database)
OrderTable = order.Table(database)
BroadcastEventTable = broadcast_event.Table(database)

_logger = logging.getLogger(__name__)

_poll_task: asyncio.Task[None] | None = None


async def delete_product(product_id: int):
    async with database.transaction():
        query = sa_exp.delete(Product).where(Product.product_id == product_id)
        await database.execute(query)

        query = sa_exp.delete(OrderedItem).where(OrderedItem.product_id == product_id)
        await database.execute(query)


# TODO: there should be a way to use the unixepoch function without this boiler plate
def unixepoch(attr: sa_orm.Mapped) -> sqlalchemy.Label:
    colname = attr.label(None)  # Fully resolved name in the `table.field` format
    alias = getattr(attr, "name")  # noqa: B009
    return sa_exp.literal_column(f"unixepoch({colname})").label(alias)


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


async def poll_broadcast_events() -> None:
    pid = os.getpid()
    last_id = await BroadcastEventTable.get_latest_id()
    try:
        while True:
            await asyncio.sleep(0.05)
            try:
                events = await BroadcastEventTable.fetch_after(last_id)
                for event in events:
                    last_id = event.id
                    if event.worker_pid != pid:
                        OrderTable.modified_flag_bc.send_local(ModifiedFlag(event.flag))
                if events and last_id > 100:
                    await BroadcastEventTable.prune(last_id - 100)
            except asyncio.CancelledError:
                raise
            except sqlite3.Error as e:
                _logger.warning("Error polling broadcast events: %s", e)
    except asyncio.CancelledError:
        pass


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
    await OrderedItemTable.ainit()

    async def _publish_broadcast_event(flag: ModifiedFlag) -> None:
        await BroadcastEventTable.insert(flag.value)

    OrderTable.modified_flag_bc.set_publish_hook(_publish_broadcast_event)

    global _poll_task
    _poll_task = asyncio.create_task(poll_broadcast_events())


async def _shutdown_db() -> None:
    global _poll_task
    if _poll_task is not None:
        _poll_task.cancel()
        with suppress(asyncio.CancelledError):
            await _poll_task
        _poll_task = None

    OrderTable.modified_flag_bc.set_publish_hook(None)
    await database.disconnect()


startup_and_shutdown_db = (_startup_db, _shutdown_db)
