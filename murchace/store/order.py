from databases import Database
from sqlalchemy import sql
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.expression import Grouping
from sqlalchemy.sql.sqltypes import Integer

from .base import Base


class Order(Base):
    __tablename__ = "orders"

    order_id: Mapped[int]
    ordered_at: Mapped[int] = mapped_column(
        server_default=Grouping(sql.func.unixepoch())
    )
    canceled_at: Mapped[int | None] = mapped_column(Integer, default=None)
    completed_at: Mapped[int | None] = mapped_column(Integer, default=None)


class Table:
    _db: Database

    def __init__(self, database: Database):
        self._db = database

    @staticmethod
    def _update(order_id: int) -> sql.Update:
        return sql.update(Order).where(Order.order_id == order_id)

    async def cancel(self, order_id: int) -> None:
        values = {Order.canceled_at: sql.func.unixepoch(), Order.completed_at: None}
        await self._db.execute(self._update(order_id).values(values))

    async def by_order_id(self, order_id: int) -> Order | None:
        query = sql.select(Order).where(Order.order_id == order_id)
        maybe_record = await self._db.fetch_one(query)
        if (record := maybe_record) is None:
            return None
        return Order(**record._mapping)

    async def select_all(self) -> list[Order]:
        query = sql.select(Order)
        return [Order(**m) async for m in self._db.iterate(query)]
