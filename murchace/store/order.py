from datetime import UTC, datetime

import sqlalchemy.sql.expression as sa_exp
from databases import Database
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.sqltypes import DateTime

from .base import Base


class Order(Base):
    __tablename__ = "orders"

    order_id: Mapped[int]
    ordered_at: Mapped[datetime] = mapped_column(
        server_default=sa_exp.text("CURRENT_TIMESTAMP")
    )
    canceled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )


class Table:
    _db: Database

    def __init__(self, database: Database):
        self._db = database

    @staticmethod
    def _update(order_id: int) -> sa_exp.Update:
        return sa_exp.update(Order).where(Order.order_id == order_id)

    async def cancel(self, order_id: int) -> None:
        values = {"canceled_at": datetime.now(UTC), "completed_at": None}
        await self._db.execute(self._update(order_id), values)

    async def _complete(self, order_id: int) -> None:
        """
        Use `supply_all_and_complete` when the `supplied_at` fields of
        `ordered_items` table should be updated as well.
        """
        values = {"canceled_at": None, "completed_at": datetime.now(UTC)}
        await self._db.execute(self._update(order_id), values)

    async def reset(self, order_id: int) -> None:
        values = {"canceled_at": None, "completed_at": None}
        await self._db.execute(self._update(order_id), values)

    async def by_order_id(self, order_id: int) -> Order | None:
        query = sa_exp.select(Order).where(Order.order_id == order_id)
        maybe_record = await self._db.fetch_one(query)
        if (record := maybe_record) is None:
            return None
        return Order(**record._mapping)

    async def select_all(self) -> list[Order]:
        query = sa_exp.select(Order)
        return [Order(**m) async for m in self._db.iterate(query)]
