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
    PlacedItem,
    Placement,
    PlacementTable,
    Product,
    database,
    supply_all_and_complete,
    supply_and_complete_placement_if_done,
    unixepoch,
)
from ..store.placement import ModifiedFlag
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


query_placed_items_incoming: sqlalchemy.Select = (
    sqlmodel.select(PlacedItem.placement_id, PlacedItem.product_id)
    .add_columns(sqlmodel.func.count(col(PlacedItem.product_id)).label("count"))
    .where(col(PlacedItem.supplied_at).is_(None))  # Filter out supplied items
    .group_by(col(PlacedItem.placement_id), col(PlacedItem.product_id))
    .select_from(sqlmodel.join(PlacedItem, Product))
    .add_columns(col(Product.name), col(Product.filename))
    .join(Placement)
    .add_columns(unixepoch(col(Placement.placed_at)))
    .where(col(Placement.canceled_at).is_(None) & col(Placement.completed_at).is_(None))
    .order_by(col(PlacedItem.product_id).asc(), col(PlacedItem.placement_id).asc())
)

type placed_item_t = dict[str, int | str | list[dict[str, int | str]]]


def _placed_items_loader() -> Callable[[], Awaitable[list[placed_item_t]]]:
    query_str = str(query_placed_items_incoming.compile())

    placed_items: list[placed_item_t] = []

    def init_cb(product_id: int, map: Mapping):
        placed_items.append(
            {"product_id": product_id, "name": map["name"], "filename": map["filename"]}
        )

    def elem_cb(map: Mapping) -> dict[str, int | str]:
        return {
            "placement_id": map["placement_id"],
            "count": map["count"],
            "placed_at": _to_time(map["placed_at"]),
        }

    def list_cb(placements: list[dict[str, int | str]]):
        placed_items[-1]["placements"] = placements

    load_placed_products = partial(
        _agen_query_executor, query_str, "product_id", init_cb, elem_cb, list_cb
    )

    async def load():
        placed_items.clear()
        await load_placed_products()
        return placed_items

    return load


load_placed_items_incoming = _placed_items_loader()


class ordered_items_incoming:  # namespace
    @macro_template("ordered-items-incoming.html")
    @staticmethod
    def page(placed_items: list[placed_item_t]): ...

    @macro_template("ordered-items-incoming.html", "component")
    @staticmethod
    def component(placed_items: list[placed_item_t]): ...

    @macro_template("ordered-items-incoming.html", "component_with_sound")
    @staticmethod
    def component_with_sound(placed_items: list[placed_item_t]): ...


type item_t = dict[str, int | str | None]
type placement_t = dict[str, int | list[item_t] | str | datetime | None]


query_incoming: sqlalchemy.Select = (
    # Query from the placements table
    sqlmodel.select(Placement.placement_id)
    .group_by(col(Placement.placement_id))
    .order_by(col(Placement.placement_id).asc())
    .add_columns(unixepoch(col(Placement.placed_at)))
    # Filter out canceled/completed placements
    .where(col(Placement.canceled_at).is_(None) & col(Placement.completed_at).is_(None))
    # Query the list of placed items
    .select_from(sqlmodel.join(Placement, PlacedItem))
    .add_columns(col(PlacedItem.product_id), unixepoch(col(PlacedItem.supplied_at)))
    .group_by(col(PlacedItem.product_id))
    .order_by(col(PlacedItem.product_id).asc())
    .add_columns(sqlmodel.func.count(col(PlacedItem.product_id)).label("count"))
    # Query product name
    .join(Product)
    .add_columns(col(Product.name))
)


query_resolved: sqlalchemy.Select = (
    # Query from the placements table
    sqlmodel.select(Placement.placement_id)
    .group_by(col(Placement.placement_id))
    .order_by(col(Placement.placement_id).asc())
    .add_columns(unixepoch(col(Placement.placed_at)))
    # Query canceled/completed placements
    .where(
        col(Placement.canceled_at).isnot(None) | col(Placement.completed_at).isnot(None)
    )
    .add_columns(unixepoch(col(Placement.canceled_at)))
    .add_columns(unixepoch(col(Placement.completed_at)))
    # Query the list of placed items
    .select_from(sqlmodel.join(Placement, PlacedItem))
    .add_columns(col(PlacedItem.product_id), unixepoch(col(PlacedItem.supplied_at)))
    .group_by(col(PlacedItem.product_id))
    .order_by(col(PlacedItem.product_id).asc())
    .add_columns(sqlmodel.func.count(col(PlacedItem.product_id)).label("count"))
    # Query product name and price
    .join(Product)
    .add_columns(col(Product.name), col(Product.price))
)


