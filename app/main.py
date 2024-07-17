import os
from contextlib import asynccontextmanager

from databases import Database
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .db import Product, ProductTable

DATABASE_URL = "sqlite:///app.db"
database = Database(DATABASE_URL)

DEBUG = True if os.environ.get("ORDER_SYSTEM_DEBUG") else False

product_table = ProductTable(database)


# https://stackoverflow.com/a/65270864
# https://fastapi.tiangolo.com/advanced/events/
@asynccontextmanager
async def lifespan(_: FastAPI):
    await database.connect()

    await product_table.create_if_not_exists()
    if await product_table.empty():
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
        await product_table.insert_many(
            [
                Product(product_id, d["name"], d["filename"])
                for product_id, d in products.items()
            ],
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


# NOTE: I am not sure if these data should be stored in database or not.
item_list_sessions: dict[int, list[Product | None]] = {}


@app.get("/order", response_class=RedirectResponse)
async def get_order_redirect():
    return RedirectResponse("/order/new")


@app.get("/order/new", response_class=RedirectResponse)
async def get_order_new():
    new_session_id = len(item_list_sessions.keys())
    item_list_sessions[new_session_id] = []
    return RedirectResponse(f"/order/{new_session_id}")


@app.get("/order/{session_id}", response_class=HTMLResponse)
async def get_order(request: Request, session_id: int):
    item_list = item_list_sessions.get(session_id)
    if item_list is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    idx_item_pairs = [
        (idx, item) for idx, item in enumerate(item_list) if item is not None
    ]
    return templates.TemplateResponse(
        "order.html",
        {
            "request": request,
            "products": await product_table.select_all(),
            "session_id": session_id,
            "idx_item_pairs": idx_item_pairs,
        },
    )


@app.post("/order/{session_id}/item", response_class=HTMLResponse)
async def post_order_item(request: Request, session_id: int, product_id: int):
    if (product := await product_table.by_product_id(product_id)) is None:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    if (item_list := item_list_sessions.get(session_id)) is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    index = len(item_list)
    item_list.append(product)
    return templates.TemplateResponse(
        "components/item.html",
        {
            "request": request,
            "product": product,
            "session_id": session_id,
            "index": index,
        },
    )


@app.delete("/order/{session_id}/item/{index}", response_class=HTMLResponse)
async def delete_order_item(session_id: int, index: int):
    item_list = item_list_sessions.get(session_id)
    if item_list is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    if item_list[index] is None:
        raise HTTPException(status_code=404, detail=f"List item {index} not found")
    else:
        item_list[index] = None
