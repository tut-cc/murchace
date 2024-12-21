from datetime import datetime, timezone
from typing import Annotated

import sqlmodel
from databases import Database
from sqlmodel import col

from ._helper import _colname
from .base import TableBase
from .order import Order
from .product import Product


class OrderedItem(TableBase, table=True):
    # NOTE: there are no Pydantic ways to set the generated table's name, as per https://github.com/fastapi/sqlmodel/issues/159
    __tablename__ = "ordered_items"  # pyright: ignore[reportAssignmentType]

    id: int | None = sqlmodel.Field(default=None, primary_key=True)
    order_id: Annotated[
        int, sqlmodel.Field(foreign_key=_colname(sqlmodel.col(Order.order_id)))
    ]
    item_no: int
    product_id: Annotated[
        int, sqlmodel.Field(foreign_key=_colname(sqlmodel.col(Product.product_id)))
    ]
    supplied_at: datetime | None = sqlmodel.Field(
        default=None, sa_column=sqlmodel.Column(sqlmodel.DateTime(timezone=True))
    )


class Table:
    _last_order_id: int | None
    _db: Database

    def __init__(self, database: Database):
        self._db = database

    async def ainit(self) -> None:
        query = sqlmodel.func.max(OrderedItem.order_id).select()
        self._last_order_id = await self._db.fetch_val(query)

    async def select_all(self) -> list[OrderedItem]:
        query = sqlmodel.select(OrderedItem)
        return [OrderedItem.model_validate(m) async for m in self._db.iterate(query)]

    async def by_order_id(self, order_id: int) -> list[OrderedItem]:
        clause = OrderedItem.order_id == order_id
        query = sqlmodel.select(OrderedItem).where(clause)
        return [OrderedItem.model_validate(m) async for m in self._db.iterate(query)]

    async def issue(self, product_ids: list[int]) -> int:
        order_id = (self._last_order_id or 0) + 1
        await self._db.execute_many(
            sqlmodel.insert(OrderedItem).values(order_id=order_id),
            [{"item_no": i, "product_id": pid} for i, pid in enumerate(product_ids)],
        )
        self._last_order_id = order_id
        return order_id

    async def _supply(self, order_id: int, product_id: int):
        query = sqlmodel.update(OrderedItem).where(
            (col(OrderedItem.order_id) == order_id)
            & (col(OrderedItem.product_id) == product_id)
        )
        await self._db.execute(query, {"supplied_at": datetime.now(timezone.utc)})

    async def _supply_all(self, order_id: int):
        """
        Use `supply_all_and_complete` when the `completed_at` fields of
        `orders` table should be updated as well.
        """
        clause = col(OrderedItem.order_id) == order_id
        query = sqlmodel.update(OrderedItem).where(clause)
        await self._db.execute(query, {"supplied_at": datetime.now(timezone.utc)})

    # NOTE: this function needs authorization since it destroys all receipts
    # async def clear(self) -> None:
    #     await self._db.execute(sqlmodel.delete(OrderedItem))
    #     self._last_order_id = None
