from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from ..db import PlacedOrderTable, PlacementStatusTable, Product, ProductTable
from ..templates import templates

router = APIRouter()

# NOTE: Do NOT store this data in database (the data is transient and should be kept in memory)
# NOTE: Or should this be optionally stored in database?
order_sessions: dict[int, list[Product | None]] = {}
last_session_id = 0


# TODO: this path should use a post method
# Also consider using this: https://htmx.org/headers/hx-location/
@router.get("/order", response_class=RedirectResponse)
async def get_order_redirect():
    return RedirectResponse("/order/new")


# TODO: move the session generation logic to /order and remove this path
@router.get("/order/new", response_class=RedirectResponse)
async def get_order_new():
    global last_session_id
    last_session_id += 1
    new_session_id = last_session_id
    order_sessions[new_session_id] = []
    return RedirectResponse(f"/order/{new_session_id}")


@router.get("/order/{session_id}", response_class=HTMLResponse)
async def get_order_session(request: Request, session_id: int):
    order_items = order_sessions.get(session_id)
    if order_items is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    idx_item_pairs = [
        (idx, item) for idx, item in enumerate(order_items) if item is not None
    ]
    return templates.TemplateResponse(
        "order.html",
        {
            "request": request,
            "products": await ProductTable.select_all(),
            "session_id": session_id,
            "idx_item_pairs": idx_item_pairs,
        },
    )


@router.post("/order/{session_id}", response_class=HTMLResponse)
async def place_order(request: Request, session_id: int):
    if (order_items := order_sessions.get(session_id)) is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    idx_item_pairs = [
        (idx, item) for idx, item in enumerate(order_items) if item is not None
    ]

    if len(idx_item_pairs) == 0:
        return templates.TemplateResponse(
            "components/order-session.html",
            {
                "request": request,
                "session_id": session_id,
                "idx_item_pairs": [],
                "placement_status": "Error: there is no item",
            },
        )

    order_sessions.pop(session_id)

    placement_id = await PlacedOrderTable.issue(
        [item.product_id for item in order_items if item is not None]
    )
    # TODO: add a branch for out of stock error
    await PlacementStatusTable.insert(placement_id)
    placement_status = f"発行注文番号: {placement_id}"
    return templates.TemplateResponse(
        "components/order-session.html",
        {
            "request": request,
            "session_id": session_id,
            "idx_item_pairs": idx_item_pairs,
            "placement_status": placement_status,
            "order_frozen": True,
        },
    )


@router.post("/order/{session_id}/item")
async def add_order_item(
    request: Request, session_id: int, product_id: int
) -> Response:
    if (product := await ProductTable.by_product_id(product_id)) is None:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    if (order_items := order_sessions.get(session_id)) is None:
        # NOTE: the branching below is a bit complicated so it might be changed in the future
        if request.headers["HX-Request"] == "true":
            # If it is a request from `hx-post`, respond with a new order session even when the `session_id` is not valid
            global last_session_id
            await get_order_new()
            new_session_id = last_session_id
            await add_order_item(request, new_session_id, product_id)
            return Response(
                f"Session {session_id} not found",
                status_code=404,
                headers={"hx-redirect": f"/order/{new_session_id}"},
            )
        else:
            # otherwise report back that the `session_id` is not valid
            raise HTTPException(
                status_code=404, detail=f"Session {session_id} not found"
            )

    order_items.append(product)
    idx_item_pairs = [
        (idx, item) for idx, item in enumerate(order_items) if item is not None
    ]
    return templates.TemplateResponse(
        "components/order-session.html",
        {
            "request": request,
            "session_id": session_id,
            "idx_item_pairs": idx_item_pairs,
        },
    )


@router.delete("/order/{session_id}/item/{index}", response_class=HTMLResponse)
async def delete_order_item(session_id: int, index: int):
    order_items = order_sessions.get(session_id)
    if order_items is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    if order_items[index] is None:
        raise HTTPException(status_code=404, detail=f"Order item {index} not found")
    else:
        order_items[index] = None
    return


# TODO: change this to @router.delete("/order/{session_id}")
@router.post("/order/{session_id}/clear")
async def clear_order_items(request: Request, session_id: int) -> Response:
    if (order_items := order_sessions.get(session_id)) is None:
        # NOTE: the branching below is a bit complicated so it might be changed in the future
        if request.headers.get("HX-Request") == "true":
            # If it is a request from `hx-post`, respond with a new order session even when the `session_id` is not valid
            global last_session_id
            await get_order_new()
            new_session_id = last_session_id
            return Response(
                f"Session {session_id} not found",
                status_code=404,
                headers={"hx-redirect": f"/order/{new_session_id}"},
            )
        else:
            # otherwise report back that the `session_id` is not valid
            raise HTTPException(
                status_code=404, detail=f"Session {session_id} not found"
            )

    order_items.clear()

    return templates.TemplateResponse(
        "components/order-session.html",
        {
            "request": request,
            "session_id": session_id,
            "idx_item_pairs": [],
        },
    )


# TODO: add proper path operation for order deferral
# # TODO: Store this data in database
# deferred_order_lists: dict[int, list[Product | None]] = {}
#
#
# @router.post("/deferal/", response_class=HTMLResponse)
# async def post_order_defer_session(request: Request, session_id: int):
#     if (order_items := order_sessions.get(session_id)) is None:
#         raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
#     if deferred_order_lists.get(session_id):
#         raise HTTPException(
#             status_code=status.HTTP_409_CONFLICT,
#             detail=f"Deferred session {session_id} already exists",
#         )
#     order_sessions.pop(session_id)
#     deferred_order_lists[session_id] = order_items
#     # TODO: respond with a message about the success of the deferral action
#     # return templates.TemplateResponse(
#     #     "components/item.html",
#     #     {
#     #         "request": request,
#     #         "session_id": session_id,
#     #     },
#     # )
