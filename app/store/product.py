import csv
from typing import Annotated, Iterable
from uuid import UUID, uuid4

import pydantic
import sqlmodel
from databases import Database
from sqlmodel import col


class Product(sqlmodel.SQLModel, table=True):
    # NOTE: there are no Pydantic ways to set the generated table's name, as per https://github.com/fastapi/sqlmodel/issues/159
    __tablename__ = "products"  # pyright: ignore[reportAssignmentType]

    id: int | None = sqlmodel.Field(default=None, primary_key=True)
    product_id: int
    name: Annotated[str, sqlmodel.Field(max_length=40)]
    filename: Annotated[str, sqlmodel.Field(max_length=100)]
    price: int
    no_stock: int | None

    def price_str(self) -> str:
        return self.to_price_str(self.price)

    @staticmethod
    def to_price_str(price: int) -> str:
        return f"¥{price:,}"


class OrderSession(pydantic.BaseModel):
    class CountedProduct(pydantic.BaseModel):
        name: str
        price: str
        count: int = pydantic.Field(default=1)

    items: dict[UUID, Product] = pydantic.Field(default_factory=dict)
    counted_products: dict[int, CountedProduct] = pydantic.Field(default_factory=dict)
    total_count: int = pydantic.Field(default=0)
    total_price: int = pydantic.Field(default=0)

    def clear(self):
        self.total_count = 0
        self.total_price = 0
        self.items = {}
        self.counted_products = {}

    def total_price_str(self) -> str:
        return Product.to_price_str(self.total_price)

    def add(self, p: Product):
        self.total_count += 1
        self.total_price += p.price
        self.items[uuid4()] = p
        if p.product_id in self.counted_products:
            self.counted_products[p.product_id].count += 1
        else:
            counted_product = self.CountedProduct(name=p.name, price=p.price_str())
            self.counted_products[p.product_id] = counted_product

    def delete(self, item_id: UUID):
        if item_id in self.items:
            self.total_count -= 1
            product = self.items.pop(item_id)
            self.total_price -= product.price
            if self.counted_products[product.product_id].count == 1:
                self.counted_products.pop(product.product_id)
            else:
                self.counted_products[product.product_id].count -= 1


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
        with open(csv_file) as f:
            reader = csv.DictReader(
                decomment(f), dialect="unix", quoting=csv.QUOTE_STRINGS, strict=True
            )
            for csv_row in reader:
                if csv_row["no_stock"] == "":
                    csv_row["no_stock"] = None
                products.append(Product.model_validate(csv_row))

        async with self._db.transaction():
            await self._db.execute(sqlmodel.delete(Product))
            await self._insert_many(products)

    async def _empty(self) -> bool:
        return await self._db.fetch_one(sqlmodel.select(Product)) is None

    async def _insert_many(self, products: list[Product]) -> None:
        query = sqlmodel.insert(Product)
        await self._db.execute_many(query, [p.model_dump() for p in products])

    async def select_all(self) -> list[Product]:
        query = sqlmodel.select(Product).order_by(col(Product.product_id).asc())
        return [Product.model_validate(m) async for m in self._db.iterate(query)]

    async def by_product_id(self, product_id: int) -> Product | None:
        query = sqlmodel.select(Product).where(Product.product_id == product_id)
        row = await self._db.fetch_one(query)
        return Product.model_validate(row) if row else None

    async def insert(self, product: Product) -> Product | None:
        query = sqlmodel.insert(Product).returning(sqlmodel.literal_column("*"))
        maybe_record = await self._db.fetch_one(query, product.model_dump())
        if (record := maybe_record) is None:
            return None
        return Product.model_validate(dict(record._mapping))

    async def update(self, product_id: int, new_product: Product) -> Product | None:
        dump = new_product.model_dump()
        dump.pop("id")

        query = (
            sqlmodel.update(Product)
            .where(col(Product.product_id) == product_id)
            .values(**dump)
            .returning(sqlmodel.literal_column("*"))
        )
        if product_id != new_product.product_id:
            dest_product_id_occupied = (
                sqlmodel.select(col(Product.product_id))
                .where(col(Product.product_id) == new_product.product_id)
                .exists()
            )
            query = query.where(sqlmodel.not_(dest_product_id_occupied))

        maybe_record = await self._db.fetch_one(query)
        if (record := maybe_record) is None:
            return None
        return Product.model_validate(dict(record._mapping))
