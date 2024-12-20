import asyncio
from datetime import datetime
from functools import partial
from typing import Annotated, Any, AsyncGenerator, Awaitable, Callable, Literal, Mapping

import sqlalchemy
import sqlmodel
from fastapi import APIRouter, Form, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlmodel import col
from sse_starlette.sse import EventSourceResponse

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
from ..templates import macro_template

router = APIRouter()


def _to_time(unix_epoch: int) -> str:
    return datetime.fromtimestamp(unix_epoch).strftime("%H:%M:%S")


async def _agen_query_executor[T](
    query: str,
    unique_key: Literal["placement_id"] | Literal["product_id"],
    init_cb: Callable[[Any, Mapping], None],
    elem_cb: Callable[[Mapping], T],
    list_cb: Callable[[list[T]], None],
):
    prev_unique_id = -1
    lst: list[T] = list()
    async for map in database.iterate(query):
        if (unique_id := map[unique_key]) != prev_unique_id:
            if prev_unique_id != -1:
                list_cb(lst)
            prev_unique_id = unique_id
            init_cb(unique_id, map)
            lst: list[T] = list()
        lst.append(elem_cb(map))
    if prev_unique_id != -1:
        list_cb(lst)


query_ordered_items_incoming: sqlalchemy.Select = (
    sqlmodel.select(OrderedItem.placement_id, OrderedItem.product_id)
    .add_columns(sqlmodel.func.count(col(OrderedItem.product_id)).label("count"))
    .where(col(OrderedItem.supplied_at).is_(None))  # Filter out supplied items
    .group_by(col(OrderedItem.placement_id), col(OrderedItem.product_id))
    .select_from(sqlmodel.join(OrderedItem, Product))
    .add_columns(col(Product.name), col(Product.filename))
    .join(Order)
    .add_columns(unixepoch(col(Order.placed_at)))
    .where(col(Order.canceled_at).is_(None) & col(Order.completed_at).is_(None))
    .order_by(col(OrderedItem.product_id).asc(), col(OrderedItem.placement_id).asc())
)

type ordered_item_t = dict[str, int | str | list[dict[str, int | str]]]


def _ordered_items_loader() -> Callable[[], Awaitable[list[ordered_item_t]]]:
    query_str = str(query_ordered_items_incoming.compile())

    ordered_items: list[ordered_item_t] = []

    def init_cb(product_id: int, map: Mapping):
        ordered_items.append(
            {"product_id": product_id, "name": map["name"], "filename": map["filename"]}
        )

    def elem_cb(map: Mapping) -> dict[str, int | str]:
        return {
            "order_id": map["placement_id"],
            "count": map["count"],
            "ordered_at": _to_time(map["placed_at"]),
        }

    def list_cb(orders: list[dict[str, int | str]]):
        ordered_items[-1]["orders"] = orders

    load_ordered_products = partial(
        _agen_query_executor, query_str, "product_id", init_cb, elem_cb, list_cb
    )

    async def load():
        ordered_items.clear()
        await load_ordered_products()
        return ordered_items

    return load


load_ordered_items_incoming = _ordered_items_loader()


class ordered_items_incoming:  # namespace
    @macro_template("ordered-items-incoming.html")
    @staticmethod
    def page(ordered_items: list[ordered_item_t]): ...

    @macro_template("ordered-items-incoming.html", "component")
    @staticmethod
    def component(ordered_items: list[ordered_item_t]): ...

    @macro_template("ordered-items-incoming.html", "component_with_sound")
    @staticmethod
    def component_with_sound(ordered_items: list[ordered_item_t]): ...


type item_t = dict[str, int | str | None]
type order_t = dict[str, int | list[item_t] | str | datetime | None]


