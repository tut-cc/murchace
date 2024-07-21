from abc import ABC, abstractmethod

import sqlalchemy
from databases import Database
from pydantic import BaseModel

DATABASE_URL = "sqlite:///app.db"
db = Database(DATABASE_URL)


class Table(ABC):
    TABLE: sqlalchemy.Table

    @classmethod
    @abstractmethod
    async def ainit(cls) -> None:
        pass

    @classmethod
    async def create_if_not_exists(cls) -> None:
        schema = sqlalchemy.schema.CreateTable(cls.TABLE, if_not_exists=True)
        await db.execute(str(schema.compile()))

    @classmethod
    async def empty(cls) -> bool:
        return await db.fetch_one(cls.TABLE.select()) is None


# TODO: add price field
# TODO: add no. stock field
class Product(BaseModel):
    product_id: int
    name: str
    filename: str


class ProductTable(Table):
    TABLE = sqlalchemy.Table(
        "products",
        sqlalchemy.MetaData(),
        sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
        sqlalchemy.Column("product_id", sqlalchemy.Integer),
        sqlalchemy.Column("name", sqlalchemy.String(length=40)),
        sqlalchemy.Column("filename", sqlalchemy.String(length=100)),
    )

    @classmethod
    async def ainit(cls) -> None:
        await cls.create_if_not_exists()

        if await cls.empty():
            # TODO: read this data from CSV or something
            # id: int32, name: string, filename: string
            products: dict[int, dict[str, str]] = {
                # Coffee
                1: {"name": "ブレンドコーヒー", "filename": "/coffee01_blend.png"},
                2: {"name": "アメリカンコーヒー", "filename": "/coffee02_american.png"},
                3: {"name": "カフェオレコーヒー", "filename": "/coffee03_cafeole.png"},
                4: {
                    "name": "ブレンドブラックコーヒー",
                    "filename": "/coffee04_blend_black.png",
                },
                5: {
                    "name": "カプチーノコーヒー",
                    "filename": "/coffee05_cappuccino.png",
                },
                6: {
                    "name": "カフェラテコーヒー",
                    "filename": "/coffee06_cafelatte.png",
                },
                7: {
                    "name": "マキアートコーヒー",
                    "filename": "/coffee07_cafe_macchiato.png",
                },
                8: {"name": "モカコーヒー", "filename": "/coffee08_cafe_mocha.png"},
                9: {
                    "name": "カラメルコーヒー",
                    "filename": "/coffee09_caramel_macchiato.png",
                },
                10: {"name": "アイスコーヒー", "filename": "/coffee10_iced_coffee.png"},
                11: {
                    "name": "アイスミルクコーヒー",
                    "filename": "/coffee11_iced_milk_coffee.png",
                },
                12: {
                    "name": "エスプレッソコーヒー",
                    "filename": "/coffee12_espresso.png",
                },
                # Tea
                13: {"name": "レモンティー", "filename": "/tea_lemon.png"},
                14: {"name": "ミルクティー", "filename": "/tea_milk.png"},
                15: {"name": "ストレイトティー", "filename": "/tea_straight.png"},
                # Others
                16: {"name": "シュガー", "filename": "/cooking_sugar_stick.png"},
                17: {"name": "ミルクシロップ", "filename": "/sweets_milk_cream.png"},
            }
            await cls.insert_many(
                [
                    Product(**{"product_id": product_id, **d})
                    for product_id, d in products.items()
                ],
            )

    @classmethod
    async def select_all(cls) -> list[Product]:
        return [Product(**dict(row)) for row in await db.fetch_all(cls.TABLE.select())]

    @classmethod
    async def by_product_id(cls, product_id: int) -> Product | None:
        query = cls.TABLE.select().where(cls.TABLE.c.product_id == product_id)
        return (
            None if (row := await db.fetch_one(query)) is None else Product(**dict(row))
        )

    @classmethod
    async def insert_many(cls, products: list[Product]) -> None:
        await db.execute_many(
            cls.TABLE.insert(),
            [p.model_dump() for p in products],
        )


