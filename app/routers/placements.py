import asyncio
from typing import Annotated, AsyncGenerator, Literal

from fastapi import APIRouter, Header, Request
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse

from .. import templates
from ..store import (
    PlacementTable,
    load_resolved_placements,
    load_incoming_placements,
)

router = APIRouter()


@router.get("/placements/incoming", response_class=HTMLResponse)
async def get_incoming_placements(request: Request):
    placements = await load_incoming_placements()
    return HTMLResponse(templates.incoming_placements(request, placements))


@router.get("/placements/incoming-stream", response_class=EventSourceResponse)
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


@router.get("/placements/resolved", response_class=HTMLResponse)
async def get_resolved_placements(request: Request):
    placements = await load_resolved_placements()
    return HTMLResponse(templates.resolved_placements(request, placements))


@router.delete("/placements/{placement_id}/resolved-at")
async def reset_placement(placement_id: int):
    await PlacementTable.reset(placement_id)


@router.post("/placements/{placement_id}/completed-at")
async def complete_placement(placement_id: int):
    await PlacementTable.complete(placement_id)


@router.post("/placements/{placement_id}/canceled-at")
async def cancel_placement(placement_id: int):
    await PlacementTable.cancel(placement_id)
