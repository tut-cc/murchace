import asyncio
from datetime import datetime, timezone
from enum import Flag, auto
from typing import Annotated

import sqlalchemy
import sqlmodel
from databases import Database
from sqlmodel import col

from .base import TableBase


class Order(TableBase, table=True):
    # NOTE: there are no Pydantic ways to set the generated table's name, as per https://github.com/fastapi/sqlmodel/issues/159
    __tablename__ = "placements"  # pyright: ignore[reportAssignmentType]

    id: int | None = sqlmodel.Field(default=None, primary_key=True)
    placement_id: int
    placed_at: Annotated[
        datetime,
        sqlmodel.Field(
            sa_column_kwargs={"server_default": sqlmodel.text("CURRENT_TIMESTAMP")}
        ),
    ]
    canceled_at: datetime | None = sqlmodel.Field(
        default=None, sa_column=sqlmodel.Column(sqlmodel.DateTime(timezone=True))
    )
    completed_at: datetime | None = sqlmodel.Field(
        default=None, sa_column=sqlmodel.Column(sqlmodel.DateTime(timezone=True))
    )


class ModifiedFlag(Flag):
    ORIGINAL = auto()
    INCOMING = auto()
    SUPPLIED = auto()
    RESOLVED = auto()
    PUT_BACK = auto()


class ModifiedCondFlag:
    _condvar: asyncio.Condition
    _flag: ModifiedFlag

    def __init__(self):
        self._condvar = asyncio.Condition()
        self._flag = ModifiedFlag.ORIGINAL

    async def __aenter__(self):
        await self._condvar.__aenter__()

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self._condvar.__aexit__(exc_type, exc, tb)

    async def wait(self) -> ModifiedFlag:
        await self._condvar.wait()
        flag = self._flag
        if len(self._condvar._waiters) == 0:
            self._flag = ModifiedFlag.ORIGINAL
        return flag

    def notify_all(self, flag: ModifiedFlag):
        self._flag |= flag
        self._condvar.notify_all()


class Table:
    modified_cond_flag = ModifiedCondFlag()

    def __init__(self, database: Database):
        self._db = database

    async def insert(self, placement_id: int) -> None:
        query = sqlmodel.insert(Order)
        await self._db.execute(query, {"placement_id": placement_id})
        async with self.modified_cond_flag:
            self.modified_cond_flag.notify_all(ModifiedFlag.INCOMING)

    @staticmethod
    def _update(placement_id: int) -> sqlalchemy.Update:
        clause = col(Order.placement_id) == placement_id
        return sqlmodel.update(Order).where(clause)

    async def cancel(self, placement_id: int) -> None:
        values = {"canceled_at": datetime.now(timezone.utc), "completed_at": None}
        await self._db.execute(self._update(placement_id), values)
        async with self.modified_cond_flag:
            self.modified_cond_flag.notify_all(ModifiedFlag.RESOLVED)

    async def _complete(self, placement_id: int) -> None:
        """
        Use `supply_all_and_complete` when the `supplied_at` fields of
        `ordered_items` table should be updated as well.
        """
        values = {"canceled_at": None, "completed_at": datetime.now(timezone.utc)}
        await self._db.execute(self._update(placement_id), values)

    async def reset(self, placement_id: int) -> None:
        values = {"canceled_at": None, "completed_at": None}
        await self._db.execute(self._update(placement_id), values)
        async with self.modified_cond_flag:
            self.modified_cond_flag.notify_all(ModifiedFlag.PUT_BACK)

    async def by_placement_id(self, placement_id: int) -> Order | None:
        query = sqlmodel.select(Order).where(Order.placement_id == placement_id)
        row = await self._db.fetch_one(query)
        return Order.model_validate(row) if row else None

    async def select_all(self) -> list[Order]:
        query = sqlmodel.select(Order)
        return [Order.model_validate(m) async for m in self._db.iterate(query)]
