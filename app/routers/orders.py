import asyncio
from collections.abc import AsyncIterable, Awaitable, Callable, Mapping
from datetime import datetime
from functools import partial
from typing import Any, Literal

import sqlalchemy
import sqlalchemy.sql.expression as sa_exp
from datastar_py import attribute_generator as data
from datastar_py.fastapi import DatastarResponse
from datastar_py.sse import DatastarEvent
from datastar_py.sse import ServerSentEventGenerator as SSE
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from htpy import (
    Element,
    HTMLElement,
    a,
    button,
    div,
    h3,
    header,
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
from ..store import (
    Order,
    OrderedItem,
    OrderTable,
    Product,
    database,
    supply_all_and_complete,
    supply_and_complete_order_if_done,
    unixepoch,
)
from ..store.order import ModifiedFlag

router = APIRouter()


def link_normal(href: str, text: str) -> Element:
    return a(href=href, class_="cursor-pointer px-2 py-1 rounded-sm bg-gray-300")[text]


def link_selected(href: str, text: str) -> Element:
    return a(
        href=href, class_="cursor-pointer px-2 py-1 rounded-sm bg-gray-900 text-white"
    )[text]


def notif_ringtone(req: Request) -> list[Element]:
    return [
        Element("notif-ringtone")(
            data.signals({"_notifRingtone": False}),
            data.attr({"notification": "$_notifRingtone"}),
            data.on("playing", "$_notifRingtone = false"),
            src=str(req.url_for("static", path="notification-1.mp3")),
        ),
        script[
            Markup(
                """
            class NotifRingtone extends HTMLElement {
              constructor() {
                super()
                this.audio = new Audio()
              }
              static get observedAttributes() {
                  return ["notification", "src"]
              }
              attributeChangedCallback(name, oldValue, newValue) {
                if (name === "notification" && newValue) {
                  this.audio.muted = false
                  this.audio.play()
                  this.dispatchEvent(new CustomEvent('playing'))
                } else if (name === 'src') {
                  this.audio.src = newValue
                  this.audio.load()
                  this.audio.muted = true
                  // Load audio in the background on a screen touch to
                  // circumvent the autoplay policy on iOS.
                  // Details: https://stackoverflow.com/a/10448078
                  document.addEventListener('touchstart', () => this.audio.play(), {once: true})
                }
              }
            }
            customElements.define("notif-ringtone", NotifRingtone)
            """
            )
        ],
    ]


def _to_time(unix_epoch: int) -> str:
    return datetime.fromtimestamp(unix_epoch).strftime("%H:%M:%S")  # noqa: DTZ006


# This function exists to reduce code duplication, at the cost of terrible
# organization of control flows.
#
# It abstracts out the 2-dimenstional row-by-row extraction loop. But in doing
# so, the caller must ensure that the outer loop variables and callbacks
# intertwines oh-so perfectly in a very subtle way. This leads to the
# `asyncio.Lock` workarounds for avoiding race conditions between tasks. I
# sincerely regret that I made this abomination in the first place.
#
# If anything, I think the loop should be handled on the caller side rather
# than managing the loop deep in the call stack. Also, it would be nice to be
# able to cache the constructed object so that only one connection needs to
# construct the object and let the others waiting for it.
async def _agen_query_executor[T](
    query: str,
    unique_key: Literal["order_id", "product_id"],
    init_cb: Callable[[Any, Mapping], None],
    elem_cb: Callable[[Mapping], T],
    list_cb: Callable[[list[T]], None],
):
    prev_unique_id = -1
    lst: list[T] = []
    async for map in database.iterate(query):
        if (unique_id := map[unique_key]) != prev_unique_id:
            if prev_unique_id != -1:
                list_cb(lst)
            prev_unique_id = unique_id
            init_cb(unique_id, map)
            lst: list[T] = []
        lst.append(elem_cb(map))
    if prev_unique_id != -1:
        list_cb(lst)


query_ordered_items_incoming: sa_exp.Select = (
    sa_exp.select(OrderedItem.order_id, OrderedItem.product_id)
    .add_columns(sa_func.count(OrderedItem.product_id).label("count"))
    .where(OrderedItem.supplied_at.is_(None))  # Filter out supplied items
    .group_by(OrderedItem.order_id, OrderedItem.product_id)
    .select_from(sa_exp.join(OrderedItem, Product))
    .add_columns(Product.name, Product.filename)
    .join(Order)
    .add_columns(unixepoch(Order.ordered_at))
    .where(Order.canceled_at.is_(None) & Order.completed_at.is_(None))
    .order_by(OrderedItem.product_id.asc(), OrderedItem.order_id.asc())
)

type ordered_item_t = dict[str, int | str | list[dict[str, int | str]]]  # noqa: PYI042


def _ordered_items_loader() -> Callable[[], Awaitable[list[ordered_item_t]]]:
    query_str = str(query_ordered_items_incoming.compile())

    ordered_items: list[ordered_item_t] = []

    def init_cb(product_id: int, map: Mapping):
        ordered_items.append(
            {"product_id": product_id, "name": map["name"], "filename": map["filename"]}
        )

    def elem_cb(map: Mapping) -> dict[str, int | str]:
        return {
            "order_id": map["order_id"],
            "count": map["count"],
            "ordered_at": _to_time(map["ordered_at"]),
        }

    def list_cb(orders: list[dict[str, int | str]]):
        ordered_items[-1]["orders"] = orders

    load_ordered_products = partial(
        _agen_query_executor, query_str, "product_id", init_cb, elem_cb, list_cb
    )

    # Hack around the situation where multiple threads potentially modifying
    # the `ordered_items` list simultaneously. See `_agen_query_executor` for
    # more information.
    lock = asyncio.Lock()

    async def load():
        async with lock:
            ordered_items.clear()
            await load_ordered_products()
            return ordered_items

    return load


load_ordered_items_incoming = _ordered_items_loader()


elm_main_ordered_items = main(
    id="ordered-items",
    class_="w-full grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 auto-rows-min gap-3 py-2 px-16 overflow-y-auto",
)


def page_ordered_items_incoming(req: Request) -> HTMLElement:
    inner = div(
        data.init("@get('/ordered-items/incoming-stream')"), class_="flex flex-col"
    )[
        header(
            class_="sticky z-10 inset-0 w-full px-16 py-3 flex gap-3 border-b border-gray-500 bg-white text-2xl"
        )[
            ul(class_="grow hidden md:flex md:flex-row gap-x-3")[
                li(class_="grow")[link_normal("/", "ホーム")],
                li[link_normal("/orders/incoming", "未受取：注文")],
                li[link_selected("/ordered-items/incoming", "未受取：商品")],
                li[link_normal("/orders/resolved", "処理済")],
            ],
            clock,
        ],
        elm_main_ordered_items,
        notif_ringtone(req),
    ]
    return page_layout(req, inner, title="未受取商品 - murchace")


def ordered_items_incoming_component(
    req: Request, ordered_items: list[ordered_item_t]
) -> Element:
    def orders(ordered_item: ordered_item_t) -> list[Element]:
        return [
            li(
                id=f"ordered-item-{order['order_id']}-{ordered_item['product_id']}",  # ty: ignore[invalid-argument-type]
                class_="flex flex-row items-center",
            )[
                span(class_="text-xl")[f"#{order['order_id']}"],  # ty: ignore[invalid-argument-type]
                span(class_="ml-1")[f"@{order['ordered_at']}"],  # ty: ignore[invalid-argument-type]
                span(class_="whitespace-nowrap ml-auto")[f"x {order['count']}"],  # ty: ignore[invalid-argument-type]
                button(
                    data.on(
                        "click",
                        f"@post('/orders/{order['order_id']}/products/{ordered_item['product_id']}/supplied-at')",  # ty: ignore[invalid-argument-type]
                    ),
                    class_="w-1/3 py-1 m-1 text-white bg-green-600 rounded-sm",
                )["✓"],
            ]
            for order in ordered_item["orders"]  # ty: ignore[not-iterable]
        ]

    return elm_main_ordered_items[
        [
            div(
                id=f"product-{ordered_item['product_id']}",
                class_="h-80 flex flex-col border-2 border-gray-300 rounded-lg pb-2",
            )[
                div(class_="width-full flex flex-row mx-1 items-start pb-2")[
                    h3(class_="text-lg ml-1")[ordered_item["name"]]
                ],
                div(class_="w-1/3 mx-auto")[
                    img(
                        src=str(req.url_for("static", path=ordered_item["filename"])),
                        alt=str(ordered_item["name"]),
                        class_="mx-auto w-full h-auto aspect-square",
                    )
                ],
                ul(class_="grow overflow-y-auto px-2 divide-y-2 divide-gray-200")[
                    *orders(ordered_item)
                ],
            ]
            for ordered_item in ordered_items
        ]
    ]


type item_t = dict[str, int | str | None]  # noqa: PYI042
type order_t = dict[str, int | list[item_t] | str | datetime | None]  # noqa: PYI042


query_incoming: sa_exp.Select = (
    # Query from the orders table
    sa_exp.select(Order.order_id)
    .group_by(Order.order_id)
    .order_by(Order.order_id.asc())
    .add_columns(unixepoch(Order.ordered_at))
    # Filter out canceled/completed orders
    .where(Order.canceled_at.is_(None) & Order.completed_at.is_(None))
    # Query the list of ordered items
    .select_from(sa_exp.join(Order, OrderedItem))
    .add_columns(OrderedItem.product_id, unixepoch(OrderedItem.supplied_at))
    .group_by(OrderedItem.product_id)
    .order_by(OrderedItem.product_id.asc())
    .add_columns(sa_func.count(OrderedItem.product_id).label("count"))
    # Query product name
    .join(Product)
    .add_columns(Product.name)
)


query_resolved: sa_exp.Select = (
    # Query from the orders table
    sa_exp.select(Order.order_id)
    .group_by(Order.order_id)
    .order_by(Order.order_id.asc())
    .add_columns(unixepoch(Order.ordered_at))
    # Query canceled/completed orders
    .where(Order.canceled_at.isnot(None) | Order.completed_at.isnot(None))
    .add_columns(unixepoch(Order.canceled_at))
    .add_columns(unixepoch(Order.completed_at))
    # Query the list of ordered items
    .select_from(sa_exp.join(Order, OrderedItem))
    .add_columns(OrderedItem.product_id, unixepoch(OrderedItem.supplied_at))
    .group_by(OrderedItem.product_id)
    .order_by(OrderedItem.product_id.asc())
    .add_columns(sa_func.count(OrderedItem.product_id).label("count"))
    # Query product name and price
    .join(Product)
    .add_columns(Product.name, Product.price)
)


def callbacks_orders_incoming(
    orders: list[order_t],
) -> tuple[
    Callable[[int, Mapping], None],
    Callable[[Mapping], item_t],
    Callable[[list[item_t]], None],
]:
    def init_cb(order_id: int, map: Mapping) -> None:
        orders.append({"order_id": order_id, "ordered_at": _to_time(map["ordered_at"])})

    def elem_cb(map: Mapping) -> item_t:
        supplied_at = map["supplied_at"]
        return {
            "product_id": map["product_id"],
            "count": map["count"],
            "name": map["name"],
            "supplied_at": _to_time(supplied_at) if supplied_at else None,
        }

    def list_cb(items: list[item_t]) -> None:
        orders[-1]["items"] = items

    return init_cb, elem_cb, list_cb


def callbacks_orders_resolved(
    orders: list[order_t],
) -> tuple[
    Callable[[int, Mapping], None],
    Callable[[Mapping], item_t],
    Callable[[list[item_t]], None],
]:
    total_price = 0

    def init_cb(order_id: int, map: Mapping) -> None:
        canceled_at, completed_at = map["canceled_at"], map["completed_at"]
        orders.append(
            {
                "order_id": order_id,
                "ordered_at": _to_time(map["ordered_at"]),
                "canceled_at": _to_time(canceled_at) if canceled_at else None,
                "completed_at": _to_time(completed_at) if completed_at else None,
            }
        )
        nonlocal total_price
        total_price = 0

    def elem_cb(map: Mapping) -> item_t:
        count, price = map["count"], map["price"]
        nonlocal total_price
        total_price += count * price
        supplied_at = map["supplied_at"]
        return {
            "product_id": map["product_id"],
            "count": count,
            "name": map["name"],
            "price": Product.to_price_str(price),
            "supplied_at": _to_time(supplied_at) if supplied_at else None,
        }

    def list_cb(items: list[item_t]) -> None:
        orders[-1]["items"] = items
        orders[-1]["total_price"] = Product.to_price_str(total_price)

    return init_cb, elem_cb, list_cb


def _orders_loader(
    query: sqlalchemy.Compiled,
    callbacks: Callable[
        [list[order_t]],
        tuple[
            Callable[[int, Mapping], None],
            Callable[[Mapping], item_t],
            Callable[[list[item_t]], None],
        ],
    ],
) -> Callable[[], Awaitable[list[order_t]]]:
    orders: list[order_t] = []

    init_cb, elem_cb, list_cb = callbacks(orders)
    load_orders = partial(
        _agen_query_executor, str(query), "order_id", init_cb, elem_cb, list_cb
    )

    # Hack around the situation where multiple threads potentially modifying
    # the `orders` list simultaneously. See `_agen_query_executor` for more
    # information.
    lock = asyncio.Lock()

    async def load():
        async with lock:
            orders.clear()
            await load_orders()
            return orders

    return load


load_incoming_orders = _orders_loader(
    query_incoming.compile(), callbacks_orders_incoming
)
load_resolved_orders = _orders_loader(
    query_resolved.compile(), callbacks_orders_resolved
)


async def load_one_resolved_order(order_id: int) -> order_t | None:
    query = query_resolved.where(Order.order_id == order_id)

    rows_agen = database.iterate(query)
    if (row := await anext(rows_agen, None)) is None:
        return None

    canceled_at, completed_at = row["canceled_at"], row["completed_at"]
    order: order_t = {
        "order_id": order_id,
        "ordered_at": _to_time(row["ordered_at"]),
        "canceled_at": _to_time(canceled_at) if canceled_at else None,
        "completed_at": _to_time(completed_at) if completed_at else None,
    }

    total_price = 0

    def to_item(row: Mapping) -> item_t:
        count, price = row["count"], row["price"]
        nonlocal total_price
        total_price += count * price
        supplied_at = row["supplied_at"]
        return {
            "product_id": row["product_id"],
            "count": count,
            "name": row["name"],
            "price": Product.to_price_str(price),
            "supplied_at": _to_time(supplied_at) if supplied_at else None,
        }

    items = [to_item(row)]
    async for row in rows_agen:
        items.append(to_item(row))
    order["items"] = items
    order["total_price"] = Product.to_price_str(total_price)

    return order


elm_main_incoming_orders = main(
    id="orders",
    class_="w-full grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 auto-rows-min gap-3 py-2 px-16 overflow-y-auto",
)


def page_incoming_orders(req: Request) -> HTMLElement:
    inner = div(data.init("@get('/orders/incoming-stream')"), class_="flex flex-col")[
        header(
            class_="sticky z-10 inset-0 w-full px-16 py-3 flex gap-3 border-b border-gray-500 bg-white text-2xl"
        )[
            ul(class_="grow hidden md:flex md:flex-row gap-x-3")[
                li(class_="grow")[link_normal("/", "ホーム")],
                li[link_selected("/orders/incoming", "未受取：注文")],
                li[link_normal("/ordered-items/incoming", "未受取：商品")],
                li[link_normal("/orders/resolved", "処理済")],
            ],
            clock,
        ],
        elm_main_incoming_orders,
        notif_ringtone(req),
    ]
    return page_layout(req, inner, title="未受取注文 - murchace")


def incoming_orders_component(orders: list[order_t]) -> Element:
    def ordered_items(order: order_t) -> list[Element]:
        return [
            li(class_="flex flex-row items-start gap-x-2 px-1")[
                (
                    span(class_="text-green-500 font-bold")["✓"]
                    if item["supplied_at"]  # ty: ignore[invalid-argument-type]
                    else span(class_="text-red-500 font-bold")["✗"]
                ),
                span(class_="break-words")[item["name"]],  # ty: ignore[invalid-argument-type]
                span(class_="ml-auto whitespace-nowrap")[f"x {item['count']}"],  # ty: ignore[invalid-argument-type]
            ]
            for item in order["items"]  # ty: ignore[not-iterable]
        ]

    return elm_main_incoming_orders[
        [
            div(
                id=f"order-{order['order_id']}",
                class_="w-full h-60 flex flex-col gap-y-1 border-2 border-gray-300 rounded-lg pb-2",
            )[
                div(class_="width-full flex flex-row p-2 items-start")[
                    div(class_="grow flex flex-row items-end")[
                        h3(class_="text-2xl")[f"#{order['order_id']}"],
                        span(class_="ml-1")[f"@{order['ordered_at']}"],
                    ],
                    button(
                        data.on(
                            "click",
                            f"confirm('確定注文 #{order['order_id']} を取り消しますか？') && @post('/orders/{order['order_id']}/canceled-at')",
                        ),
                        class_="px-2 py-1 text-white bg-red-600 rounded-lg",
                    )["取消"],
                ],
                ul(class_="grow overflow-y-auto px-2 divide-y-2 divide-gray-200")[
                    ordered_items(order)
                ],
                button(
                    data.on(
                        "click",
                        f"@post('/orders/{order['order_id']}/completed-at')",
                    ),
                    class_="mx-10 py-1 text-white bg-blue-600 rounded-lg",
                )["完了"],
            ]
            for order in orders
        ]
    ]


def page_resolved_orders(req: Request, orders: list[order_t]) -> HTMLElement:
    inner = div(class_="flex flex-col")[
        header(
            class_="sticky z-10 inset-0 w-full px-16 py-3 flex gap-3 border-b border-gray-500 bg-white text-2xl"
        )[
            ul(class_="grow hidden md:flex md:flex-row gap-x-3")[
                li(class_="grow")[link_normal("/", "ホーム")],
                li[link_normal("/orders/incoming", "未受取：注文")],
                li[link_normal("/ordered-items/incoming", "未受取：商品")],
                li[link_selected("/orders/resolved", "処理済")],
            ],
            clock,
        ],
        main(
            id="orders",
            class_="w-full grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 auto-rows-min gap-3 py-2 px-16 overflow-y-auto",
        )[
            [
                resolved_order_completed(order)
                if order["completed_at"]
                else resolved_order_canceled(order)
                for order in reversed(orders)
            ]
        ],
    ]
    return page_layout(req, inner, title="処理済注文 - murchace")


def resolved_order_completed(order: order_t) -> Element:
    return div(
        id=f"order-{order['order_id']}",
        class_="w-full h-64 flex flex-col gap-y-1 border-2 border-gray-300 rounded-lg pb-2",
    )[
        div(class_="width-full flex flex-row items-start p-2 bg-cyan-100 rounded-t-lg")[
            div(class_="grow flex flex-row items-end")[
                h3(class_="text-2xl")[f"#{order['order_id']}"],
                span(class_="ml-1")[f"@{order['ordered_at']}-{order['completed_at']}"],
            ],
            button(
                data.on(
                    "click",
                    f"confirm('完了した注文 #{order['order_id']} を取り消しますか？') && @post('/orders/{order['order_id']}/canceled-at?card_response=1')",
                ),
                class_="px-2 py-1 text-white bg-red-600 rounded-lg",
            )["取消"],
        ],
        _order_body(order),
    ]


def resolved_order_canceled(order: order_t) -> Element:
    return div(
        id=f"order-{order['order_id']}",
        class_="w-full h-64 flex flex-col gap-y-1 border-2 border-gray-300 rounded-lg pb-2",
    )[
        div(
            class_="width-full flex flex-row items-start p-2 bg-orange-200 rounded-t-md"
        )[
            div(class_="grow flex flex-row items-end")[
                h3(class_="text-2xl line-through")[f"#{order['order_id']}"],
                span(class_="ml-1")[f"@{order['ordered_at']}-{order['canceled_at']}"],
            ],
            button(
                data.on(
                    "click",
                    f"$card_response=true; confirm('一度取り消した注文 #{order['order_id']} を完了しますか？') && @post('/orders/{order['order_id']}/completed-at?card_response=1')",
                ),
                class_="px-2 py-1 text-white bg-red-600 rounded-lg",
            )["完了"],
        ],
        _order_body(order),
    ]


def _order_body(order: order_t) -> list[Element]:
    return [
        ul(class_="grow overflow-y-auto px-2 divide-y-2 divide-gray-200")[
            [
                li(class_="flex flex-row items-start gap-x-2")[
                    span(class_="text-green-500 font-bold")["✓"]
                    if item["supplied_at"]  # ty: ignore[invalid-argument-type]
                    else span(class_="text-red-500 font-bold")["✗"],
                    span(class_="break-words")[item["name"]],  # ty: ignore[invalid-argument-type]
                    span(class_="ml-auto whitespace-nowrap")[
                        f"{item['price']} x {item['count']}"  # ty: ignore[invalid-argument-type]
                    ],
                ]
                for item in order["items"]  # ty: ignore[not-iterable]
            ]
        ],
        p(class_="flex flex-row mx-1 justify-between px-2")[
            span(class_="break-words")["合計金額"],
            span(class_="whitespace-nowrap")[order["total_price"]],  # ty: ignore[invalid-argument-type]
        ],
        button(
            data.on(
                "click",
                f"confirm('一度取り消した注文 #{order['order_id']} を受け取り待ちに戻しますか？') && @delete('/orders/{order['order_id']}/resolved-at')",
            ),
            class_="mx-10 py-1 border border-gray-600 rounded-lg",
        )["未受取に戻す"],
    ]


@router.get("/ordered-items/incoming", response_class=HTMLResponse)
async def get_incoming_ordered_items(request: Request):
    return HTMLResponse(page_ordered_items_incoming(request))


@router.get("/ordered-items/incoming-stream")
async def ordered_items_incoming_stream(request: Request):
    return DatastarResponse(_ordered_items_incoming_stream(request))


async def _ordered_items_incoming_stream(req: Request) -> AsyncIterable[DatastarEvent]:
    ordered_items = await load_ordered_items_incoming()
    yield SSE.patch_elements(ordered_items_incoming_component(req, ordered_items))
    async with OrderTable.modified_flag_bc.attach_receiver() as flag_rx:
        while True:
            flag = await flag_rx.recv()
            new_order = flag & (ModifiedFlag.INCOMING | ModifiedFlag.PUT_BACK)
            ordered_items = await load_ordered_items_incoming()
            yield SSE.patch_elements(
                ordered_items_incoming_component(req, ordered_items)
            )
            if new_order:
                yield SSE.patch_signals({"_notifRingtone": "true"})


@router.post("/orders/{order_id}/products/{product_id}/supplied-at")
async def supply_products(order_id: int, product_id: int):
    completed = await supply_and_complete_order_if_done(order_id, product_id)
    if completed:
        id = f"#ordered-{product_id}"
    else:
        id = f"#ordered-item-{order_id}-{product_id}"
    return DatastarResponse(SSE.remove_elements(id))


@router.get("/orders/incoming", response_class=HTMLResponse)
async def get_incoming_orders(request: Request):
    return HTMLResponse(page_incoming_orders(request))


@router.get("/orders/incoming-stream")
async def incoming_orders_stream():
    return DatastarResponse(_incoming_orders_stream())


async def _incoming_orders_stream() -> AsyncIterable[DatastarEvent]:
    orders = await load_incoming_orders()
    yield SSE.patch_elements(incoming_orders_component(orders))
    async with OrderTable.modified_flag_bc.attach_receiver() as flag_rx:
        while True:
            flag = await flag_rx.recv()
            new_order = flag & (ModifiedFlag.INCOMING | ModifiedFlag.PUT_BACK)
            orders = await load_incoming_orders()
            yield SSE.patch_elements(incoming_orders_component(orders))
            if new_order:
                yield SSE.patch_signals({"_notifRingtone": "true"})


@router.get("/orders/resolved", response_class=HTMLResponse)
async def get_resolved_orders(request: Request):
    orders = await load_resolved_orders()
    return HTMLResponse(page_resolved_orders(request, orders))


@router.delete("/orders/{order_id}/resolved-at")
async def reset(order_id: int):
    await OrderTable.reset(order_id)
    return DatastarResponse(SSE.remove_elements(f"#order-{order_id}"))


@router.post("/orders/{order_id}/completed-at")
async def complete(order_id: int, card_response: bool = False):
    if not card_response:
        await supply_all_and_complete(order_id)
        return DatastarResponse(SSE.remove_elements(f"#order-{order_id}"))

    async with database.transaction():
        await supply_all_and_complete(order_id)
        maybe_order = await load_one_resolved_order(order_id)

    if (order := maybe_order) is None:
        detail = f"Order {order_id} not found"
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

    order_card = resolved_order_completed(order)
    return DatastarResponse(SSE.patch_elements(order_card))


@router.post("/orders/{order_id}/canceled-at")
async def cancel(order_id: int, card_response: bool = False):
    if not card_response:
        await OrderTable.cancel(order_id)
        return

    async with database.transaction():
        await OrderTable.cancel(order_id)
        maybe_order = await load_one_resolved_order(order_id)

    if (order := maybe_order) is None:
        detail = f"Order {order_id} not found"
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

    order_card = resolved_order_canceled(order)
    return DatastarResponse(SSE.patch_elements(order_card))
