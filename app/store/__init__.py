from datetime import datetime, timezone
from enum import Enum, auto
from functools import partial
from typing import Any, Awaitable, Callable, Literal, Mapping

import sqlalchemy
import sqlmodel
from databases import Database
from sqlalchemy import orm as sa_orm
from sqlmodel import col

from . import placed_item, placement, product
from ._helper import _colname
from .placed_item import PlacedItem
from .placement import Placement
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


def _to_time(unix_epoch: int) -> str:
    return datetime.fromtimestamp(unix_epoch).strftime("%H:%M:%S")


type item_t = dict[str, int | str | None]
type placement_t = dict[str, int | list[item_t] | str | datetime | None]


# TODO: there should be a way to use the unixepoch function without this boiler plate
def unixepoch(attr: sa_orm.Mapped) -> sqlalchemy.Label:
    colname = _colname(col(attr))
    alias = getattr(attr, "name")
    return sqlalchemy.literal_column(f"unixepoch({colname})").label(alias)


class PlacementsQuery(Enum):
    incoming = auto()
    resolved = auto()

    def placements(self) -> sqlalchemy.Select:
        # Query from the placements table
        query: sqlalchemy.Select = (
            sqlmodel.select(Placement.placement_id)
            .group_by(col(Placement.placement_id))
            .order_by(col(Placement.placement_id).asc())
            .add_columns(unixepoch(col(Placement.placed_at)))
        )

        query = self._extra_timestamps(query)

        query = (
            # Query the list of placed items
            query.select_from(sqlmodel.join(Placement, PlacedItem))
            .add_columns(col(PlacedItem.product_id))
            .add_columns(unixepoch(col(PlacedItem.supplied_at)))
            .group_by(col(PlacedItem.product_id))
            .order_by(col(PlacedItem.product_id).asc())
            .add_columns(sqlmodel.func.count(col(PlacedItem.product_id)).label("count"))
            # Query product information
            .join(Product)
            .add_columns(col(Product.name))
        )

        # Include prices for resolved placements
        if self == self.resolved:
            query = query.add_columns(col(Product.price))

        return query

    def _extra_timestamps(self, query: sqlalchemy.Select) -> sqlalchemy.Select:
        """Conditionally include/exclude extra timestamps."""
        match self:
            case self.incoming:
                return query.where(
                    col(Placement.canceled_at).is_(None)
                    & col(Placement.completed_at).is_(None)
                )
            case self.resolved:
                return query.where(
                    col(Placement.canceled_at).isnot(None)
                    | col(Placement.completed_at).isnot(None)
                ).add_columns(
                    unixepoch(col(Placement.canceled_at)),
                    unixepoch(col(Placement.completed_at)),
                )

    def placements_callbacks(
        self, placements: list[placement_t]
    ) -> tuple[
        Callable[[int, Mapping], None],
        Callable[[Mapping], item_t],
        Callable[[list[item_t]], None],
    ]:
        match self:
            case self.incoming:

                def init_cb(placement_id: int, map: Mapping) -> None:
                    placements.append(
                        {
                            "placement_id": placement_id,
                            "placed_at": _to_time(map["placed_at"]),
                        }
                    )

                def elem_cb(map: Mapping) -> item_t:
                    supplied_at = map["supplied_at"]
                    return {
                        "product_id": map["product_id"],
                        "count": map["count"],
                        "name": map["name"],
                        "supplied_at": _to_time(supplied_at) if supplied_at else None,
                    }

                def list_cb(items: list[item_t]) -> None:
                    if len(placements) > 0:
                        placements[-1]["items_"] = items

                return init_cb, elem_cb, list_cb

            case self.resolved:
                total_price = 0

                def init_cb(placement_id: int, map: Mapping) -> None:
                    canceled_at, completed_at = map["canceled_at"], map["completed_at"]
                    placements.append(
                        {
                            "placement_id": placement_id,
                            "placed_at": _to_time(map["placed_at"]),
                            "canceled_at": _to_time(canceled_at)
                            if canceled_at
                            else None,
                            "completed_at": _to_time(completed_at)
                            if completed_at
                            else None,
                        }
                    )
                    nonlocal total_price
                    total_price = 0

                def elem_cb(map: Mapping) -> item_t:
                    count, price = map["count"], map["price"]
                    nonlocal total_price
                    total_price += count * price
                    supplied_at = map["supplied_at"]
                    return {
                        "product_id": map["product_id"],
                        "count": count,
                        "name": map["name"],
                        "price": Product.to_price_str(price),
                        "supplied_at": _to_time(supplied_at) if supplied_at else None,
                    }

                def list_cb(items: list[item_t]) -> None:
                    if len(placements) > 0:
                        placements[-1]["items_"] = items
                        placements[-1]["total_price"] = Product.to_price_str(
                            total_price
                        )

                return init_cb, elem_cb, list_cb


async def _agen_query_executor[T](
    db: Database,
    query: str,
    unique_key: Literal["placement_id"] | Literal["product_id"],
    init_cb: Callable[[Any, Mapping], None],
    elem_cb: Callable[[Mapping], T],
    list_cb: Callable[[list[T]], None],
):
    prev_unique_id = -1
    lst: list[T] = list()
    async for map in db.iterate(query):
        if (unique_id := map[unique_key]) != prev_unique_id:
            prev_unique_id = unique_id
            list_cb(lst)
            init_cb(unique_id, map)
            lst: list[T] = list()
        lst.append(elem_cb(map))
    list_cb(lst)


