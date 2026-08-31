from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from htpy import Element, HTMLElement, a, div, p

from .components import page_layout
from .env import DEBUG
from .routers import orders, products, register, stat
from .store import startup_and_shutdown_db


# https://stackoverflow.com/a/65270864
# https://fastapi.tiangolo.com/advanced/events/
@asynccontextmanager
async def lifespan(_: FastAPI):
    startup_db, shutdown_db = startup_and_shutdown_db
    await startup_db()
    yield
    await shutdown_db()


app = FastAPI(debug=DEBUG, lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")


def _link_box(href: str, text: str) -> Element:
    return a(
        href=href,
        class_="flex items-center justify-center pt-2 border-2 border-gray-500 rounded-2xl cursor-pointer",
    )[p[text]]


def page_index(request: Request) -> HTMLElement:
    inner = div(
        class_="w-full h-dvh px-16 py-8 grid grid-cols-1 lg:grid-cols-2 gap-12 text-4xl"
    )[
        _link_box("/register", "新しい注文"),
        _link_box("/orders/incoming", "確定注文一覧"),
        _link_box("/wait-estimates", "予測待ち時間"),
        _link_box("/stat", "統計情報"),
        _link_box("/products", "商品編集（実装中）"),
        a(
            class_="flex items-center justify-center pt-2 border-2 border-gray-500 rounded-2xl cursor-not-allowed",
        )[p["設定（未実装）"]],
    ]
    return page_layout(request, inner, title="ホーム - murchace")


@app.get("/", response_class=HTMLResponse)
async def get_root(request: Request):
    return HTMLResponse(page_index(request))


app.include_router(products.router)
app.include_router(register.router)
app.include_router(orders.router)
app.include_router(stat.router)
