from datetime import datetime
from enum import Enum, auto
from functools import partial
from typing import Awaitable, Callable, Mapping, assert_never

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


def _to_time(unix_epoch: int) -> str:
    return datetime.fromtimestamp(unix_epoch).strftime("%H:%M:%S")


type products_t = list[dict[str, int | str]]
type placements_t = list[dict[str, int | products_t | str | datetime | None]]


# TODO: there should be a way to use the unixepoch function without this boiler plate
def unixepoch(attr: sa_orm.Mapped) -> sqlalchemy.Label:
    colname = _colname(col(attr))
    alias = getattr(attr, "name")
    return sqlalchemy.literal_column(f"unixepoch({colname})").label(alias)


class SortOrderedProductsBy(Enum):
    PRODUCT_ID = "product_id"
    TIME = "time"
    NO_ITEMS = "no_items"

    def order_by(self) -> sqlalchemy.ColumnElement:
        match self:
            case self.PRODUCT_ID:
                return sqlmodel.asc(col(PlacedItem.product_id))
            case self.TIME:
                return sqlmodel.desc(col(Placement.placed_at))
            case self.NO_ITEMS:
                return sqlmodel.desc(sqlmodel.literal_column("count"))


class PlacementsQuery(Enum):
    incoming = auto()
    canceled = auto()
    completed = auto()

    def by_placement_id(self) -> sqlalchemy.Select:
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
            .group_by(col(PlacedItem.product_id))
            .order_by(col(PlacedItem.product_id).asc())
            .add_columns(sqlmodel.func.count(col(PlacedItem.product_id)).label("count"))
            # Query product information
            .join(Product)
            .add_columns(col(Product.name), col(Product.filename))
        )

        # Include prices for canceled/completed placements
        if self != self.incoming:
            query = query.add_columns(col(Product.price))

        return query

    def by_ordered_products(self, sort_by: SortOrderedProductsBy) -> sqlalchemy.Select:
        query = (
            sqlmodel.select(
                PlacedItem.placement_id,
                sqlmodel.func.count(col(PlacedItem.product_id)).label("count"),
                PlacedItem.product_id,
            )
            .group_by(col(PlacedItem.placement_id), col(PlacedItem.product_id))
            .select_from(sqlmodel.join(PlacedItem, Product))
            .add_columns(col(Product.name), col(Product.filename))
            .join(Placement)
        )

        query = self._extra_timestamps(query)

        return query.order_by(sort_by.order_by())

    def _extra_timestamps(self, query: sqlalchemy.Select) -> sqlalchemy.Select:
        """Conditionally include/exclude extra timestamps."""
        match self:
            case self.incoming:
                return query.where(
                    col(Placement.canceled_at).is_(None)
                    & col(Placement.completed_at).is_(None)
                )
            case self.canceled:
                return query.where(col(Placement.canceled_at).isnot(None)).add_columns(
                    unixepoch(col(Placement.canceled_at))
                )
            case self.completed:
                return query.where(col(Placement.completed_at).isnot(None)).add_columns(
                    unixepoch(col(Placement.completed_at))
                )


class _PlacementsLoader:
    def __new__(
        cls, db: Database, status: PlacementsQuery
    ) -> Callable[[], Awaitable[placements_t]]:
        placements: placements_t = []

        match status:
            case status.incoming:

                def init_cb(placement_id: int, map: Mapping) -> products_t:
                    products = []
                    placements.append(
                        {
                            "placement_id": placement_id,
                            "products": products,
                            "placed_at": _to_time(map["placed_at"]),
                        }
                    )
                    return products

                def update_product_cb(map: Mapping) -> dict[str, int | str]:
                    return {
                        "product_id": map["product_id"],
                        "count": map["count"],
                        "name": map["name"],
                        "filename": map["filename"],
                    }

                def last_cb(): ...

            case status.canceled:
                total_price = 0

                def init_cb(placement_id: int, map: Mapping) -> products_t:
                    products = []
                    placements.append(
                        {
                            "placement_id": placement_id,
                            "products": products,
                            "placed_at": _to_time(map["placed_at"]),
                            "canceled_at": _to_time(map["canceled_at"]),
                        }
                    )
                    nonlocal total_price
                    total_price = 0
                    return products

                def update_product_cb(map: Mapping) -> dict[str, int | str]:
                    count, price = map["count"], map["price"]
                    nonlocal total_price
                    total_price += count * price
                    return {
                        "product_id": map["product_id"],
                        "count": count,
                        "name": map["name"],
                        "filename": map["filename"],
                        "price": Product.to_price_str(price),
                    }

                def last_cb() -> None:
                    if len(placements) > 0:
                        placements[-1]["total_price"] = Product.to_price_str(
                            total_price
                        )

            case status.completed:
                total_price = 0

                def init_cb(placement_id: int, map: Mapping) -> products_t:
                    products = []
                    placements.append(
                        {
                            "placement_id": placement_id,
                            "products": products,
                            "placed_at": _to_time(map["placed_at"]),
                            "completed_at": _to_time(map["completed_at"]),
                        }
                    )
                    nonlocal total_price
                    total_price = 0
                    return products

                def update_product_cb(map: Mapping) -> dict[str, int | str]:
                    count, price = map["count"], map["price"]
                    nonlocal total_price
                    total_price += count * price
                    return {
                        "product_id": map["product_id"],
                        "count": count,
                        "name": map["name"],
                        "filename": map["filename"],
                        "price": Product.to_price_str(price),
                    }

                def last_cb() -> None:
                    if len(placements) > 0:
                        placements[-1]["total_price"] = Product.to_price_str(
                            total_price
                        )

            case _:
                assert_never()

        query = str(status.by_placement_id().compile())
        load_placements = partial(
            cls._execute, db, query, init_cb, update_product_cb, last_cb
        )

        async def loader():
            placements.clear()
            await load_placements()
            return placements

        return loader

    @staticmethod
    async def _execute(
        db: Database,
        query: str,
        init_cb: Callable[[int, Mapping], products_t],
        update_product_cb: Callable[[Mapping], dict[str, int | str]],
        last_cb: Callable[[], None],
    ):
        products = []
        prev_placement_id = -1
        async for map in db.iterate(query):
            if (placement_id := map["placement_id"]) != prev_placement_id:
                prev_placement_id = placement_id
                last_cb()
                products = init_cb(placement_id, map)
            products.append(update_product_cb(map))
        last_cb()


load_incoming_placements = _PlacementsLoader(database, PlacementsQuery.incoming)
load_canceled_placements = _PlacementsLoader(database, PlacementsQuery.canceled)
load_completed_placements = _PlacementsLoader(database, PlacementsQuery.completed)


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


async def load_ordered_products(
    sort_by: SortOrderedProductsBy,
) -> list[dict[str, int | str | list[dict[str, int]]]]:
    query = PlacementsQuery.incoming.by_ordered_products(sort_by)
    ret: dict[int, dict[str, int | str | list[dict[str, int]]]] = {}
    async for map in database.iterate(query):
        product_id = map["product_id"]
        if (product_dict := ret.get(product_id)) is None:
            ret[product_id] = {
                "name": map["name"],
                "filename": map["filename"],
                "placements": [],
            }
            lst: ... = ret[product_id]["placements"]
        else:
            lst: ... = product_dict["placements"]
        lst.append(
            {
                "placement_id": map["placement_id"],
                "count": map["count"],
            }
        )
    return list(ret.values())


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
