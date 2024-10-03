import asyncio
from datetime import datetime, timezone
from typing import Annotated

import sqlalchemy
import sqlmodel
from databases import Database
from sqlmodel import col


class Placement(sqlmodel.SQLModel, table=True):
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


class Table:
    modified: asyncio.Condition = asyncio.Condition()

    def __init__(self, database: Database):
        self._db = database

    async def insert(self, placement_id: int) -> None:
        query = sqlmodel.insert(Placement)
        await self._db.execute(query, {"placement_id": placement_id})
        async with self.modified:
            self.modified.notify_all()

    @staticmethod
    def _update(placement_id: int) -> sqlalchemy.Update:
        clause = col(Placement.placement_id) == placement_id
        return sqlmodel.update(Placement).where(clause)

    async def cancel(self, placement_id: int) -> None:
        values = {"canceled_at": datetime.now(timezone.utc), "completed_at": None}
        await self._db.execute(self._update(placement_id), values)
        async with self.modified:
            self.modified.notify_all()

    async def complete(self, placement_id: int) -> None:
        values = {"canceled_at": None, "completed_at": datetime.now(timezone.utc)}
        await self._db.execute(self._update(placement_id), values)
        async with self.modified:
            self.modified.notify_all()

    async def reset(self, placement_id: int) -> None:
        values = {"canceled_at": None, "completed_at": None}
        await self._db.execute(self._update(placement_id), values)
        async with self.modified:
            self.modified.notify_all()

    async def by_placement_id(self, placement_id: int) -> Placement | None:
        query = sqlmodel.select(Placement).where(Placement.placement_id == placement_id)
        row = await self._db.fetch_one(query)
        return Placement.model_validate(row) if row else None

    async def select_all(self) -> list[Placement]:
        query = sqlmodel.select(Placement)
        return [Placement.model_validate(m) async for m in self._db.iterate(query)]
