# https://dev.to/jaydevm/fastapi-and-htmx-a-modern-approach-to-full-stack-bma

import os

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from databases import Database
from contextlib import asynccontextmanager
import sqlalchemy

DATABASE_URL = "sqlite:///app.db"
database = Database(DATABASE_URL)

DEBUG = True if os.environ.get("ORDER_SYSTEM_DEBUG") else False

products_table = sqlalchemy.Table(
    "products",
    sqlalchemy.MetaData(),
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("product_id", sqlalchemy.Integer),
    sqlalchemy.Column("name", sqlalchemy.String(length=40)),
    sqlalchemy.Column("filename", sqlalchemy.String(length=100)),
)


# https://stackoverflow.com/a/65270864
# https://fastapi.tiangolo.com/advanced/events/
@asynccontextmanager
async def lifespan(_: FastAPI):
    await database.connect()

    schema = sqlalchemy.schema.CreateTable(products_table, if_not_exists=True)
    await database.execute(str(schema.compile()))
    if await database.fetch_one(products_table.select()) is None:
        # TODO: read this data from csv or something
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
            5: {"name": "カプチーノコーヒー", "filename": "/coffee05_cappuccino.png"},
            6: {"name": "カフェラテコーヒー", "filename": "/coffee06_cafelatte.png"},
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
            12: {"name": "エスプレッソコーヒー", "filename": "/coffee12_espresso.png"},
            # Tea
            13: {"name": "レモンティー", "filename": "/tea_lemon.png"},
            14: {"name": "ミルクティー", "filename": "/tea_milk.png"},
            15: {"name": "ストレイトティー", "filename": "/tea_straight.png"},
            # Others
            16: {"name": "シュガー", "filename": "/cooking_sugar_stick.png"},
            17: {"name": "ミルクシロップ", "filename": "/sweets_milk_cream.png"},
        }
        await database.execute_many(
            products_table.insert(),
            [{"product_id": product_id, **d} for product_id, d in products.items()],
        )

    yield

    await database.disconnect()


app = FastAPI(debug=DEBUG, lifespan=lifespan)
if DEBUG:
    templates = Jinja2Templates(
        directory="app/templates", extensions=["jinja2.ext.debug"]
    )
else:
    templates = Jinja2Templates(directory="app/templates")


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def get_root(request: Request):
    return templates.TemplateResponse(
        "hello.html", {"request": request, "name": "world"}
    )


list_items: dict[int, dict[str, str] | None] = {}


# TODO: return a page with a newly generated UUID: /order?session_id={uuid}
@app.get("/order", response_class=HTMLResponse)
async def get_order(request: Request):
    products = {
        row[1]: {"name": row[2], "filename": row[3]}
        for row in await database.fetch_all(products_table.select())
    }
    idx_list_item_pairs = [
        (idx, list_item)
        for idx, list_item in list_items.items()
        if list_item is not None
    ]
    return templates.TemplateResponse(
        "order.html",
        {
            "request": request,
            "products": products,
            "idx_list_item_pairs": idx_list_item_pairs,
        },
    )


@app.post("/order/list-item", response_class=HTMLResponse)
async def post_order_list_item(request: Request, product_id: int):
    row = await database.fetch_one(
        products_table.select().where(products_table.c.product_id == product_id)
    )
    if row is None:
        return
    product = {"name": row[2], "filename": row[3]}
    index = len(list_items.keys())
    list_items[index] = product
    return templates.TemplateResponse(
        "components/list-item.html",
        {"request": request, "product": product, "index": index},
    )


@app.delete("/order/list-item", response_class=HTMLResponse)
async def delete_order_list_item(index: int):
    list_items[index] = None
