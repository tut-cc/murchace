from databases import Database
from sqlalchemy import sql
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import ForeignKey
from sqlalchemy.sql.sqltypes import Integer

from .base import Base
from .order import Order
from .product import Product


class OrderedItem(Base):
    __tablename__ = "ordered_items"

    order_id: Mapped[int] = mapped_column(ForeignKey(Order.order_id))
    item_no: Mapped[int]
    product_id: Mapped[int] = mapped_column(ForeignKey(Product.product_id))
    count: Mapped[int]
    supplied_at: Mapped[int | None] = mapped_column(Integer, default=None)


class Table:
    _db: Database

    def __init__(self, database: Database):
        self._db = database

    async def select_all(self) -> list[OrderedItem]:
        query = sql.select(OrderedItem)
        return [OrderedItem(**m) async for m in self._db.iterate(query)]

    async def by_order_id(self, order_id: int) -> list[OrderedItem]:
        query = sql.select(OrderedItem).where(OrderedItem.order_id == order_id)
        return [OrderedItem(**m) async for m in self._db.iterate(query)]

    # NOTE: this function needs authorization since it destroys all receipts
    # async def clear(self) -> None:
    #     await self._db.execute(sql.delete(OrderedItem))
    #     self._last_order_id = None
