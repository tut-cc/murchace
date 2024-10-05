from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse

from .. import templates
from ..store import PlacedItemTable, PlacementTable, ProductTable
from ..store.product import OrderSession

router = APIRouter()

# NOTE: Do NOT store this data in database (the data is transient and should be kept in memory)
# NOTE: Or should this be optionally stored in database?
order_sessions: dict[int, OrderSession] = {}
last_session_id = 0


def create_new_session() -> int:
    global last_session_id
    last_session_id += 1
    new_session_id = last_session_id
    order_sessions[new_session_id] = OrderSession()
    return new_session_id


@router.post("/orders", response_class=Response)
async def create_new_order():
    location = f"/orders/{create_new_session()}"
    return Response(
        location,
        status_code=status.HTTP_201_CREATED,
        headers={"location": location, "hx-location": location},
    )


@router.get("/orders/{session_id}", response_class=HTMLResponse)
async def get_order_session(request: Request, session_id: int):
    if (order_session := order_sessions.get(session_id)) is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    products = await ProductTable.select_all()
    return HTMLResponse(templates.orders(request, session_id, products, order_session))


@router.get("/orders/{session_id}/confirm", response_class=HTMLResponse)
async def get_order_session_to_confirm(request: Request, session_id: int):
    if (order_session := order_sessions.get(session_id)) is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    if order_session.total_count == 0:
        error_status = "エラー：商品が選択されていません"
    else:
        error_status = None
    return HTMLResponse(
        templates.components.order_confirm(
            request,
            session_id,
            order_session,
            error_status,
        )
    )


@router.post("/orders/{session_id}", response_class=HTMLResponse)
async def place_order(request: Request, session_id: int):
    if (order_session := order_sessions.get(session_id)) is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    if order_session.total_count == 0:
        error_status = "エラー：商品が選択されていません"
        placement_id = None
    else:
        error_status = None
        order_sessions.pop(session_id)
        product_ids = [item.product_id for item in order_session.products.values()]
        placement_id = await PlacedItemTable.issue(product_ids)
        # TODO: add a branch for out of stock error
        await PlacementTable.insert(placement_id)

    return HTMLResponse(
        templates.components.order_issued(
            request,
            session_id,
            placement_id,
            order_session,
            error_status,
        )
    )


@router.post("/orders/{session_id}/item")
async def add_order_item(
    request: Request,
    session_id: int,
    product_id: Annotated[int, Form()],
) -> Response:
    if (product := await ProductTable.by_product_id(product_id)) is None:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    if (order_session := order_sessions.get(session_id)) is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    order_session.add(product)
    return HTMLResponse(
        templates.components.order_session(
            request,
            session_id,
            order_session,
        )
    )


@router.delete("/orders/{session_id}/item/{index}", response_class=HTMLResponse)
async def delete_order_item(request: Request, session_id: int, index: UUID):
    if (order_session := order_sessions.get(session_id)) is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    order_session.delete(index)
    return HTMLResponse(
        templates.components.order_session(
            request,
            session_id,
            order_session,
        )
    )


@router.delete("/orders/{session_id}")
async def clear_order_items(
    request: Request,
    session_id: int,
) -> Response:
    if (order_session := order_sessions.get(session_id)) is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    order_session.clear()
    return HTMLResponse(
        templates.components.order_session(
            request,
            session_id,
            order_session,
        )
    )


# TODO: add proper path operation for order deferral
# # TODO: Store this data in database
# deferred_order_lists: dict[int, list[Product | None]] = {}
#
#
# @router.post("/deferred_orders/{session_id}", response_class=HTMLResponse)
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
#     # placement_status = "注文を保留しました"
#     # return HTMLResponse(
#     #     templates.components.order_session(request, session_id, [], Product.to_price_str(0), placement_status=placement_status)
#     # )
