# from typing import Annotated

# from fastapi import APIRouter, Header, Request
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

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
