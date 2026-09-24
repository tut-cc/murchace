from pathlib import Path
from typing import Annotated, Any

import sqlalchemy.sql.expression as sa_exp
from datastar_py import attribute_generator as data
from datastar_py.fastapi import DatastarResponse, read_signals
from datastar_py.sse import ServerSentEventGenerator as SSE
from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from htpy import (
    Element,
    HTMLElement,
    a,
    article,
    aside,
    button,
    div,
    figcaption,
    figure,
    h2,
    img,
    li,
    main,
    p,
    script,
    span,
    ul,
)
from markupsafe import Markup
from sqlalchemy.sql.functions import func as sa_func

from ..components import clock, page_layout
from ..receipt_service import PrinterQueueDeps, build_receipt_data
from ..store import (
    ModifiedFlag,
    Order,
    OrderedItem,
    OrderTable,
    Product,
    ProductTable,
    database,
)

router = APIRouter()


with open(Path(__file__).parent / "register-items.js", encoding="utf-8") as f:
    _register_items_script = script[Markup(f.read())]
    register_items = Element("register-items")


def page_register(req: Request, products: list[Product]) -> HTMLElement:
    return page_layout(
        req,
        register(req, products),
        "新規注文 - murchace",
        head_section=[_register_items_script],
    )


def register(req: Request, products: list[Product]) -> HTMLElement:
    inner = div(
        data.signals({"items": []}).ifmissing,
        {"data-persist": "items"},
        data.computed(
            totalCount="$items.reduce((acc, item) => acc + item.count, 0)",
            totalPriceStr="new Intl.NumberFormat('ja-JP', {style: 'currency', currency: 'JPY'}).format($items.reduce((sum, item) => sum + item.count * item.price, 0))",
        ),
        id="register",
        class_="h-dvh flex flex-row",
    )[
        main(
            id="products",
            class_="w-1/2 lg:w-4/6 h-full grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 2xl:grid-cols-6 auto-cols-max auto-rows-min gap-2 py-2 pl-10 pr-6 overflow-y-auto",
        )[
            [
                figure(
                    data.on(
                        "click",
                        f'$items = $items.at(-1)?.name === el.dataset.productName ? [...$items.slice(0, -1), {{...$items.at(-1), count: $items.at(-1).count + 1}}] : [...$items, {{"productId": {product.product_id}, "name": el.dataset.productName, "count": 1, "price": {product.price}}}]',
                    ),
                    data_product_name=product.name,
                    class_="flex flex-col border-4 border-gray-200 rounded-md transition-colors ease-in-out active:bg-gray-100",
                )[
                    img(
                        class_="mx-auto w-full h-auto aspect-square",
                        src=str(req.url_for("static", path=product.filename)),
                        alt=product.name,
                    ),
                    figcaption(class_="text-center truncate")[product.name],
                    div(class_="text-center")[product.price_str()],
                ]
                for product in products
            ]
        ],
        aside(class_="w-1/2 lg:w-2/6 h-full flex flex-col p-4 justify-between")[
            div(class_="flex flex-row py-2 justify-around items-center text-xl")[
                a(
                    href="/",
                    class_="cursor-pointer px-2 py-1 rounded-sm bg-gray-300 hidden lg:inline-block",
                )["ホーム"],
                button(
                    data.on("click", "$items = []"),
                    data.attr(disabled="$items.length === 0"),
                    class_="hidden sm:inline-block text-white px-2 py-1 rounded-sm bg-red-600 disabled:cursor-not-allowed disabled:text-gray-700 disabled:bg-gray-100",
                    tabindex="0",
                )["全消去"],
                div(class_="hidden md:inline-block")[clock],
            ],
            items(),
        ],
    ]
    return page_layout(req, inner, "新規注文 - murchace")


