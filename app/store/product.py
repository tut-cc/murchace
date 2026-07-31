import csv
from collections.abc import Iterable
from dataclasses import asdict
from typing import Any

import sqlalchemy.sql.expression as sae
from databases import Database
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.sqltypes import String

from .base import Base


class Product(Base):
    __tablename__ = "products"

    product_id: Mapped[int]
    name: Mapped[str] = mapped_column(String(length=40))
    filename: Mapped[str] = mapped_column(String(length=100))
    price: Mapped[int]
    no_stock: Mapped[int | None]

    def price_str(self) -> str:
        return self.to_price_str(self.price)

    @staticmethod
    def to_price_str(price: int) -> str:
        return f"¥{price:,}"


class Table:
    def __init__(self, database: Database):
        self._db = database

    async def ainit(self) -> None:
        if not await self._empty():
            return
        await self.renew_from_static_csv()

    # TODO: This function is defined temporally for convenience and should be removed in the future.
    async def renew_from_static_csv(self, csv_file: str = "static/product-list.csv"):
        def decomment(csv_rows: Iterable[str]):
            for row in csv_rows:
                row_body = row.split("#")[0].strip()
                if row_body != "":
                    yield row_body

        products: list[Product] = []
        with open(csv_file) as f:  # noqa: ASYNC230
            reader = csv.DictReader(
                decomment(f), dialect="unix", quoting=csv.QUOTE_STRINGS, strict=True
            )
            for csv_row in reader:
                csv_row: dict[str, Any]
                if csv_row["no_stock"] == "":
                    csv_row["no_stock"] = None
                assert all(isinstance(k, str) for k in csv_row)
                products.append(Product(**dict(**csv_row)))  # ty: ignore[invalid-argument-type]

        async with self._db.transaction():
            await self._db.execute(sae.delete(Product))
            await self._insert_many(products)

    async def _empty(self) -> bool:
        return await self._db.fetch_one(sae.select(Product)) is None

    async def _insert_many(self, products: list[Product]) -> None:
        query = sae.insert(Product)
        await self._db.execute_many(query, [asdict(p) for p in products])

    async def select_all(self) -> list[Product]:
        query = sae.select(Product).order_by(Product.product_id.asc())
        return [Product(**m) async for m in self._db.iterate(query)]

    async def by_product_id(self, product_id: int) -> Product | None:
        query = sae.select(Product).where(Product.product_id == product_id)
        maybe_record = await self._db.fetch_one(query)
        if (record := maybe_record) is None:
            return None
        return Product(**dict(record._mapping))

    async def insert(self, product: Product) -> Product | None:
        query = sae.insert(Product).returning(sae.literal_column("*"))
        maybe_record = await self._db.fetch_one(query, asdict(product))
        if (record := maybe_record) is None:
            return None
        return Product(**record._mapping)

    async def update(self, product_id: int, new_product: Product) -> Product | None:
        dump = asdict(new_product)
        dump.pop("id")

        query = (
            sae.update(Product)
            .where(Product.product_id == product_id)
            .values(**dump)
            .returning(sae.literal_column("*"))
        )
        if product_id != new_product.product_id:
            dest_product_id_occupied = (
                sae.select(Product.product_id)
                .where(Product.product_id == new_product.product_id)
                .exists()
            )
            query = query.where(sae.not_(dest_product_id_occupied))

        maybe_record = await self._db.fetch_one(query)
        if (record := maybe_record) is None:
            return None
        return Product(**dict(record._mapping))