query_incoming: sqlalchemy.Select = (
    # Query from the orders table
    sqlmodel.select(Order.placement_id)
    .group_by(col(Order.placement_id))
    .order_by(col(Order.placement_id).asc())
    .add_columns(unixepoch(col(Order.placed_at)))
    # Filter out canceled/completed orders
    .where(col(Order.canceled_at).is_(None) & col(Order.completed_at).is_(None))
    # Query the list of ordered items
    .select_from(sqlmodel.join(Order, OrderedItem))
    .add_columns(col(OrderedItem.product_id), unixepoch(col(OrderedItem.supplied_at)))
    .group_by(col(OrderedItem.product_id))
    .order_by(col(OrderedItem.product_id).asc())
    .add_columns(sqlmodel.func.count(col(OrderedItem.product_id)).label("count"))
    # Query product name
    .join(Product)
    .add_columns(col(Product.name))
)


query_resolved: sqlalchemy.Select = (
    # Query from the orders table
    sqlmodel.select(Order.placement_id)
    .group_by(col(Order.placement_id))
    .order_by(col(Order.placement_id).asc())
    .add_columns(unixepoch(col(Order.placed_at)))
    # Query canceled/completed orders
    .where(col(Order.canceled_at).isnot(None) | col(Order.completed_at).isnot(None))
    .add_columns(unixepoch(col(Order.canceled_at)))
    .add_columns(unixepoch(col(Order.completed_at)))
    # Query the list of ordered items
    .select_from(sqlmodel.join(Order, OrderedItem))
    .add_columns(col(OrderedItem.product_id), unixepoch(col(OrderedItem.supplied_at)))
    .group_by(col(OrderedItem.product_id))
    .order_by(col(OrderedItem.product_id).asc())
    .add_columns(sqlmodel.func.count(col(OrderedItem.product_id)).label("count"))
    # Query product name and price
    .join(Product)
    .add_columns(col(Product.name), col(Product.price))
)


