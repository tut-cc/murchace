from dataclasses import dataclass

import sqlalchemy
from databases import Database


@dataclass
class Product:
    product_id: int
    name: str
    filename: str


class ProductTable:
    _table = sqlalchemy.Table(
        "products",
        sqlalchemy.MetaData(),
        sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
        sqlalchemy.Column("product_id", sqlalchemy.Integer),
        sqlalchemy.Column("name", sqlalchemy.String(length=40)),
        sqlalchemy.Column("filename", sqlalchemy.String(length=100)),
    )

    def __init__(self, db: Database):
        self._db = db

    async def create_if_not_exists(self) -> None:
        schema = sqlalchemy.schema.CreateTable(self._table, if_not_exists=True)
        await self._db.execute(str(schema.compile()))

    async def select_all(self) -> list[Product]:
        return [
            Product(row["product_id"], row["name"], row["filename"])
            for row in await self._db.fetch_all(self._table.select())
        ]

    async def empty(self) -> bool:
        return await self._db.fetch_one(self._table.select()) is None

    async def by_product_id(self, product_id: int) -> Product | None:
        query = self._table.select().where(self._table.c.product_id == product_id)
        return (
            None
            if (row := await self._db.fetch_one(query)) is None
            else Product(row["product_id"], row["name"], row["filename"])
        )

    async def insert_many(self, products: list[Product]) -> None:
        await self._db.execute_many(self._table.insert(), products)
