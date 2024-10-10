import asyncio
from typing import Annotated, AsyncGenerator, Literal

from fastapi import APIRouter, Form, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse

from .. import templates
from ..store import (
    PlacementTable,
    database,
    load_incoming_placements,
    load_one_resolved_placement,
    load_placed_items_incoming,
    load_resolved_placements,
    supply_all_and_complete,
    supply_and_complete_placement_if_done,
)

router = APIRouter()


@router.get("/placed-items/incoming", response_class=HTMLResponse)
async def get_incoming_placed_items(request: Request):
    placed_items = await load_placed_items_incoming()
    return HTMLResponse(templates.placed_items_incoming.page(request, placed_items))


@router.get("/placed-items/incoming-stream", response_class=EventSourceResponse)
async def placed_items_incoming_stream(
    request: Request, accept: Annotated[Literal["text/event-stream"], Header()]
):
    _ = accept
    return EventSourceResponse(_placed_items_incoming_stream(request))


async def _placed_items_incoming_stream(request: Request):
    placed_items = await load_placed_items_incoming()
    content = templates.placed_items_incoming.component(request, placed_items)
    yield dict(data=content)
    try:
        while True:
            async with PlacementTable.modified:
                await PlacementTable.modified.wait()
                placed_items = await load_placed_items_incoming()
                content = templates.placed_items_incoming.component(
                    request, placed_items
                )
                yield dict(data=content)
    except asyncio.CancelledError:
        yield dict(event="shutdown", data="")
    finally:
        yield dict(event="shutdown", data="")


@router.post("/placements/{placement_id}/products/{product_id}/supplied-at")
async def supply_products(placement_id: int, product_id: int):
    await supply_and_complete_placement_if_done(placement_id, product_id)


@router.get("/placements/incoming", response_class=HTMLResponse)
async def get_incoming_placements(request: Request):
    placements = await load_incoming_placements()
    return HTMLResponse(templates.incoming_placements.page(request, placements))


@router.get("/placements/incoming-stream", response_class=EventSourceResponse)
async def incoming_placements_stream(
    request: Request, accept: Annotated[Literal["text/event-stream"], Header()]
):
    _ = accept
    return EventSourceResponse(_incoming_placements_stream(request))


async def _incoming_placements_stream(
    request: Request,
) -> AsyncGenerator[dict[str, str], None]:
    placements = await load_incoming_placements()
    content = templates.incoming_placements.component(request, placements)
    yield dict(data=content)
    try:
        while True:
            async with PlacementTable.modified:
                await PlacementTable.modified.wait()
                placements = await load_incoming_placements()
                content = templates.incoming_placements.component(request, placements)
                yield dict(data=content)
    except asyncio.CancelledError:
        yield dict(event="shutdown", data="")
    finally:
        yield dict(event="shutdown", data="")


@router.get("/placements/resolved", response_class=HTMLResponse)
async def get_resolved_placements(request: Request):
    placements = await load_resolved_placements()
    return HTMLResponse(templates.resolved_placements.page(request, placements))


@router.delete("/placements/{placement_id}/resolved-at")
async def reset(placement_id: int):
    await PlacementTable.reset(placement_id)


@router.post("/placements/{placement_id}/completed-at", response_class=HTMLResponse)
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

    return HTMLResponse(templates.resolved_placements.completed(request, placement))


@router.post("/placements/{placement_id}/canceled-at", response_class=HTMLResponse)
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

    return HTMLResponse(templates.resolved_placements.canceled(request, placement))
