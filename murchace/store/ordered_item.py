from datetime import UTC, datetime

import sqlalchemy.sql.expression as sa_exp
from databases import Database
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import ForeignKey
from sqlalchemy.sql.functions import func as sa_func
from sqlalchemy.sql.sqltypes import DateTime

from .base import Base
from .order import Order
from .product import Product


class OrderedItem(Base):
    __tablename__ = "ordered_items"

    order_id: Mapped[int] = mapped_column(ForeignKey(Order.order_id))
    item_no: Mapped[int]
    product_id: Mapped[int] = mapped_column(ForeignKey(Product.product_id))
    supplied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )


class Table:
    _last_order_id: int | None
    _db: Database

    def __init__(self, database: Database):
        self._db = database

    async def ainit(self) -> None:
        query = sa_func.max(OrderedItem.order_id).select()
        self._last_order_id = await self._db.fetch_val(query)

    async def select_all(self) -> list[OrderedItem]:
        query = sa_exp.select(OrderedItem)
        return [OrderedItem(**m) async for m in self._db.iterate(query)]

    async def by_order_id(self, order_id: int) -> list[OrderedItem]:
        query = sa_exp.select(OrderedItem).where(OrderedItem.order_id == order_id)
        return [OrderedItem(**m) async for m in self._db.iterate(query)]

    async def issue(self, product_ids: list[int]) -> int:
        order_id = (self._last_order_id or 0) + 1
        await self._db.execute_many(
            sa_exp.insert(OrderedItem).values(order_id=order_id),
            [{"item_no": i, "product_id": pid} for i, pid in enumerate(product_ids)],
        )
        self._last_order_id = order_id
        return order_id

    async def _supply(self, order_id: int, product_id: int):
        query = sa_exp.update(OrderedItem).where(
            (OrderedItem.order_id == order_id) & (OrderedItem.product_id == product_id)
        )
        await self._db.execute(query, {"supplied_at": datetime.now(UTC)})

    async def _supply_all(self, order_id: int):
        """
        Use `supply_all_and_complete` when the `completed_at` fields of
        `orders` table should be updated as well.
        """
        query = sa_exp.update(OrderedItem).where(OrderedItem.order_id == order_id)
        await self._db.execute(query, {"supplied_at": datetime.now(UTC)})

    # NOTE: this function needs authorization since it destroys all receipts
    # async def clear(self) -> None:
    #     await self._db.execute(sa_exp.delete(OrderedItem))
    #     self._last_order_id = None