def callbacks_placements_incoming(
    placements: list[placement_t],
) -> tuple[
    Callable[[int, Mapping], None],
    Callable[[Mapping], item_t],
    Callable[[list[item_t]], None],
]:
    def init_cb(placement_id: int, map: Mapping) -> None:
        placements.append(
            {
                "placement_id": placement_id,
                "placed_at": _to_time(map["placed_at"]),
            }
        )

    def elem_cb(map: Mapping) -> item_t:
        supplied_at = map["supplied_at"]
        return {
            "product_id": map["product_id"],
            "count": map["count"],
            "name": map["name"],
            "supplied_at": _to_time(supplied_at) if supplied_at else None,
        }

    def list_cb(items: list[item_t]) -> None:
        placements[-1]["items_"] = items

    return init_cb, elem_cb, list_cb


def callbacks_placements_resolved(
    placements: list[placement_t],
) -> tuple[
    Callable[[int, Mapping], None],
    Callable[[Mapping], item_t],
    Callable[[list[item_t]], None],
]:
    total_price = 0

    def init_cb(placement_id: int, map: Mapping) -> None:
        canceled_at, completed_at = map["canceled_at"], map["completed_at"]
        placements.append(
            {
                "placement_id": placement_id,
                "placed_at": _to_time(map["placed_at"]),
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
        placements[-1]["items_"] = items
        placements[-1]["total_price"] = Product.to_price_str(total_price)

    return init_cb, elem_cb, list_cb


def _placements_loader(
    query: sqlalchemy.Compiled,
    callbacks: Callable[
        [list[placement_t]],
        tuple[
            Callable[[int, Mapping], None],
            Callable[[Mapping], item_t],
            Callable[[list[item_t]], None],
        ],
    ],
) -> Callable[[], Awaitable[list[placement_t]]]:
    placements: list[placement_t] = []

    init_cb, elem_cb, list_cb = callbacks(placements)
    load_placements = partial(
        _agen_query_executor, str(query), "placement_id", init_cb, elem_cb, list_cb
    )

    async def load():
        placements.clear()
        await load_placements()
        return placements

    return load


load_incoming_placements = _placements_loader(
    query_incoming.compile(), callbacks_placements_incoming
)
load_resolved_placements = _placements_loader(
    query_resolved.compile(), callbacks_placements_resolved
)


async def load_one_resolved_placement(placement_id: int) -> placement_t | None:
    query = query_resolved.where(col(Placement.placement_id) == placement_id)

    rows_agen = database.iterate(query)
    if (row := await anext(rows_agen, None)) is None:
        return None

    canceled_at, completed_at = row["canceled_at"], row["completed_at"]
    placement: placement_t = {
        "placement_id": placement_id,
        "placed_at": _to_time(row["placed_at"]),
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
    placement["items_"] = items
    placement["total_price"] = Product.to_price_str(total_price)

    return placement


class incoming_orders:  # namespace
    @macro_template("incoming-orders.html")
    @staticmethod
    def page(placements: list[placement_t]): ...

    @macro_template("incoming-orders.html", "component")
    @staticmethod
    def component(placements: list[placement_t]): ...

    @macro_template("incoming-orders.html", "component_with_sound")
    @staticmethod
    def component_with_sound(placements: list[placement_t]): ...


class resolved_orders:  # namespace
    @macro_template("resolved-orders.html")
    @staticmethod
    def page(placements: list[placement_t]): ...

    @macro_template("resolved-orders.html", "completed")
    @staticmethod
    def completed(placement: placement_t): ...

    @macro_template("resolved-orders.html", "canceled")
    @staticmethod
    def canceled(placement: placement_t): ...


@router.get("/ordered-items/incoming", response_class=HTMLResponse)
async def get_incoming_ordered_items(request: Request):
    placed_items = await load_placed_items_incoming()
    return HTMLResponse(ordered_items_incoming.page(request, placed_items))


@router.get("/ordered-items/incoming-stream", response_class=EventSourceResponse)
async def ordered_items_incoming_stream(
    request: Request, accept: Annotated[Literal["text/event-stream"], Header()]
):
    _ = accept
    return EventSourceResponse(_ordered_items_incoming_stream(request))


async def _ordered_items_incoming_stream(request: Request):
    placed_items = await load_placed_items_incoming()
    content = ordered_items_incoming.component(request, placed_items)
    yield dict(data=content)
    try:
        while True:
            async with PlacementTable.modified_cond_flag:
                flag = await PlacementTable.modified_cond_flag.wait()
                if flag & (ModifiedFlag.INCOMING | ModifiedFlag.PUT_BACK):
                    template = ordered_items_incoming.component_with_sound
                else:
                    template = ordered_items_incoming.component
                placed_items = await load_placed_items_incoming()
                yield dict(data=template(request, placed_items))
    except asyncio.CancelledError:
        yield dict(event="shutdown", data="")
    finally:
        yield dict(event="shutdown", data="")


@router.post("/orders/{placement_id}/products/{product_id}/supplied-at")
async def supply_products(placement_id: int, product_id: int):
    await supply_and_complete_placement_if_done(placement_id, product_id)


@router.get("/orders/incoming", response_class=HTMLResponse)
async def get_incoming_orders(request: Request):
    placements = await load_incoming_placements()
    return HTMLResponse(incoming_orders.page(request, placements))


@router.get("/orders/incoming-stream", response_class=EventSourceResponse)
async def incoming_orders_stream(
    request: Request, accept: Annotated[Literal["text/event-stream"], Header()]
):
    _ = accept
    return EventSourceResponse(_incoming_orders_stream(request))


async def _incoming_orders_stream(
    request: Request,
) -> AsyncGenerator[dict[str, str], None]:
    placements = await load_incoming_placements()
    content = incoming_orders.component(request, placements)
    yield dict(data=content)
    try:
        while True:
            async with PlacementTable.modified_cond_flag:
                flag = await PlacementTable.modified_cond_flag.wait()
                if flag & (ModifiedFlag.INCOMING | ModifiedFlag.PUT_BACK):
                    template = incoming_orders.component_with_sound
                else:
                    template = incoming_orders.component
                placements = await load_incoming_placements()
                yield dict(data=template(request, placements))
    except asyncio.CancelledError:
        yield dict(event="shutdown", data="")
    finally:
        yield dict(event="shutdown", data="")


@router.get("/orders/resolved", response_class=HTMLResponse)
async def get_resolved_orders(request: Request):
    placements = await load_resolved_placements()
    return HTMLResponse(resolved_orders.page(request, placements))


@router.delete("/orders/{placement_id}/resolved-at")
async def reset(placement_id: int):
    await PlacementTable.reset(placement_id)


@router.post("/orders/{placement_id}/completed-at", response_class=HTMLResponse)
async def complete(
    request: Request, placement_id: int, card_response: Annotated[bool, Form()] = False
):
    if not card_response:
        await supply_all_and_complete(placement_id)
        return

    async with database.transaction():
        await supply_all_and_complete(placement_id)
        maybe_placement = await load_one_resolved_placement(placement_id)

    if (placement := maybe_placement) is None:
        detail = f"Placement {placement_id} not found"
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

    return HTMLResponse(resolved_orders.completed(request, placement))


@router.post("/orders/{placement_id}/canceled-at", response_class=HTMLResponse)
async def cancel(
    request: Request, placement_id: int, card_response: Annotated[bool, Form()] = False
):
    if not card_response:
        await PlacementTable.cancel(placement_id)
        return

    async with database.transaction():
        await PlacementTable.cancel(placement_id)
        maybe_placement = await load_one_resolved_placement(placement_id)

    if (placement := maybe_placement) is None:
        detail = f"Placement {placement_id} not found"
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

    return HTMLResponse(resolved_orders.canceled(request, placement))
