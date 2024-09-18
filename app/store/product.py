from typing import Annotated

from databases import Database
import sqlmodel


class Product(sqlmodel.SQLModel, table=True):
    # NOTE: there are no Pydantic ways to set the generated table's name, as per https://github.com/fastapi/sqlmodel/issues/159
    __tablename__ = "products"  # type: ignore[reportAssignmentType]

    id: int | None = sqlmodel.Field(default=None, primary_key=True)
    product_id: int
    # Column(..., String(length=40))
    name: Annotated[str, sqlmodel.Field(max_length=40)]
    # Column(..., String(length=100))
    filename: Annotated[str, sqlmodel.Field(max_length=40)]
    price: int
    no_stock: int | None  # Column(..., nullable=True)

    def price_str(self) -> str:
        return self.to_price_str(self.price)

    @staticmethod
    def to_price_str(price: int) -> str:
        return f"¥{price}"


class Table:
    def __init__(self, database: Database):
        self._db = database

    async def ainit(self) -> None:
        if not await self._empty():
            return

        # TODO: read this data from CSV or something
        products = [
            # Coffee
            {
                "product_id": 1,
                "name": "ブレンドコーヒー",
                "filename": "coffee01_blend.png",
                "price": 150,
                "no_stock": 100,
            },
            {
                "product_id": 2,
                "name": "アメリカンコーヒー",
                "filename": "coffee02_american.png",
                "price": 150,
                "no_stock": 100,
            },
            {
                "product_id": 3,
                "name": "カフェオレコーヒー",
                "filename": "coffee03_cafeole.png",
                "price": 150,
                "no_stock": 100,
            },
            {
                "product_id": 4,
                "name": "ブレンドブラックコーヒー",
                "filename": "coffee04_blend_black.png",
                "price": 150,
                "no_stock": 100,
            },
            {
                "product_id": 5,
                "name": "カプチーノコーヒー",
                "filename": "coffee05_cappuccino.png",
                "price": 150,
                "no_stock": 100,
            },
            {
                "product_id": 6,
                "name": "カフェラテコーヒー",
                "filename": "coffee06_cafelatte.png",
                "price": 150,
                "no_stock": 100,
            },
            {
                "product_id": 7,
                "name": "マキアートコーヒー",
                "filename": "coffee07_cafe_macchiato.png",
                "price": 150,
                "no_stock": 100,
            },
            {
                "product_id": 8,
                "name": "モカコーヒー",
                "filename": "coffee08_cafe_mocha.png",
                "price": 150,
                "no_stock": 100,
            },
            {
                "product_id": 9,
                "name": "カラメルコーヒー",
                "filename": "coffee09_caramel_macchiato.png",
                "price": 150,
                "no_stock": 100,
            },
            {
                "product_id": 10,
                "name": "アイスコーヒー",
                "filename": "coffee10_iced_coffee.png",
                "price": 150,
                "no_stock": 100,
            },
            {
                "product_id": 11,
                "name": "アイスミルクコーヒー",
                "filename": "coffee11_iced_milk_coffee.png",
                "price": 150,
                "no_stock": 100,
            },
            {
                "product_id": 12,
                "name": "エスプレッソコーヒー",
                "filename": "coffee12_espresso.png",
                "price": 150,
                "no_stock": 100,
            },
            # Tea
            {
                "product_id": 13,
                "name": "レモンティー",
                "filename": "tea_lemon.png",
                "price": 100,
                "no_stock": 100,
            },
            {
                "product_id": 14,
                "name": "ミルクティー",
                "filename": "tea_milk.png",
                "price": 100,
                "no_stock": 100,
            },
            {
                "product_id": 15,
                "name": "ストレイトティー",
                "filename": "tea_straight.png",
                "price": 100,
                "no_stock": 100,
            },
            # Others
            {
                "product_id": 16,
                "name": "シュガー",
                "filename": "cooking_sugar_stick.png",
                "price": 0,
                "no_stock": None,
            },
            {
                "product_id": 17,
                "name": "ミルクシロップ",
                "filename": "sweets_milk_cream.png",
                "price": 0,
                "no_stock": None,
            },
        ]
        await self._insert_many([Product.model_validate(obj) for obj in products])

    async def _empty(self) -> bool:
        return await self._db.fetch_one(sqlmodel.select(Product)) is None

    async def _insert_many(self, products: list[Product]) -> None:
        query = sqlmodel.insert(Product)
        await self._db.execute_many(query, [p.model_dump() for p in products])

    async def select_all(self) -> list[Product]:
        query = sqlmodel.select(Product)
        return [Product.model_validate(m) async for m in self._db.iterate(query)]

    async def by_product_id(self, product_id: int) -> Product | None:
        query = sqlmodel.select(Product).where(Product.product_id == product_id)
        row = await self._db.fetch_one(query)
        return Product.model_validate(row) if row else None
