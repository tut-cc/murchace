from typing import Annotated
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    Form,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.responses import HTMLResponse

from .. import templates
from ..store import PlacedItemTable, PlacementTable, ProductTable
from ..store.product import OrderSession

router = APIRouter()

# NOTE: Do NOT store this data in database (the data is transient and should be kept in memory)
order_sessions: dict[UUID, OrderSession] = {}
SESSION_COOKIE_KEY = "session_key"


async def order_session_dep(session_key: Annotated[UUID, Cookie()]) -> OrderSession:
    if (order_session := order_sessions.get(session_key)) is None:
        raise HTTPException(status_code=404, detail=f"Session {session_key} not found")
    return order_session


SessionDeps = Annotated[OrderSession, Depends(order_session_dep)]


@router.get("/order", response_class=HTMLResponse)
async def instruct_creation_of_new_session_or_get_existing_session(
    request: Request, session_key: Annotated[UUID | None, Cookie()] = None
):
    if session_key is None or (session := order_sessions.get(session_key)) is None:
        return HTMLResponse(
            templates.hx_post(request, "/order"),
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
            headers={"allow": "POST"},
        )

    products = await ProductTable.select_all()
    return HTMLResponse(templates.order(request, products, session))


@router.get("/order/confirm", response_class=HTMLResponse)
async def get_confirm_dialog(request: Request, session: SessionDeps):
    if session.total_count == 0:
        error_status = "エラー：商品が選択されていません"
    else:
        error_status = None
    return HTMLResponse(
        templates.components.order_confirm(request, session, error_status)
    )


@router.post("/order")
async def create_new_session_or_place_order(
    request: Request, session_key: Annotated[UUID | None, Cookie()] = None
):
    if session_key is None or (session := order_sessions.get(session_key)) is None:
        session_key = _create_new_session()

        LOCATION = "/order"
        headers = {"location": LOCATION, "hx-location": LOCATION}
        res = Response(LOCATION, status_code=status.HTTP_201_CREATED, headers=headers)
        res.set_cookie(SESSION_COOKIE_KEY, str(session_key))
        return res

    if session.total_count == 0:
        error_status = "エラー：商品が選択されていません"
        return HTMLResponse(
            templates.components.order_issued(request, None, session, error_status)
        )

    order_sessions.pop(session_key)
    res = await _place_order(request, session)
    res.delete_cookie(SESSION_COOKIE_KEY)
    return res


def _create_new_session() -> UUID:
    session_key = uuid4()
    session = OrderSession()
    order_sessions[session_key] = session
    return session_key


async def _place_order(request: Request, session: SessionDeps) -> HTMLResponse:
    product_ids = [item.product_id for item in session.items.values()]
    placement_id = await PlacedItemTable.issue(product_ids)
    # TODO: add a branch for out of stock error
    await PlacementTable.insert(placement_id)
    return HTMLResponse(
        templates.components.order_issued(request, placement_id, session, None)
    )


@router.post("/order/items")
async def add_order_item(
    request: Request, session: SessionDeps, product_id: Annotated[int, Form()]
) -> Response:
    if (product := await ProductTable.by_product_id(product_id)) is None:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")

    session.add(product)
    return HTMLResponse(templates.components.order_session(request, session))


@router.delete("/order/items/{item_id}", response_class=HTMLResponse)
async def delete_order_item(request: Request, session: SessionDeps, item_id: UUID):
    session.delete(item_id)
    return HTMLResponse(templates.components.order_session(request, session))


@router.delete("/order/items")
async def clear_order_items(request: Request, session: SessionDeps) -> Response:
    session.clear()
    return HTMLResponse(templates.components.order_session(request, session))


# TODO: add proper path operation for order deferral
# # TODO: Store this data in database
# deferred_order_sessions: dict[int, OrderSession] = {}
#
#
# @router.post("/deferred_orders/", response_class=HTMLResponse)
# async def post_order_defer_session(request: Request, session_key: Annotated[UUID, Cookie()]):
#     order_session = await order_session_dep(session_key)
#     if order_session in deferred_order_sessions:
#         raise HTTPException(
#             status_code=status.HTTP_409_CONFLICT,
#             detail=f"Deferred session already exists",
#         )
#     deferred_order_sessions.append(order_sessions.pop(session_key))
#     # TODO: respond with a message about the success of the deferral action
#     # message = "注文を保留しました"
#     # res = HTMLResponse(
#     #     templates.components.order_session(request, OrderSession(), message=message)
#     # )
#     # res.delete_cookie(SESSION_COOKIE_KEY)
#     # return res
