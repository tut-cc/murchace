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
import pydantic

from ..store import PlacedItemTable, PlacementTable, Product, ProductTable
from ..templates import hx_post as tmp_hx_post
from ..templates import macro_template

router = APIRouter()


class OrderSession(pydantic.BaseModel):
    class CountedProduct(pydantic.BaseModel):
        name: str
        price: str
        count: int = pydantic.Field(default=1)

    items: dict[UUID, Product] = pydantic.Field(default_factory=dict)
    counted_products: dict[int, CountedProduct] = pydantic.Field(default_factory=dict)
    total_count: int = pydantic.Field(default=0)
    total_price: int = pydantic.Field(default=0)

    def clear(self):
        self.total_count = 0
        self.total_price = 0
        self.items = {}
        self.counted_products = {}

    def total_price_str(self) -> str:
        return Product.to_price_str(self.total_price)

    def add(self, p: Product):
        self.total_count += 1
        self.total_price += p.price
        self.items[uuid4()] = p
        if p.product_id in self.counted_products:
            self.counted_products[p.product_id].count += 1
        else:
            counted_product = self.CountedProduct(name=p.name, price=p.price_str())
            self.counted_products[p.product_id] = counted_product

    def delete(self, item_id: UUID):
        if item_id in self.items:
            self.total_count -= 1
            product = self.items.pop(item_id)
            self.total_price -= product.price
            if self.counted_products[product.product_id].count == 1:
                self.counted_products.pop(product.product_id)
            else:
                self.counted_products[product.product_id].count -= 1


@macro_template("register.html")
def tmp_register(products: list[Product], session: OrderSession): ...


@macro_template("register.html", "order_session")
def tmp_session(session: OrderSession): ...


@macro_template("register.html", "confirm_modal")
def tmp_confirm_modal(session: OrderSession): ...


@macro_template("register.html", "issued_modal")
def tmp_issued_modal(order_id: int, session: OrderSession): ...


@macro_template("register.html", "error_modal")
def tmp_error_modal(message: str): ...


# NOTE: Do NOT store this data in database because the data is transient and should be kept in memory
order_sessions: dict[UUID, OrderSession] = {}
SESSION_COOKIE_KEY = "session_key"


async def order_session_dep(session_key: Annotated[UUID, Cookie()]) -> OrderSession:
    if (order_session := order_sessions.get(session_key)) is None:
        raise HTTPException(status_code=404, detail=f"Session {session_key} not found")
    return order_session


SessionDeps = Annotated[OrderSession, Depends(order_session_dep)]


@router.get("/register", response_class=HTMLResponse)
async def instruct_creation_of_new_session_or_get_existing_session(
    request: Request, session_key: Annotated[UUID | None, Cookie()] = None
):
    if session_key is None or (session := order_sessions.get(session_key)) is None:
        return HTMLResponse(
            tmp_hx_post(request, "/register"),
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
            headers={"allow": "POST"},
        )

    products = await ProductTable.select_all()
    return HTMLResponse(tmp_register(request, products, session))


@router.get("/register/confirm-modal", response_class=HTMLResponse)
async def get_confirm_dialog(request: Request, session: SessionDeps):
    if session.total_count == 0:
        error_msg = "商品が選択されていません"
        return HTMLResponse(tmp_error_modal(request, error_msg))
    else:
        return HTMLResponse(tmp_confirm_modal(request, session))


@router.post("/register")
async def create_new_session_or_place_order(
    request: Request, session_key: Annotated[UUID | None, Cookie()] = None
):
    if session_key is None or (session := order_sessions.get(session_key)) is None:
        session_key = _create_new_session()

        LOCATION = "/register"
        headers = {"location": LOCATION, "hx-location": LOCATION}
        res = Response(LOCATION, status_code=status.HTTP_201_CREATED, headers=headers)
        res.set_cookie(SESSION_COOKIE_KEY, str(session_key))
        return res

    if session.total_count == 0:
        error_msg = "商品が選択されていません"
        return HTMLResponse(tmp_error_modal(request, error_msg))

    order_sessions.pop(session_key)
    res = await _place_order(request, session)
    res.delete_cookie(SESSION_COOKIE_KEY)
    return res


def _create_new_session() -> UUID:
    session_key = uuid4()
    order_sessions[session_key] = OrderSession()
    return session_key


async def _place_order(request: Request, session: SessionDeps) -> HTMLResponse:
    product_ids = [item.product_id for item in session.items.values()]
    order_id = await PlacedItemTable.issue(product_ids)
    # TODO: add a branch for out of stock error
    await PlacementTable.insert(order_id)
    return HTMLResponse(tmp_issued_modal(request, order_id, session))


@router.post("/register/items")
async def add_session_item(
    request: Request, session: SessionDeps, product_id: Annotated[int, Form()]
) -> Response:
    if (product := await ProductTable.by_product_id(product_id)) is None:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")

    session.add(product)
    return HTMLResponse(tmp_session(request, session))


@router.delete("/register/items/{item_id}", response_class=HTMLResponse)
async def delete_session_item(request: Request, session: SessionDeps, item_id: UUID):
    session.delete(item_id)
    return HTMLResponse(tmp_session(request, session))


@router.delete("/register/items")
async def clear_session_items(request: Request, session: SessionDeps) -> Response:
    session.clear()
    return HTMLResponse(tmp_session(request, session))


# TODO: add proper path operation for order deferral
# # TODO: Store this data in database
# deferred_order_sessions: dict[int, OrderSession] = {}
#
#
# @router.post("/register/deferred", response_class=HTMLResponse)
# async def post_defer_session(request: Request, session_key: Annotated[UUID, Cookie()]):
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
#     #     tmp_session(request, OrderSession(), message=message)
#     # )
#     # res.delete_cookie(SESSION_COOKIE_KEY)
#     # return res