def items() -> Element:
    return div(id="items", class_="min-h-0 pt-2 flex flex-col")[
        # `flex-col-reverse` lets the browser to pin scroll to bottom
        div(class_="flex flex-col-reverse overflow-y-auto")[
            register_items(
                data.attr(items="$items"),
                data.on(
                    "delete-item", "$items = [...$items.toSpliced(evt.detail.index, 1)]"
                ),
            ),
        ],
        div(class_="flex flex-row p-2 items-center")[
            div(class_="basis-1/4 text-right lg:text-2xl")[
                span(data.text("$totalCount")), span[" 点"]
            ],
            div(class_="basis-2/4 text-center lg:text-2xl")[
                span["合計: "], span(data.text("$totalPriceStr"))
            ],
            button(
                data.on("click", "@get('/register/confirm-modal')"),
                data.attr(disabled="$items.length === 0"),
                class_="basis-1/4 lg:text-xl text-center text-white p-2 rounded-sm bg-blue-600 disabled:cursor-not-allowed disabled:text-gray-700 disabled:bg-gray-100",
            )["確定"],
            div(id="order-modal-container"),
        ],
    ]


def confirm_modal(items: list[dict[str, int | str]]) -> Element:
    return div(id="order-modal-container")[
        div(
            id="order-modal",
            class_="z-10 fixed inset-0 w-dvw h-dvh py-4 flex items-center bg-gray-500/75",
            role="dialog",
            aria_modal="true",
            onclick="this.remove()",
        )[
            div(
                id="order-confirm-modal",
                class_="mx-auto w-5/6 md:w-2/3 xl:w-1/3 h-4/5 p-4 flex flex-col gap-y-2 rounded-lg bg-white relative animate-[scale-50_150ms_ease-in]",
                onclick="event.stopPropagation()",
            )[
                button(
                    class_="absolute top-0 right-0 px-4 py-3 text-3xl font-bold bg-transparent rounded-tr-lg",
                    onclick="window['order-modal'].remove()",
                )["✕"],
                article(
                    class_="grow min-h-0 flex flex-col gap-y-2 px-3 text-center text-lg"
                )[h2(class_="font-semibold")["注文の確定"], _total(items)],
                button(
                    data.on("click", "@post('/register')"),
                    class_="w-full py-4 text-center text-xl font-semibold text-white bg-blue-600 rounded-sm",
                )["確認"],
            ]
        ]
    ]


def issued_modal(order_id: int, items: list[dict[str, int | str]]) -> Element:
    return div(id="order-modal-container")[
        div(
            id="order-modal",
            class_="z-10 fixed inset-0 w-dvw h-dvh py-4 flex items-center bg-gray-500/75",
            role="dialog",
            aria_modal="true",
        )[
            div(
                class_="mx-auto w-5/6 md:w-2/3 xl:w-1/3 h-4/5 p-4 flex flex-col gap-y-2 rounded-lg bg-white animate-[scale-95_150ms_ease-in]"
            )[
                article(
                    class_="grow min-h-0 flex flex-col gap-y-2 px-3 text-center text-lg"
                )[h2(class_="font-semibold")[f"注文番号 #{order_id}"], _total(items)],
                button(
                    data.on("click", "window['order-modal'].remove()"),
                    class_="w-full py-4 text-center text-xl font-semibold text-white bg-green-600 rounded-sm",
                )["新規"],
                a(
                    href="/",
                    class_="w-full py-4 text-center text-xl font-semibold bg-white border border-gray-300 rounded-sm",
                )["ホームに戻る"],
            ]
        ]
    ]


def _total(items: list[dict[str, int | str]]) -> list[Element]:
    total_count = sum((item["count"] for item in items), 0)
    total_price = sum((item["price"] for item in items), 0)
    assert isinstance(total_price, int)

    return [
        ul(class_="grow flex flex-col overflow-y-auto")[
            [
                li(class_="flex flex-row items-start gap-x-2")[
                    span(class_="break-words")[item["name"]],
                    span(class_="ml-auto whitespace-nowrap")[
                        f"{Product.to_price_str(item['price'])} x {item['count']}"  # ty: ignore[invalid-argument-type]
                    ],
                ]
                for item in items
            ]
        ],
        div[
            p(class_="flex flex-row")[
                span["計"],
                span(class_="ml-auto whitespace-nowrap")[f"{total_count} 点"],
            ],
            p(class_="flex flex-row")[
                span(class_="break-words")["合計金額"],
                span(class_="ml-auto")[Product.to_price_str(total_price)],
            ],
        ],
    ]


