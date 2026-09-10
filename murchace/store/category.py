from dataclasses import asdict

import sqlalchemy.sql.expression as sae
from databases import Database
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.sqltypes import String

from .base import Base


class Category(Base):
    __tablename__ = "categories"

    category_id: Mapped[int]
    name: Mapped[str] = mapped_column(String(length=40))


class Table:
    def __init__(self, database: Database):
        self._db = database

    async def ainit(self) -> None:
        if not await self._empty():
            return
        await self.renew_from_static_csv()

    # TODO: This function is defined temporally for convenience and should be removed in the future.
    async def renew_from_static_csv(self, csv_file: str = "static/category-list.csv"):
        import csv
        from collections.abc import Iterable

        def decomment(csv_rows: Iterable[str]):
            for row in csv_rows:
                row_body = row.split("#")[0].strip()
                if row_body != "":
                    yield row_body

        categories: list[Category] = []
        with open(csv_file) as f:  # noqa: ASYNC230
            reader = csv.DictReader(
                decomment(f), dialect="unix", quoting=csv.QUOTE_STRINGS, strict=True
            )
            for csv_row in reader:
                assert all(isinstance(k, str) for k in csv_row)
                categories.append(Category(**dict(**csv_row)))  # ty: ignore[invalid-argument-type]

        async with self._db.transaction():
            await self._db.execute(sae.delete(Category))
            await self._insert_many(categories)

    async def _empty(self) -> bool:
        return await self._db.fetch_one(sae.select(Category)) is None

    async def _insert_many(self, categories: list[Category]) -> None:
        query = sae.insert(Category)
        await self._db.execute_many(query, [asdict(c) for c in categories])

    async def select_all(self) -> list[Category]:
        query = sae.select(Category).order_by(Category.category_id.asc())
        return [Category(**m) async for m in self._db.iterate(query)]