def callbacks_orders_incoming(
    orders: list[order_t],
) -> tuple[
    Callable[[int, Mapping], None],
    Callable[[Mapping], item_t],
    Callable[[list[item_t]], None],
]:
    def init_cb(order_id: int, map: Mapping) -> None:
        orders.append({"order_id": order_id, "ordered_at": _to_time(map["placed_at"])})

    def elem_cb(map: Mapping) -> item_t:
        supplied_at = map["supplied_at"]
        return {
            "product_id": map["product_id"],
            "count": map["count"],
            "name": map["name"],
            "supplied_at": _to_time(supplied_at) if supplied_at else None,
        }

    def list_cb(items: list[item_t]) -> None:
        orders[-1]["items_"] = items

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
                "ordered_at": _to_time(map["placed_at"]),
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
        orders[-1]["items_"] = items
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
        _agen_query_executor, str(query), "placement_id", init_cb, elem_cb, list_cb
    )

    async def load():
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
    query = query_resolved.where(col(Order.placement_id) == order_id)

    rows_agen = database.iterate(query)
    if (row := await anext(rows_agen, None)) is None:
        return None

    canceled_at, completed_at = row["canceled_at"], row["completed_at"]
    order: order_t = {
        "order_id": order_id,
        "ordered_at": _to_time(row["placed_at"]),
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
    order["items_"] = items
    order["total_price"] = Product.to_price_str(total_price)

    return order


class incoming_orders:  # namespace
    @macro_template("incoming-orders.html")
    @staticmethod
    def page(orders: list[order_t]): ...

    @macro_template("incoming-orders.html", "component")
    @staticmethod
    def component(orders: list[order_t]): ...

    @macro_template("incoming-orders.html", "component_with_sound")
    @staticmethod
    def component_with_sound(orders: list[order_t]): ...


class resolved_orders:  # namespace
    @macro_template("resolved-orders.html")
    @staticmethod
    def page(orders: list[order_t]): ...

    @macro_template("resolved-orders.html", "completed")
    @staticmethod
    def completed(order: order_t): ...

    @macro_template("resolved-orders.html", "canceled")
    @staticmethod
    def canceled(order: order_t): ...


@router.get("/ordered-items/incoming", response_class=HTMLResponse)
async def get_incoming_ordered_items(request: Request):
    ordered_items = await load_ordered_items_incoming()
    return HTMLResponse(ordered_items_incoming.page(request, ordered_items))


@router.get("/ordered-items/incoming-stream", response_class=EventSourceResponse)
async def ordered_items_incoming_stream(
    request: Request, accept: Annotated[Literal["text/event-stream"], Header()]
):
    _ = accept
    return EventSourceResponse(_ordered_items_incoming_stream(request))


async def _ordered_items_incoming_stream(request: Request):
    ordered_items = await load_ordered_items_incoming()
    content = ordered_items_incoming.component(request, ordered_items)
    yield dict(data=content)
    try:
        while True:
            async with OrderTable.modified_cond_flag:
                flag = await OrderTable.modified_cond_flag.wait()
                if flag & (ModifiedFlag.INCOMING | ModifiedFlag.PUT_BACK):
                    template = ordered_items_incoming.component_with_sound
                else:
                    template = ordered_items_incoming.component
                ordered_items = await load_ordered_items_incoming()
                yield dict(data=template(request, ordered_items))
    except asyncio.CancelledError:
        yield dict(event="shutdown", data="")
    finally:
        yield dict(event="shutdown", data="")


@router.post("/orders/{order_id}/products/{product_id}/supplied-at")
async def supply_products(order_id: int, product_id: int):
    await supply_and_complete_order_if_done(order_id, product_id)


@router.get("/orders/incoming", response_class=HTMLResponse)
async def get_incoming_orders(request: Request):
    orders = await load_incoming_orders()
    return HTMLResponse(incoming_orders.page(request, orders))


@router.get("/orders/incoming-stream", response_class=EventSourceResponse)
async def incoming_orders_stream(
    request: Request, accept: Annotated[Literal["text/event-stream"], Header()]
):
    _ = accept
    return EventSourceResponse(_incoming_orders_stream(request))


async def _incoming_orders_stream(
    request: Request,
) -> AsyncGenerator[dict[str, str], None]:
    orders = await load_incoming_orders()
    content = incoming_orders.component(request, orders)
    yield dict(data=content)
    try:
        while True:
            async with OrderTable.modified_cond_flag:
                flag = await OrderTable.modified_cond_flag.wait()
                if flag & (ModifiedFlag.INCOMING | ModifiedFlag.PUT_BACK):
                    template = incoming_orders.component_with_sound
                else:
                    template = incoming_orders.component
                orders = await load_incoming_orders()
                yield dict(data=template(request, orders))
    except asyncio.CancelledError:
        yield dict(event="shutdown", data="")
    finally:
        yield dict(event="shutdown", data="")


@router.get("/orders/resolved", response_class=HTMLResponse)
async def get_resolved_orders(request: Request):
    orders = await load_resolved_orders()
    return HTMLResponse(resolved_orders.page(request, orders))


@router.delete("/orders/{order_id}/resolved-at")
async def reset(order_id: int):
    await OrderTable.reset(order_id)


@router.post("/orders/{order_id}/completed-at", response_class=HTMLResponse)
async def complete(
    request: Request, order_id: int, card_response: Annotated[bool, Form()] = False
):
    if not card_response:
        await supply_all_and_complete(order_id)
        return

    async with database.transaction():
        await supply_all_and_complete(order_id)
        maybe_order = await load_one_resolved_order(order_id)

    if (order := maybe_order) is None:
        detail = f"Order {order_id} not found"
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

    return HTMLResponse(resolved_orders.completed(request, order))


@router.post("/orders/{order_id}/canceled-at", response_class=HTMLResponse)
async def cancel(
    request: Request, order_id: int, card_response: Annotated[bool, Form()] = False
):
    if not card_response:
        await OrderTable.cancel(order_id)
        return

    async with database.transaction():
        await OrderTable.cancel(order_id)
        maybe_order = await load_one_resolved_order(order_id)

    if (order := maybe_order) is None:
        detail = f"Order {order_id} not found"
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

    return HTMLResponse(resolved_orders.canceled(request, order))
