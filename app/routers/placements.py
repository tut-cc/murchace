import asyncio
from typing import Annotated, AsyncGenerator, Literal

from fastapi import APIRouter, Header, Request
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse

from .. import templates
from ..store import (
    PlacementTable,
    load_canceled_placements,
    load_completed_placements,
    load_incoming_placements,
)

router = APIRouter()


@router.get("/incoming-placements", response_class=HTMLResponse)
async def get_incoming_placements(request: Request):
    placements = await load_incoming_placements()
    return HTMLResponse(templates.incoming_placements(request, placements))


@router.get("/incoming-placements/stream", response_class=EventSourceResponse)
async def incoming_placements_stream(
    request: Request, accept: Annotated[Literal["text/event-stream"], Header()]
):
    return EventSourceResponse(_stream(request))


async def _stream(request: Request) -> AsyncGenerator[dict[str, str], None]:
    placements = await load_incoming_placements()
    content = templates.components.incoming_placements(request, placements)
    yield dict(data=content)
    try:
        while True:
            async with PlacementTable.modified:
                await PlacementTable.modified.wait()
                placements = await load_incoming_placements()
                content = templates.components.incoming_placements(request, placements)
                yield dict(data=content)
    except asyncio.CancelledError:
        yield dict(event="shutdown", data="")
    finally:
        yield dict(event="shutdown", data="")


@router.get("/canceled-placements", response_class=HTMLResponse)
async def get_canceled_placements(request: Request):
    placements = await load_canceled_placements()
    return HTMLResponse(templates.canceled_placements(request, placements))


@router.get("/completed-placements", response_class=HTMLResponse)
async def get_completed_placements(request: Request):
    placements = await load_completed_placements()
    return HTMLResponse(templates.completed_placements(request, placements))


@router.post("/incoming-placements/{placement_id}")
async def reset_placement(placement_id: int):
    await PlacementTable.reset(placement_id)


@router.post("/completed-placements/{placement_id}")
async def complete_placement(placement_id: int):
    await PlacementTable.complete(placement_id)


@router.post("/canceled-placements/{placement_id}")
async def cancel_placement(placement_id: int):
    await PlacementTable.cancel(placement_id)
