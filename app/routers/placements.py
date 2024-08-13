from fastapi import APIRouter, HTTPException, Request

from ..db import PlacedOrderTable, PlacementStatusTable
from ..templates import templates

router = APIRouter()


@router.get("/placements")
async def get_placements(
    request: Request, canceled: bool = False, completed: bool = False
):
    # +--------+  +--------+  +--------+  +--------+
    # | plcmnt |  | plcmnt |  | plcmnt |  | plcmnt |
    # +--------+  +--------+  +--------+  +--------+
    #
    # +--------+  +--------+  +--------+  +--------+
    # | plcmnt |  | plcmnt |  | plcmnt |  | plcmnt |
    # +--------+  +--------+  +--------+  +--------+
    #
    # +------------------------+
    # | - placemnet id         |
    # | - products             |
    # |   - {product_name} x n |
    # |   - {product_name} x n |
    # |   - {product_name} x n |
    # | - total price          |
    # | - [ ] cancel           |
    # | - [ ] complete         |
    # +------------------------+

    placements = await PlacedOrderTable.select_placements(canceled, completed)

    if request.headers.get("HX-Request") == "true":
        return templates.TemplateResponse(
            request,
            "components/placements.html",
            {"placements": placements, "canceled": canceled, "completed": completed},
        )
    else:
        return templates.TemplateResponse(
            request,
            "placements.html",
            {"placements": placements, "canceled": canceled, "completed": completed},
        )


@router.get("/placements/{placement_id}")
async def get_placement(request: Request, placement_id: int):
    if (placement := await PlacementStatusTable.by_placement_id(placement_id)) is None:
        raise HTTPException(404, f"Placement {placement_id} not found")
    # TODO: write down components/placement.html template
    return templates.TemplateResponse(
        request, "components/placement.html", {"placement": placement}
    )


@router.post("/placements/{placement_id}")
async def complete_placement(request: Request, placement_id: int):
    await PlacementStatusTable.complete(placement_id)


@router.delete("/placements/{placement_id}")
async def cancel_placement(request: Request, placement_id: int):
    await PlacementStatusTable.cancel(placement_id)