def error_modal(message: str) -> Element:
    return div(id="order-modal-container")[
        div(
            id="order-modal",
            class_="z-10 fixed inset-0 w-dvw h-dvh py-4 flex items-center bg-gray-500/75",
            role="dialog",
            aria_modal="true",
        )[
            div(
                id="order-error-modal",
                class_="mx-auto w-5/6 md:w-2/3 xl:w-1/3 h-4/5 p-4 flex flex-col gap-y-2 rounded-lg bg-white [.datastar-settling_&]:scale-50 transition-transform duration-150",
            )[
                article(
                    class_="grow min-h-0 flex flex-col gap-y-2 px-3 text-center text-lg"
                )[h2(class_="font-semibold text-red-500")["エラー"], p[message]],
                button(
                    data.on("click", "$items = []; window.location.reload()"),
                    class_="w-full py-4 text-center text-xl font-semibold bg-white border border-gray-300 rounded-sm",
                )["リロードする"],
            ]
        ]
    ]


@router.get("/register", response_class=HTMLResponse)
async def get_register(
    request: Request,
    c: Annotated[list[int] | None, Query()] = None,  # category
):
    products = await (
        ProductTable.by_category_ids(c) if c is not None else ProductTable.select_all()
    )
    return HTMLResponse(page_register(request, products))


def parse_items(signals: dict[str, Any] | None) -> list | str:
    if signals is None:
        return "シグナルが見つかりません"
    if (items := signals.get("items")) is None:
        return "items属性が見つかりません"
    if not isinstance(items, list):
        return "itemsがlistではありません"
    if len(items) == 0:
        return "商品が選択されていません"
    return items


@router.get("/register/confirm-modal")
async def get_confirm_dialog(request: Request):
    if isinstance(items := parse_items(await read_signals(request)), str):
        return DatastarResponse(SSE.patch_elements(error_modal(items)))
    return DatastarResponse(SSE.patch_elements(confirm_modal(items)))


@router.post("/register")
async def place_order(request: Request, queue: PrinterQueueDeps):
    if isinstance(items := parse_items(await read_signals(request)), str):
        return DatastarResponse(SSE.patch_elements(error_modal(items)))

    # We modify order tables all in one transaction. If `POST /register` happens
    # fast enough then the first mutating query (database.fetch_val in this
    # case) will throw sqlite3.OperationalError with "database is locked"
    # message. This rarely happens in practice but even if it does a user just
    # receives no feedback and so they can issue another database transaction.
    # TODO: We should give users a small feedback about database lock in some
    # way.
    async with database.transaction():
        # We reject order issuance when product name and price do not match up
        product_map = {p.product_id: p for p in await ProductTable.select_all()}
        product_ids: list[int] = []
        for item in items:
            product = product_map[item["productId"]]
            if product.name != item["name"]:
                err_msg = f"商品名が異なります: {product.name} != {item['name']}"
                return DatastarResponse(SSE.patch_elements(error_modal(err_msg)))
            if product.price != item["price"]:
                err_msg = f"値段が異なります: {product.price} != {item['price']}"
                return DatastarResponse(SSE.patch_elements(error_modal(err_msg)))
            for _ in range(item["count"]):
                product_ids.append(item["productId"])

        max_order_id_p1 = sa_exp.select(
            sa_func.coalesce(sa_func.max(Order.order_id), 0) + 1
        ).scalar_subquery()
        order_row = await database.fetch_one(
            sa_exp.insert(Order)
            .values(order_id=max_order_id_p1)
            .returning(Order.order_id, Order.ordered_at)
        )
        assert order_row is not None, "INSERT ... RETURNING returned no row"
        order_id, ordered_at = order_row["order_id"], order_row["ordered_at"]

        await database.execute_many(
            sa_exp.insert(OrderedItem).values(order_id=order_id),
            [{"item_no": i, "product_id": pid} for i, pid in enumerate(product_ids)],
        )

        OrderTable.modified_flag_bc.send(ModifiedFlag.INCOMING)

    # Enqueue receipt for printing
    queue.enqueue(build_receipt_data(order_id, items, ordered_at=ordered_at))

    return DatastarResponse(
        [
            SSE.patch_signals({"items": []}),
            SSE.patch_elements(issued_modal(order_id, items)),
        ]
    )
