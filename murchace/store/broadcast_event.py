import os
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import NamedTuple

import sqlalchemy.sql.expression as sa_exp
from databases import Database
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class BroadcastEvent(Base):
    __tablename__ = "broadcast_events"

    flag: Mapped[int]
    worker_pid: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(
        server_default=sa_exp.text("CURRENT_TIMESTAMP")
    )


class EventRecord(NamedTuple):
    id: int
    flag: int
    worker_pid: int


class Table:
    def __init__(self, database: Database):
        self._db = database

    async def insert(self, flag: int) -> int:
        query = (
            sa_exp.insert(BroadcastEvent)
            .values(
                flag=flag,
                worker_pid=os.getpid(),
                created_at=datetime.now(UTC),
            )
            .returning(BroadcastEvent.id)
        )
        val = await self._db.fetch_val(query)
        assert val is not None
        return int(val)

    async def get_latest_id(self) -> int:
        query = sa_exp.select(sa_exp.func.max(BroadcastEvent.id))
        val = await self._db.fetch_val(query)
        return int(val) if val is not None else 0

    async def fetch_after(self, after_id: int) -> Sequence[EventRecord]:
        query = (
            sa_exp.select(
                BroadcastEvent.id,
                BroadcastEvent.flag,
                BroadcastEvent.worker_pid,
            )
            .where(BroadcastEvent.id > after_id)
            .order_by(BroadcastEvent.id.asc())
        )
        records = await self._db.fetch_all(query)
        return [
            EventRecord(
                id=int(r[0]),
                flag=int(r[1]),
                worker_pid=int(r[2]),
            )
            for r in records
        ]

    async def prune(self, before_id: int) -> None:
        if before_id > 0:
            query = sa_exp.delete(BroadcastEvent).where(BroadcastEvent.id < before_id)
            await self._db.execute(query)