class PlacedOrder(BaseModel):
    placement_id: int
    item_no: int
    product_id: int


class PlacedOrderTable(Table):
    TABLE = sqlalchemy.Table(
        "placed_orders",
        sqlalchemy.MetaData(),
        sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
        sqlalchemy.Column("placement_id", sqlalchemy.Integer),
        sqlalchemy.Column("item_no", sqlalchemy.Integer),
        sqlalchemy.Column("product_id", sqlalchemy.Integer),
    )

    last_placement_id: int | None

    @classmethod
    async def ainit(cls) -> None:
        await cls.create_if_not_exists()
        await cls.update_last_placement_id()

    @classmethod
    async def update_last_placement_id(cls) -> None:
        cls.last_placement_id = await db.fetch_val(
            sqlalchemy.sql.expression.func.max(cls.TABLE.c.placement_id).select()
        )

    @classmethod
    async def select_all(cls) -> list[PlacedOrder]:
        return [
            PlacedOrder(**dict(row)) for row in await db.fetch_all(cls.TABLE.select())
        ]

    @classmethod
    async def by_placement_id(cls, placement_id: int) -> list[PlacedOrder]:
        query = cls.TABLE.select().where(cls.TABLE.c.placement_id == placement_id)
        return [PlacedOrder(**dict(row)) for row in await db.fetch_all(query)]

    @classmethod
    async def issue(cls, product_ids: list[int]) -> int:
        placement_id = (cls.last_placement_id or 0) + 1
        await db.execute_many(
            cls.TABLE.insert().values(placement_id=placement_id),
            [
                {"item_no": idx, "product_id": product_id}
                for idx, product_id in enumerate(product_ids)
            ],
        )
        cls.last_placement_id = placement_id
        return placement_id

    # NOTE: this function needs authorization since it destroys all receipts
    #
    @classmethod
    async def clear(cls) -> None:
        await db.execute(cls.TABLE.delete())
        await cls.update_last_placement_id()


class PlacementStatus(BaseModel):
    placement_id: int
    canceled: bool
    done: bool


class PlacementStatusTable(Table):
    TABLE = sqlalchemy.Table(
        "placements",
        sqlalchemy.MetaData(),
        sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
        sqlalchemy.Column("placement_id", sqlalchemy.Integer),
        sqlalchemy.Column(
            "canceled", sqlalchemy.Boolean, server_default=sqlalchemy.text("0")
        ),
        sqlalchemy.Column(
            "done", sqlalchemy.Boolean, server_default=sqlalchemy.text("0")
        ),
    )

    @classmethod
    async def ainit(cls) -> None:
        await cls.create_if_not_exists()

    @classmethod
    async def insert(cls, placement_id: int):
        await db.execute(cls.TABLE.insert(), {"placement_id": placement_id})

    @classmethod
    async def update(cls, placement_id: int, canceled: bool, done: bool):
        query = cls.TABLE.update().where(cls.TABLE.c.placement_id == placement_id)
        await db.execute(query, {"canceled": canceled, "done": done})

    @classmethod
    async def cancel(cls, placement_id: int):
        await cls.update(placement_id, canceled=True, done=False)

    @classmethod
    async def done(cls, placement_id: int):
        await cls.update(placement_id, canceled=False, done=True)

    @classmethod
    async def reset(cls, placement_id: int):
        await cls.update(placement_id, canceled=False, done=False)

    @classmethod
    async def select_all(cls) -> list[PlacementStatus]:
        return [
            PlacementStatus(**dict(row))
            for row in await db.fetch_all(cls.TABLE.select())
        ]


async def _startup_db():
    await db.connect()
    await ProductTable.ainit()
    await PlacedOrderTable.ainit()
    await PlacementStatusTable.ainit()


async def _shutdown_db():
    await db.disconnect()


startup_and_shutdown_db = (_startup_db, _shutdown_db)
