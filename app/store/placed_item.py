from typing import Annotated

import sqlmodel
from databases import Database

from ._helper import _colname
from .placement import Placement
from .product import Product


class PlacedItem(sqlmodel.SQLModel, table=True):
    # NOTE: there are no Pydantic ways to set the generated table's name, as per https://github.com/fastapi/sqlmodel/issues/159
    __tablename__ = "placed_items"  # pyright: ignore[reportAssignmentType]

    id: int | None = sqlmodel.Field(default=None, primary_key=True)
    placement_id: Annotated[
        int, sqlmodel.Field(foreign_key=_colname(sqlmodel.col(Placement.placement_id)))
    ]
    item_no: int
    product_id: Annotated[
        int, sqlmodel.Field(foreign_key=_colname(sqlmodel.col(Product.product_id)))
    ]


class Table:
    _last_placement_id: int | None
    _db: Database

    def __init__(self, database: Database):
        self._db = database

    async def ainit(self) -> None:
        query = sqlmodel.func.max(PlacedItem.placement_id).select()
        self._last_placement_id = await self._db.fetch_val(query)

    async def select_all(self) -> list[PlacedItem]:
        query = sqlmodel.select(PlacedItem)
        return [PlacedItem.model_validate(m) async for m in self._db.iterate(query)]

    async def by_placement_id(self, placement_id: int) -> list[PlacedItem]:
        clause = PlacedItem.placement_id == placement_id
        query = sqlmodel.select(PlacedItem).where(clause)
        return [PlacedItem.model_validate(m) async for m in self._db.iterate(query)]

    async def issue(self, product_ids: list[int]) -> int:
        placement_id = (self._last_placement_id or 0) + 1
        await self._db.execute_many(
            sqlmodel.insert(PlacedItem).values(placement_id=placement_id),
            [{"item_no": i, "product_id": pid} for i, pid in enumerate(product_ids)],
        )
        self._last_placement_id = placement_id
        return placement_id

    # NOTE: this function needs authorization since it destroys all receipts
    async def clear(self) -> None:
        await self._db.execute(sqlmodel.delete(PlacedItem))
        self._last_placement_id = None
