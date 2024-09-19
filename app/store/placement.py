from datetime import datetime, timezone
from typing import Annotated

import sqlmodel
from databases import Database


class Placement(sqlmodel.SQLModel, table=True):
    # NOTE: there are no Pydantic ways to set the generated table's name, as per https://github.com/fastapi/sqlmodel/issues/159
    __tablename__ = "placements"  # pyright: ignore[reportAssignmentType]

    id: int | None = sqlmodel.Field(default=None, primary_key=True)
    placement_id: int
    # Column(..., server_default=sqlalchemy.text("0"))
    canceled: Annotated[
        bool, sqlmodel.Field(sa_column_kwargs={"server_default": sqlmodel.text("0")})
    ]
    # Column(..., server_default=sqlalchemy.text("0"))
    completed: Annotated[
        bool, sqlmodel.Field(sa_column_kwargs={"server_default": sqlmodel.text("0")})
    ]
    placed_at: Annotated[
        datetime,
        sqlmodel.Field(
            sa_column_kwargs={"server_default": sqlmodel.text("CURRENT_TIMESTAMP")}
        ),
    ]
    completed_at: datetime | None = sqlmodel.Field(
        default=None, sa_column=sqlmodel.Column(sqlmodel.DateTime(timezone=True))
    )


class Table:
    def __init__(self, database: Database):
        self._db = database

    async def insert(self, placement_id: int) -> None:
        query = sqlmodel.insert(Placement)
        await self._db.execute(query, {"placement_id": placement_id})

    async def update(self, placement_id: int, canceled: bool, completed: bool) -> None:
        clause = Placement.placement_id == placement_id
        # NOTE: I don't why, but this where clause argument does not typecheck
        query = sqlmodel.update(Placement).where(clause)  # pyright: ignore[reportArgumentType]
        values = {
            "canceled": canceled,
            "completed": completed,
            "completed_at": datetime.now(timezone.utc) if completed else None,
        }
        await self._db.execute(query, values)

    async def cancel(self, placement_id: int) -> None:
        await self.update(placement_id, canceled=True, completed=False)

    async def complete(self, placement_id: int) -> None:
        await self.update(placement_id, canceled=False, completed=True)

    async def reset(self, placement_id: int) -> None:
        await self.update(placement_id, canceled=False, completed=False)

    async def by_placement_id(self, placement_id: int) -> Placement | None:
        query = sqlmodel.select(Placement).where(Placement.placement_id == placement_id)
        row = await self._db.fetch_one(query)
        return Placement.model_validate(row) if row else None

    async def select_all(self) -> list[Placement]:
        query = sqlmodel.select(Placement)
        return [Placement.model_validate(m) async for m in self._db.iterate(query)]
