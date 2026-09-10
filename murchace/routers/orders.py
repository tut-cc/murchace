import asyncio
import json
from collections.abc import AsyncIterable, Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Flag, auto
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, Self

import sqlalchemy.sql.expression as sa_exp
from datastar_py import attribute_generator as data
from datastar_py.fastapi import DatastarResponse, read_signals
from datastar_py.sse import DatastarEvent
from datastar_py.sse import ServerSentEventGenerator as SSE
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from htpy import (
    Element,
    HTMLElement,
    a,
    article,
    button,
    div,
    fieldset,
    h2,
    h3,
    header,
    img,
    input,
    label,
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
    CategoryTable,
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


with open(Path(__file__).parent / "notif-ringtone.js", encoding="utf-8") as f:
    _notif_ringtone_script = script[Markup(f.read())]


def notif_ringtone(req: Request) -> list[Element]:
    return [
        Element("notif-ringtone")(
            data.signals({"_notifRingtone": False}),
            data.attr({"notification": "$_notifRingtone"}),
            data.on("playing", "$_notifRingtone = false"),
            src=str(req.url_for("static", path="notification-1.mp3")),
        ),
        _notif_ringtone_script,
    ]


def _to_time(unix_epoch: int | None) -> str | None:
    return (
        datetime.fromtimestamp(unix_epoch).strftime("%H:%M:%S") if unix_epoch else None  # noqa: DTZ006
    )


@dataclass
class OrderFilter:
    class StatusFlag(Flag):
        unprocessed = auto()
        canceled = auto()
        completed = auto()

        @classmethod
        def from_list(cls: type[Self], statuses: list[str]) -> Self:
            res = cls(0)
            for maybe_keyname in statuses:
                maybe_flag = getattr(cls, maybe_keyname, None)
                if isinstance(maybe_flag, cls):
                    res |= maybe_flag
            return res

        def column(self) -> sa_exp.ColumnElement[bool]:
            clause = sa_exp.literal(False)
            if self & self.unprocessed:
                clause |= Order.canceled_at.is_(None) & Order.completed_at.is_(None)
            if self & self.canceled:
                clause |= Order.canceled_at.is_not(None)
            if self & self.completed:
                clause |= Order.completed_at.is_not(None)
            return clause

    card: Literal["item", "order"]
    status_flag: StatusFlag
    all_category: bool
    category_ids: list[int]

    @classmethod
    def parse_from_signals(cls: type[Self], signals: dict[str, Any]) -> Self:
        category_ids = [int(c) for c in signals["filterCategories"] if c.isdigit()]
        return cls(
            card=signals["filterCard"],
            status_flag=cls.StatusFlag.from_list(signals["filterStatuses"]),
            all_category=signals["filterAllCategory"],
            category_ids=category_ids,
        )

    def by_category_ids(self) -> sa_exp.ColumnElement[bool]:
        return (
            sa_exp.literal(True)
            if self.all_category
            else Product.category_id.in_(self.category_ids)
        )


# TODO: use frozendict() when Python is updated to 3.15
default_filter_signals = MappingProxyType(
    {
        "filterCard": "item",  # or "order"
        "filterStatuses": ["unprocessed"],
        "filterAllCategory": True,
        "filterCategories": [],
    }
)
# JavaScript expressions for managing prefixed local variables
filter_signals_init_expr = ";".join(
    f"$_{k}={f'[...${k}]' if isinstance(v, list) else f'${k}'}"
    for k, v in default_filter_signals.items()
)
filter_signals_reset_expr = ";".join(
    f"${k}={json.dumps(v)};$_{k}={json.dumps(v)}"
    for k, v in default_filter_signals.items()
)
filter_signals_update_expr = ";".join(
    f"${k}={f'[...$_{k}]' if isinstance(v, list) else f'$_{k}'}"
    for k, v in default_filter_signals.items()
)

elm_order_filter_container = div(
    "#order-filter-container",
    data.signals(default_filter_signals).ifmissing,
    {"data-persist": ",".join(default_filter_signals.keys())},
)


@router.get("/order-filter", response_class=HTMLResponse)
async def get_order_filter():
    categories = await CategoryTable.select_all()

    radio = lambda text, *attrs, **kwargs: label(class_="flex items-center")[
        input(*attrs, type="radio", class_="peer size-5", **kwargs),
        span(class_="ml-2 peer-disabled:text-gray-300")[text],
    ]
    checkbox = lambda text, *attrs, **kwargs: label(class_="flex items-center")[
        input(*attrs, type="checkbox", class_="peer size-5", **kwargs),
        span(class_="ml-2 peer-disabled:text-gray-300")[text],
    ]

    order_filter_modal = div(
        data.init(filter_signals_init_expr),
        id="order-filter",
        class_="z-10 fixed inset-0 w-dvw h-dvh py-4 flex items-center bg-gray-500/75",
        role="dialog",
        aria_modal="true",
        onclick="this.remove()",
    )[
        div(
            id="order-filter-modal",
            class_="mx-auto w-5/6 md:w-2/3 xl:w-1/3 h-4/5 p-4 flex flex-col gap-y-2 rounded-lg bg-white relative animate-[scale-50_150ms_ease-in]",
            onclick="event.stopPropagation()",
        )[
            button(
                class_="absolute top-0 right-0 px-4 py-3 text-3xl font-bold bg-transparent rounded-tr-lg",
                onclick="window['order-filter'].remove()",
            )["✕"],
            article(class_="min-h-0 flex flex-col gap-y-2 px-3 text-center text-lg")[
                h2(class_="font-semibold")["フィルタ"],
                fieldset(
                    class_="grow min-h-0 grid grid-cols-1 md:grid-cols-4 gap-y-2 px-3 text-center text-lg"
                )[
                    div["カード"],
                    div(
                        class_="md:col-span-3 flex flex-col md:flex-row gap-x-4 md:ml-2"
                    )[
                        radio("商品", data.bind("_filterCard"), value="item"),
                        radio("注文", data.bind("_filterCard"), value="order"),
                    ],
                    div["状態"],
                    div(
                        class_="md:col-span-3 flex flex-col md:flex-row gap-x-4 md:ml-2"
                    )[
                        checkbox(
                            "未受取",
                            data.bind("_filterStatuses"),
                            value=OrderFilter.StatusFlag.unprocessed.name,
                        ),
                        checkbox(
                            "キャンセル",
                            data.bind("_filterStatuses"),
                            value=OrderFilter.StatusFlag.canceled.name,
                        ),
                        checkbox(
                            "完了",
                            data.bind("_filterStatuses"),
                            value=OrderFilter.StatusFlag.completed.name,
                        ),
                    ],
                    div["カテゴリ"],
                    div(class_="md:col-span-3 grow md:ml-2 overflow-y-auto")[
                        checkbox(
                            "すべて",
                            data.bind("_filterAllCategory"),
                            data.attr({"disabled": "$_filterCard == 'order'"}),
                            switch=True,
                        ),
                        div(class_="flex flex-col gap-2 py-2")[
                            (
                                checkbox(
                                    c.name,
                                    data.bind("_filterCategories"),
                                    data.attr(
                                        {
                                            "disabled": "$_filterAllCategory || $_filterCard == 'order'"
                                        }
                                    ),
                                    value=c.category_id,
                                )
                                for c in categories
                            )
                        ],
                    ],
                ],
            ],
            div(class_="grow"),
            button(
                data.on("click", filter_signals_reset_expr),
                class_="w-full py-2 text-center text-xl font-semibold text-white bg-blue-600 rounded-sm",
            )["デフォルトに戻す"],
            button(
                data.on(
                    "click",
                    f"{filter_signals_update_expr};window['order-filter'].remove();@get('/orders/stream')",
                ),
                class_="w-full py-4 text-center text-xl font-semibold text-white bg-blue-600 rounded-sm",
            )["変更"],
        ]
    ]
    return DatastarResponse(
        SSE.patch_elements(elm_order_filter_container[order_filter_modal])
    )


elm_main_units = main(
    id="units",
    class_="w-full grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 auto-rows-min gap-3 py-2 px-16 overflow-y-auto",
)


def page_orders(req: Request) -> HTMLElement:
    inner = div(
        # Delay until filter signals are initialized
        data.init("@get('/orders/stream')").delay("50ms"),
        class_="flex flex-col",
    )[
        header(
            class_="sticky z-10 inset-0 w-full px-16 py-3 flex items-center gap-3 border-b border-gray-500 bg-white text-2xl"
        )[
            a(href="/", class_="cursor-pointer px-2 py-1 rounded-sm bg-gray-300")[
                "ホーム"
            ],
            div(class_="grow"),
            button(
                data.on("click", "@get('/order-filter')"),
                class_="cursor-pointer px-2 py-1 rounded-sm bg-gray-300",
            )["フィルタ"],
            clock,
        ],
        elm_order_filter_container,
        elm_main_units,
        notif_ringtone(req),
    ]
    return page_layout(req, inner, title="注文一覧 - murchace")


@router.get("/orders", response_class=HTMLResponse)
async def get_orders(request: Request):
    return HTMLResponse(page_orders(request))


type ordered_item_t = dict[str, int | str | list[dict[str, int | str | None]]]  # noqa: PYI042


def item_stream_component(req: Request, ordered_items: list[ordered_item_t]) -> Element:
    def item_timestamp(order: dict[str, int | str]) -> str:
        return (
            f"@{order['ordered_at']}-{order['supplied_at']}"
            if order["supplied_at"]
            else f"@{order['ordered_at']}"
        )

    def orders(ordered_item: ordered_item_t) -> list[Element]:
        return [
            li(
                id=f"ordered-item-{order['order_id']}-{ordered_item['product_id']}",  # ty: ignore[invalid-argument-type]
                class_="flex flex-row items-center",
            )[
                span(class_="text-xl")[f"#{order['order_id']}"],  # ty: ignore[invalid-argument-type]
                span(class_="ml-1")[item_timestamp(order)],  # ty: ignore[invalid-argument-type]
                span(class_="whitespace-nowrap ml-auto")[f"x {order['count']}"],  # ty: ignore[invalid-argument-type]
                button(
                    data.on(
                        "click",
                        f"@post('/orders/{order['order_id']}/products/{ordered_item['product_id']}/supplied-at')",  # ty: ignore[invalid-argument-type]
                    ),
                    class_="w-1/3 py-1 m-1 text-white bg-green-600 rounded-sm",
                )["✓"]
                if order["supplied_at"] is None  # ty: ignore[invalid-argument-type]
                else None,
            ]
            for order in ordered_item["orders"]  # ty: ignore[not-iterable]
        ]

    return elm_main_units[
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


@router.get("/orders/stream")
async def get_orders_stream(request: Request):
    signals = await read_signals(request)
    assert signals is not None

    print("signals:", signals)
    # statuses = signals["filterStatuses"]
    # is_incoming = "unprocessed" in statuses and not (
    #     "canceled" in statuses or "completed" in statuses
    # )
    filter = OrderFilter.parse_from_signals(signals)
    if filter.card == "item":
        return DatastarResponse(item_unit_stream(request, filter))
    elif filter.card == "order":
        return DatastarResponse(order_unit_stream(filter))


def _items_loader() -> Callable[[sa_exp.Select], Awaitable[list[ordered_item_t]]]:
    ordered_items: list[ordered_item_t] = []

    def init_cb(product_id: int, map: Mapping):
        ordered_items.append(
            {"product_id": product_id, "name": map["name"], "filename": map["filename"]}
        )

    def elem_cb(map: Mapping) -> dict[str, int | str | None]:
        return {
            "order_id": map["order_id"],
            "count": map["count"],
            "ordered_at": _to_time(map["ordered_at"]),
            "supplied_at": _to_time(map["supplied_at"]),
        }

    def list_cb(orders: list[dict[str, int | str | None]]):
        ordered_items[-1]["orders"] = orders

    # Hack around the situation where multiple threads potentially modifying
    # the `ordered_items` list simultaneously.
    lock = asyncio.Lock()

    # NOTE:  With the current implementation, we must ensure the outer loop
    # variables and callbacks intertwine oh-so perfectly in a very subtle way.
    # I think the loop should be handled on the caller side rather than managing
    # the loop deep in the call stack. Also, it would be nice to be able to
    # cache the constructed object so that only one connection needs to
    # construct the `ordered_items` list and let the others wait for its
    # completion. Right now, we query the database and iterate rows for every
    # request.
    async def load(query: sa_exp.Select):
        async with lock:
            ordered_items.clear()

            prev_unique_id = -1
            lst: list[dict[str, int | str | None]] = []
            async for map in database.iterate(query):
                if (unique_id := map["product_id"]) != prev_unique_id:
                    if prev_unique_id != -1:
                        list_cb(lst)
                    prev_unique_id = unique_id
                    init_cb(unique_id, map)
                    lst: list[dict[str, int | str | None]] = []
                lst.append(elem_cb(map))
            if prev_unique_id != -1:
                list_cb(lst)

            return ordered_items

    return load


load_items = _items_loader()


def query_items(filter: OrderFilter) -> sa_exp.Select:
    return (
        sa_exp.select(OrderedItem.order_id, OrderedItem.product_id)
        .add_columns(sa_func.count(OrderedItem.product_id).label("count"))
        .where(
            OrderedItem.supplied_at.is_(None)
            if filter.status_flag == OrderFilter.StatusFlag.unprocessed
            else sa_exp.literal(True)
        )
        .group_by(OrderedItem.order_id, OrderedItem.product_id)
        .select_from(sa_exp.join(OrderedItem, Product))
        .add_columns(Product.name, Product.filename)
        .join(Order)
        .add_columns(unixepoch(Order.ordered_at), unixepoch(OrderedItem.supplied_at))
        .where(filter.status_flag.column() & filter.by_category_ids())
        .order_by(
            OrderedItem.product_id.asc(),
            OrderedItem.order_id.asc()
            if filter.status_flag == OrderFilter.StatusFlag.unprocessed
            else OrderedItem.order_id.desc(),
        )
    )


async def item_unit_stream(
    req: Request, filter: OrderFilter
) -> AsyncIterable[DatastarEvent]:
    query = query_items(filter)

    ordered_items = await load_items(query)
    yield SSE.patch_elements(item_stream_component(req, ordered_items))
    async with OrderTable.modified_flag_bc.attach_receiver() as flag_rx:
        while True:
            flag = await flag_rx.recv()
            new_order = flag & (ModifiedFlag.INCOMING | ModifiedFlag.PUT_BACK)
            ordered_items = await load_items(query)
            yield SSE.patch_elements(item_stream_component(req, ordered_items))
            if new_order:
                yield SSE.patch_signals({"_notifRingtone": "true"})


type item_t = dict[str, int | str | None]  # noqa: PYI042
type order_t = dict[str, int | list[item_t] | str | datetime | None]  # noqa: PYI042


def order_stream_component(orders: list[order_t]) -> Element:
    def ordered_items(order: order_t) -> list[Element]:
        return [
            li(class_="flex flex-row items-start gap-x-2 px-1")[
                (
                    span(class_="text-green-500 font-bold")["✓"]
                    if item["supplied_at"]  # ty: ignore[invalid-argument-type]
                    else span(class_="text-red-500 font-bold")["✗"]
                ),
                span(class_="break-words")[item["name"]],  # ty: ignore[invalid-argument-type]
                span(class_="ml-auto whitespace-nowrap")[
                    f"{item['price']} x {item['count']}"  # ty: ignore[invalid-argument-type]
                ],
            ]
            for item in order["items"]  # ty: ignore[not-iterable]
        ]

    def order_timestamp(order: order_t) -> str:
        return (
            f"@{order['ordered_at']}-{order['completed_at']}"
            if order["completed_at"]
            else f"@{order['ordered_at']}-{order['canceled_at']}"
            if order["canceled_at"]
            else f"@{order['ordered_at']}"
        )

    return elm_main_units[
        [
            div(
                id=f"order-{order['order_id']}",
                class_="w-full h-60 flex flex-col gap-y-1 border-2 border-gray-300 rounded-lg pb-2",
            )[
                div(
                    class_=f"width-full flex flex-row items-start p-2 {'bg-cyan-100' if order['completed_at'] else 'bg-orange-200' if order['canceled_at'] else ''}"
                )[
                    div(class_="grow flex flex-row items-end")[
                        h3(
                            class_=f"text-2xl {'line-through' if order['canceled_at'] else ''}"
                        )[f"#{order['order_id']}"],
                        span(class_="ml-1")[order_timestamp(order)],
                    ],
                    button(
                        data.on(
                            "click",
                            f"confirm('完了した注文 #{order['order_id']} を取り消しますか？') && @post('/orders/{order['order_id']}/canceled-at')"
                            if order["completed_at"]
                            else f"confirm('一度取り消した注文 #{order['order_id']} を完了しますか？') && @post('/orders/{order['order_id']}/completed-at')"
                            if order["canceled_at"]
                            else f"confirm('注文 #{order['order_id']} を取り消しますか？') && @post('/orders/{order['order_id']}/canceled-at')",
                        ),
                        class_="px-2 py-1 text-white bg-red-600 rounded-lg",
                    )["完了" if order["canceled_at"] else "取消"],
                ],
                ul(class_="grow overflow-y-auto px-2 divide-y-2 divide-gray-200")[
                    ordered_items(order)
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
                )["未受取に戻す"]
                if order["completed_at"] or order["canceled_at"]
                else button(
                    data.on(
                        "click", f"@post('/orders/{order['order_id']}/completed-at')"
                    ),
                    class_="mx-10 py-1 text-white bg-blue-600 rounded-lg",
                )["完了"],
            ]
            for order in orders
        ]
    ]


def _orders_loader() -> Callable[[sa_exp.Select], Awaitable[list[order_t]]]:
    orders: list[order_t] = []
    total_price = 0

    def init_cb(order_id: int, map: Mapping) -> None:
        orders.append(
            {
                "order_id": order_id,
                "ordered_at": _to_time(map["ordered_at"]),
                "canceled_at": _to_time(map["canceled_at"]),
                "completed_at": _to_time(map["completed_at"]),
            }
        )
        nonlocal total_price
        total_price = 0

    def elem_cb(map: Mapping) -> item_t:
        count, price = map["count"], map["price"]
        nonlocal total_price
        total_price += count * price
        return {
            "product_id": map["product_id"],
            "count": count,
            "name": map["name"],
            "price": Product.to_price_str(price),
            "supplied_at": _to_time(map["supplied_at"]),
        }

    def list_cb(items: list[item_t]) -> None:
        orders[-1]["items"] = items
        orders[-1]["total_price"] = Product.to_price_str(total_price)

    # Hack around the situation where multiple threads potentially modifying
    # the `orders` list simultaneously.
    lock = asyncio.Lock()

    # NOTE: See note for load(query) closure in _items_loader()
    async def load(query: sa_exp.Select):
        async with lock:
            orders.clear()

            prev_unique_id = -1
            lst: list[item_t] = []
            async for map in database.iterate(query):
                if (unique_id := map["order_id"]) != prev_unique_id:
                    if prev_unique_id != -1:
                        list_cb(lst)
                    prev_unique_id = unique_id
                    init_cb(unique_id, map)
                    lst: list[item_t] = []
                lst.append(elem_cb(map))
            if prev_unique_id != -1:
                list_cb(lst)

            return orders

    return load


load_orders = _orders_loader()


def query_orders(filter: OrderFilter) -> sa_exp.Select:
    return (
        # Query from the orders table
        sa_exp.select(Order.order_id)
        .group_by(Order.order_id)
        .order_by(
            Order.order_id.asc()
            if filter.status_flag == OrderFilter.StatusFlag.unprocessed
            else Order.order_id.desc()
        )
        .add_columns(unixepoch(Order.ordered_at))
        .where(filter.status_flag.column())
        .add_columns(unixepoch(Order.canceled_at), unixepoch(Order.completed_at))
        # Query the list of ordered items
        .select_from(sa_exp.join(Order, OrderedItem))
        .add_columns(OrderedItem.product_id, unixepoch(OrderedItem.supplied_at))
        .group_by(OrderedItem.product_id)
        .order_by(OrderedItem.id.asc())
        .add_columns(sa_func.count(OrderedItem.product_id).label("count"))
        # Query product name and price
        .join(Product)
        .add_columns(Product.name, Product.price)
    )


async def order_unit_stream(filter: OrderFilter) -> AsyncIterable[DatastarEvent]:
    query = query_orders(filter)

    orders = await load_orders(query)
    yield SSE.patch_elements(order_stream_component(orders))
    async with OrderTable.modified_flag_bc.attach_receiver() as flag_rx:
        while True:
            flag = await flag_rx.recv()
            new_order = flag & (ModifiedFlag.INCOMING | ModifiedFlag.PUT_BACK)
            orders = await load_orders(query)
            yield SSE.patch_elements(order_stream_component(orders))
            if new_order:
                yield SSE.patch_signals({"_notifRingtone": "true"})


@router.post("/orders/{order_id}/products/{product_id}/supplied-at")
async def supply_products(order_id: int, product_id: int):
    completed = await supply_and_complete_order_if_done(order_id, product_id)
    if completed:
        id = f"#product-{product_id}"
    else:
        id = f"#ordered-item-{order_id}-{product_id}"
    return DatastarResponse(SSE.remove_elements(id))


@router.delete("/orders/{order_id}/resolved-at")
async def reset(order_id: int):
    await OrderTable.reset(order_id)
    return DatastarResponse(SSE.remove_elements(f"#order-{order_id}"))


@router.post("/orders/{order_id}/completed-at")
async def complete(order_id: int):
    await supply_all_and_complete(order_id)
    return DatastarResponse(SSE.remove_elements(f"#order-{order_id}"))


@router.post("/orders/{order_id}/canceled-at")
async def cancel(order_id: int):
    await OrderTable.cancel(order_id)
