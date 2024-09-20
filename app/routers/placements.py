from typing import Annotated

from fastapi import APIRouter, Header, Request
from fastapi.responses import HTMLResponse

from .. import templates
from ..store import PlacementTable, select_placements

router = APIRouter()


@router.get("/placements", response_class=HTMLResponse)
async def get_placements(
    request: Request,
    canceled: bool = False,
    completed: bool = False,
    hx_request: Annotated[str | None, Header()] = None,
):
    placements = await select_placements(canceled, completed)
    macro = (
        templates.components.placements
        if hx_request == "true"
        else templates.placements
    )
    return HTMLResponse(macro(request, placements, canceled, completed))


# @router.get("/placements/{placement_id}")
# async def get_placement(request: Request, placement_id: int):
#     if (placement := await PlacementTable.by_placement_id(placement_id)) is None:
#         raise HTTPException(404, f"Placement {placement_id} not found")
#     return templates.components.placement(request, placement)


@router.post("/placements/{placement_id}")
async def complete_placement(placement_id: int):
    await PlacementTable.complete(placement_id)


@router.delete("/placements/{placement_id}")
async def cancel_placement(placement_id: int):
    await PlacementTable.cancel(placement_id)
