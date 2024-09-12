from enum import Enum
from typing import assert_never

import sqlalchemy
from databases import Database
from pydantic import BaseModel
from sqlmodel import SQLModel

from . import placed_item, placement, product
from .placed_item import PlacedItem
from .placement import Placement
from .product import Product

DATABASE_URL = "sqlite:///app.db"
database = Database(DATABASE_URL)


ProductTable = product.Table(database)
PlacedItemTable = placed_item.Table(database)
PlacementTable = placement.Table(database)


class PlacementReceipt(BaseModel):
    class ProductEntry(BaseModel):
        product_id: int
        count: int
        name: str
        filename: str
        price: int

    placement_id: int
    products: list[ProductEntry]
    total_price: int

    class Result(BaseModel):
        placement_id: int
        product_id: int
        count: int
        name: str
        filename: str
        price: int


async def select_placements(
    canceled: bool,
    completed: bool,
) -> list[dict[str, int | list[dict[str, int | str]] | str]]:
    # list of products with each row alongside the number of ordered items
    query = f"""
        SELECT
            {PlacedItem.placement_id},
            {PlacedItem.product_id},
            COUNT({PlacedItem.product_id}) AS count,
            {Product.name},
            {Product.filename},
            {Product.price}
        FROM {PlacedItem.__tablename__} as {PlacedItem.__name__}
        JOIN {Product.__tablename__} as {Product.__name__} ON {PlacedItem.product_id} = {Product.product_id}
        JOIN {Placement.__tablename__} as {Placement.__name__} ON {PlacedItem.placement_id} = {Placement.placement_id}
        WHERE {Placement.canceled} = {int(canceled)} AND
              {Placement.completed} = {int(completed)}
        GROUP BY {PlacedItem.placement_id}, {PlacedItem.product_id}
        ORDER BY {PlacedItem.placement_id} ASC, {PlacedItem.product_id} ASC
    """
    placements: list[dict[str, int | list[dict[str, int | str]] | str]] = []
    prev_placement_id = -1
    prev_products: list[dict[str, int | str]] = []
    total_price = 0

    async for map in database.iterate(query):
        placement_id = map["placement_id"]
        if placement_id != prev_placement_id:
            if prev_placement_id != -1:
                placements.append(
                    {
                        "placement_id": prev_placement_id,
                        "products": prev_products,
                        "total_price": Product.to_price_str(total_price),
                    }
                )
            prev_placement_id = placement_id
            prev_products = []
            total_price = 0
        count, price = map["count"], map["price"]
        prev_products.append(
            {
                "product_id": map["product_id"],
                "count": count,
                "name": map["name"],
                "filename": map["filename"],
                "price": Product.to_price_str(price),
            }
        )
        total_price += count * price
    if prev_placement_id != -1:
        placements.append(
            {
                "placement_id": prev_placement_id,
                "products": prev_products,
                "total_price": Product.to_price_str(total_price),
            }
        )
    return placements


# NOTE:get placements by incoming order in datetime
# TODO: add a datetime field to PlacedItem
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


class SortOrderedProductsBy(Enum):
    PRODUCT_ID = "product_id"
    TIME = "time"
    NO_ITEMS = "no_items"


async def select_ordered_products(
    sort_by: SortOrderedProductsBy,
    canceled: bool,
    completed: bool,
) -> list[dict[str, int | str | list[dict[str, int]]]]:
    match sort_by:
        case SortOrderedProductsBy.PRODUCT_ID:
            order_by = f"{PlacedItem.product_id} ASC"
        case SortOrderedProductsBy.TIME:
            # TODO: add datatime field to the placements table
            # order_by = Placement.datetime
            order_by = NotImplemented
        case SortOrderedProductsBy.NO_ITEMS:
            order_by = "count DESC"
        case _:
            assert_never(SortOrderedProductsBy)
    query = f"""
        SELECT
            {PlacedItem.placement_id},
            COUNT({PlacedItem.product_id}) AS count,
            {PlacedItem.product_id},
            {Product.name},
            {Product.filename}
        FROM {PlacedItem.__tablename__} as {PlacedItem.__name__}
        JOIN {Product.__tablename__} as {Product.__name__} ON {PlacedItem.product_id} = {Product.product_id}
        JOIN {Placement.__tablename__} as {Placement.__name__} ON {PlacedItem.placement_id} = {Placement.placement_id}
        WHERE {Placement.canceled} = {int(canceled)} AND
              {Placement.completed} = {int(completed)}
        GROUP BY {PlacedItem.placement_id}, {PlacedItem.product_id}
        ORDER BY {order_by}
    """
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
    for table in SQLModel.metadata.tables.values():
        schema = sqlalchemy.schema.CreateTable(table, if_not_exists=True)
        query = str(schema.compile())
        await database.execute(query)

    await ProductTable.ainit()
    await PlacedItemTable.ainit()


async def _shutdown_db() -> None:
    await database.disconnect()


startup_and_shutdown_db = (_startup_db, _shutdown_db)