def _placements_loader(
    db: Database, status: PlacementsQuery
) -> Callable[[], Awaitable[list[placement_t]]]:
    placements: list[placement_t] = []

    query = str(status.placements().compile())
    init_cb, elem_cb, list_cb = status.placements_callbacks(placements)
    load_placements = partial(
        _agen_query_executor, db, query, "placement_id", init_cb, elem_cb, list_cb
    )

    async def load():
        placements.clear()
        await load_placements()
        return placements

    return load


load_incoming_placements = _placements_loader(database, PlacementsQuery.incoming)
load_resolved_placements = _placements_loader(database, PlacementsQuery.resolved)


async def load_one_resolved_placement(placement_id: int) -> placement_t | None:
    query = PlacementsQuery.resolved.placements().where(
        col(Placement.placement_id) == placement_id
    )

    rows_agen = database.iterate(query)
    if (row := await anext(rows_agen, None)) is None:
        return None

    canceled_at, completed_at = row["canceled_at"], row["completed_at"]
    placement: placement_t = {
        "placement_id": placement_id,
        "placed_at": _to_time(row["placed_at"]),
        "canceled_at": _to_time(canceled_at) if canceled_at else None,
        "completed_at": _to_time(completed_at) if completed_at else None,
    }

    total_price = 0

    def to_item(row: Mapping) -> item_t:
        count, price = row["count"], row["price"]
        nonlocal total_price
        total_price += count * price
        supplied_at = row["supplied_at"]
        return {
            "product_id": row["product_id"],
            "count": count,
            "name": row["name"],
            "price": Product.to_price_str(price),
            "supplied_at": _to_time(supplied_at) if supplied_at else None,
        }

    items = [to_item(row)]
    async for row in rows_agen:
        items.append(to_item(row))
    placement["items_"] = items
    placement["total_price"] = Product.to_price_str(total_price)

    return placement


# NOTE:get placements by incoming order in datetime
#
# async def select_placements_by_incoming_order() -> dict[int, list[dict]]:
#     query = f"""
#         SELECT
#             {PlacedItem.placement_id},
#             {PlacedItem.product_id},
#             {Product.name},
#             {Product.filename}
#         FROM {PlacedItem.__tablename__}
#         JOIN {Product.__tablename__} as {Product.__name__} ON {PlacedItem.product_id} = {Product.product_id}
#         ORDER BY {PlacedItem.placement_id} ASC, {PlacedItem.item_no} ASC;
#     """
#     placements: dict[int, list[dict]] = {}
#     async for row in db.iterate(query):
#         print(dict(row))
#     return placements


type placed_item_t = dict[str, int | str | list[dict[str, int | str]]]


def _placed_items_loader(db: Database) -> Callable[[], Awaitable[list[placed_item_t]]]:
    query = (
        sqlmodel.select(
            PlacedItem.placement_id,
            sqlmodel.func.count(col(PlacedItem.product_id)).label("count"),
            PlacedItem.product_id,
        )
        .where(col(PlacedItem.supplied_at).is_(None))  # Filter out supplied items
        .group_by(col(PlacedItem.placement_id), col(PlacedItem.product_id))
        .select_from(sqlmodel.join(PlacedItem, Product))
        .add_columns(col(Product.name), col(Product.filename))
        .join(Placement)
        .add_columns(unixepoch(col(Placement.placed_at)))
    )

    query = (
        PlacementsQuery.incoming._extra_timestamps(query)
        .order_by(col(PlacedItem.product_id).asc())
        .order_by(col(PlacedItem.placement_id).asc())
    )

    query_str = str(query.compile())

    placed_items: list[placed_item_t] = []

    def init_cb(product_id: int, map: Mapping):
        placed_items.append(
            {"product_id": product_id, "name": map["name"], "filename": map["filename"]}
        )

    def elem_cb(map: Mapping) -> dict[str, int | str]:
        return {
            "placement_id": map["placement_id"],
            "count": map["count"],
            "placed_at": _to_time(map["placed_at"]),
        }

    def list_cb(placements: list[dict[str, int | str]]):
        if len(placed_items) > 0:
            placed_items[-1]["placements"] = placements

    load_placed_products = partial(
        _agen_query_executor, db, query_str, "product_id", init_cb, elem_cb, list_cb
    )

    async def load():
        placed_items.clear()
        await load_placed_products()
        return placed_items

    return load


load_placed_items_incoming = _placed_items_loader(database)


async def supply_all_and_complete(placement_id: int):
    async with database.transaction():
        await PlacedItemTable._supply_all(placement_id)
        await PlacementTable._complete(placement_id)
    async with PlacementTable.modified:
        PlacementTable.modified.notify_all()


async def supply_and_complete_placement_if_done(placement_id: int, product_id: int):
    async with database.transaction():
        await PlacedItemTable._supply(placement_id, product_id)

        update_query = sqlmodel.update(Placement).where(
            (col(Placement.placement_id) == placement_id)
            & sqlmodel.select(
                sqlmodel.func.count(col(PlacedItem.item_no))
                == sqlmodel.func.count(col(PlacedItem.supplied_at))
            )
            .where(col(PlacedItem.placement_id) == placement_id)
            .scalar_subquery()
        )
        values = {"completed_at": datetime.now(timezone.utc)}
        await database.execute(update_query, values)

    async with PlacementTable.modified:
        PlacementTable.modified.notify_all()


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
