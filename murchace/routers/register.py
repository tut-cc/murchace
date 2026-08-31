from collections.abc import Iterable
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID, uuid4

from datastar_py import attribute_generator as data
from datastar_py.fastapi import DatastarResponse
from datastar_py.sse import ServerSentEventGenerator as SSE
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from htpy import (
    Element,
    HTMLElement,
    a,
    article,
    aside,
    button,
    div,
    figcaption,
    figure,
    h2,
    img,
    li,
    main,
    p,
    span,
    ul,
)

from ..components import clock, page_layout
from ..store import OrderedItemTable, OrderTable, Product, ProductTable

router = APIRouter()


@dataclass
class OrderSession:
    @dataclass
    class CountedProduct:
        name: str
        price: str
        count: int = 1

    items: dict[UUID, Product]
    counted_products: dict[int, CountedProduct]
    total_count: int = 0
    total_price: int = 0

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


def page_register(req: Request) -> HTMLElement:
    return page_layout(
        req,
        div(data.init("@post('/register')"), id="register", class_="hidden"),
        "新規注文 - murchace",
    )


def register(
    req: Request, products: list[Product], session: OrderSession
) -> HTMLElement:
    inner = div(id="register", class_="h-dvh flex flex-row")[
        main(
            class_="w-1/2 lg:w-4/6 h-full grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 2xl:grid-cols-6 auto-cols-max auto-rows-min gap-2 py-2 pl-10 pr-6 overflow-y-auto"
        )[
            [
                figure(
                    data.on(
                        "click",
                        f"@post('/register/items?product_id={product.product_id}')",
                    ),
                    class_="flex flex-col border-4 border-gray-200 rounded-md transition-colors ease-in-out active:bg-gray-100",
                )[
                    img(
                        class_="mx-auto w-full h-auto aspect-square",
                        src=str(req.url_for("static", path=product.filename)),
                        alt=product.name,
                    ),
                    figcaption(class_="text-center truncate")[product.name],
                    div(class_="text-center")[product.price_str()],
                ]
                for product in products
            ]
        ],
        aside(class_="w-1/2 lg:w-2/6 h-full flex flex-col p-4 justify-between")[
            div(class_="flex flex-row py-2 justify-around items-center text-xl")[
                a(
                    href="/",
                    class_="px-2 py-1 rounded-sm bg-gray-300 hidden lg:inline-block",
                )["ホーム"],
                button(
                    data.on("click", "@delete('/register/items')"),
                    class_="text-white px-2 py-1 rounded-sm bg-red-600 hidden sm:inline-block",
                    tabindex="0",
                )["全消去"],
                div(class_="text-xl hidden md:inline-block")[clock],
            ],
            order_session(session),
        ],
    ]
    return page_layout(req, inner, "新規注文 - murchace")


def order_session(session: OrderSession) -> Element:
    def item(item_id: UUID, product: Product):
        return li(id=f"item-{item_id}", class_="flex justify-between")[
            div(
                class_="overflow-x-auto whitespace-nowrap sm:flex sm:flex-1 sm:justify-between p-4"
            )[p(class_="sm:flex-1")[product.name], div[product.price_str()]],
            div(class_="flex items-center")[
                button(
                    data.on("click", f"@delete('/register/items/{item_id}')"),
                    class_="font-bold text-white bg-red-600 px-2 rounded-sm",
                )["X"]
            ],
        ]

    return div(id="order-session", class_="min-h-0 pt-2 flex flex-col")[
        # `flex-col-reverse` lets the browser to pin scroll to bottom
        div(class_="flex flex-col-reverse overflow-y-auto")[
            ul(class_="text-lg divide-y-4 divide-gray-200")[
                [item(item_id, product) for item_id, product in session.items.items()]
            ]
        ],
        div(class_="flex flex-row p-2 items-center")[
            div(class_="basis-1/4 text-right lg:text-2xl")[f"{session.total_count} 点"],
            div(class_="basis-2/4 text-center lg:text-2xl")[
                f"合計: {session.total_price_str()}"
            ],
            button(
                data.on("click", "@get('/register/confirm-modal')"),
                class_="basis-1/4 lg:text-xl text-center text-white p-2 rounded-sm bg-blue-600 disabled:cursor-not-allowed disabled:text-gray-700 disabled:bg-gray-100",
                disabled=True if session.total_count == 0 else None,
            )["確定"],
            div(id="order-modal-container"),
        ],
    ]


def confirm_modal(session: OrderSession) -> Element:
    return div(id="order-modal-container")[
        div(
            id="order-modal",
            class_="z-10 fixed inset-0 w-dvw h-dvh py-4 flex items-center bg-gray-500/75",
            role="dialog",
            aria_modal="true",
            onclick="this.remove()",
        )[
            div(
                id="order-confirm-modal",
                class_="mx-auto w-1/3 h-4/5 p-4 flex flex-col gap-y-2 rounded-lg bg-white animate-[scale-50_150ms_ease-in]",
                onclick="event.stopPropagation()",
            )[
                article(
                    class_="grow min-h-0 flex flex-col gap-y-2 px-3 text-center text-lg"
                )[
                    h2(class_="font-semibold")["注文の確定"],
                    _total(
                        session.counted_products.values(),
                        session.total_count,
                        session.total_price_str(),
                    ),
                ],
                button(
                    data.on("click", "@post('/register')"),
                    class_="w-full py-4 text-center text-xl font-semibold text-white bg-blue-600 rounded-sm",
                )["確認"],
                button(
                    class_="w-full py-4 text-center text-xl font-semibold bg-white border border-gray-300 rounded-sm",
                    onclick="window['order-modal'].remove()",
                )["閉じる"],
            ]
        ]
    ]


def issued_modal(order_id: int, session: OrderSession) -> Element:
    return div(id="order-modal-container")[
        div(
            id="order-modal",
            class_="z-10 fixed inset-0 w-dvw h-dvh py-4 flex items-center bg-gray-500/75",
            role="dialog",
            aria_modal="true",
        )[
            div(
                class_="mx-auto w-1/3 h-4/5 p-4 flex flex-col gap-y-2 rounded-lg bg-white animate-[scale-95_150ms_ease-in]"
            )[
                article(
                    class_="grow min-h-0 flex flex-col gap-y-2 px-3 text-center text-lg"
                )[
                    h2(class_="font-semibold")[f"注文番号 #{order_id}"],
                    _total(
                        session.counted_products.values(),
                        session.total_count,
                        session.total_price_str(),
                    ),
                ],
                button(
                    data.on("click", "@post('/register')"),
                    class_="w-full py-4 text-center text-xl font-semibold text-white bg-green-600 rounded-sm",
                )["新規"],
                a(
                    href="/",
                    class_="w-full py-4 text-center text-xl font-semibold bg-white border border-gray-300 rounded-sm",
                )["ホームに戻る"],
            ]
        ]
    ]


def _total(
    counted_products: Iterable[OrderSession.CountedProduct],
    total_count: int,
    total_price: str,
) -> list[Element]:
    return [
        ul(class_="grow flex flex-col overflow-y-auto")[
            (
                li(class_="flex flex-row items-start gap-x-2")[
                    span(class_="break-words")[counted_product.name],
                    span(class_="ml-auto whitespace-nowrap")[
                        f"{counted_product.price} x {counted_product.count}"
                    ],
                ]
                for counted_product in counted_products
            )
        ],
        div[
            p(class_="flex flex-row")[
                span["計"],
                span(class_="ml-auto whitespace-nowrap")[f"{total_count} 点"],
            ],
            p(class_="flex flex-row")[
                span(class_="break-words")["合計金額"],
                span(class_="ml-auto")[total_price],
            ],
        ],
    ]


def error_modal(message: str) -> Element:
    return div(id="order-modal-container")[
        div(
            id="order-modal",
            class_="z-10 fixed inset-0 w-dvw h-dvh py-4 flex items-center bg-gray-500/75",
            role="dialog",
            aria_modal="true",
        )[
            div(
                id="order-error-modal",
                class_="mx-auto w-1/3 h-4/5 p-4 flex flex-col gap-y-2 rounded-lg bg-white [.datastar-settling_&]:scale-50 transition-transform duration-150",
            )[
                article(
                    class_="grow min-h-0 flex flex-col gap-y-2 px-3 text-center text-lg"
                )[h2(class_="font-semibold text-red-500")["エラー"], p[message]],
                button(
                    class_="w-full py-4 text-center text-xl font-semibold bg-white border border-gray-300 rounded-sm",
                    onclick="window['order-modal'].remove()",
                )["閉じる"],
            ]
        ]
    ]


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
        return HTMLResponse(page_register(request))

    products = await ProductTable.select_all()
    return HTMLResponse(register(request, products, session))


@router.get("/register/confirm-modal")
async def get_confirm_dialog(session: SessionDeps):
    if session.total_count == 0:
        fragment = error_modal("商品が選択されていません")
    else:
        fragment = confirm_modal(session)
    return DatastarResponse(SSE.patch_elements(fragment))


@router.post("/register")
async def create_new_session_or_place_order(
    session_key: Annotated[UUID | None, Cookie()] = None,
):
    if session_key is None or (session := order_sessions.get(session_key)) is None:
        session_key = _create_new_session()

        res = DatastarResponse(SSE.execute_script("location.reload()"))
        res.headers["location"] = "/register"
        res.set_cookie(SESSION_COOKIE_KEY, str(session_key))
        return res

    if session.total_count == 0:
        fragment = error_modal("商品が選択されていません")
        return DatastarResponse(SSE.patch_elements(fragment))

    order_sessions.pop(session_key)
    res = await _place_order(session)
    res.delete_cookie(SESSION_COOKIE_KEY)
    return res


def _create_new_session() -> UUID:
    session_key = uuid4()
    order_sessions[session_key] = OrderSession(items={}, counted_products={})
    return session_key


async def _place_order(session: SessionDeps) -> Response:
    product_ids = [item.product_id for item in session.items.values()]
    order_id = await OrderedItemTable.issue(product_ids)
    # TODO: add a branch for out of stock error
    await OrderTable.insert(order_id)
    fragment = issued_modal(order_id, session)
    return DatastarResponse(SSE.patch_elements(fragment))


@router.post("/register/items")
async def add_session_item(session: SessionDeps, product_id: int) -> Response:
    if (product := await ProductTable.by_product_id(product_id)) is None:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")

    session.add(product)
    fragment = order_session(session)
    return DatastarResponse(SSE.patch_elements(fragment))


@router.delete("/register/items/{item_id}")
async def delete_session_item(session: SessionDeps, item_id: UUID):
    session.delete(item_id)
    fragment = order_session(session)
    return DatastarResponse(SSE.patch_elements(fragment))


@router.delete("/register/items")
async def clear_session_items(session: SessionDeps) -> Response:
    session.clear()
    fragment = order_session(session)
    return DatastarResponse(SSE.patch_elements(fragment))


# TODO: add proper path operation for order deferral
# # TODO: Store this data in database
# deferred_order_sessions: dict[int, OrderSession] = {}
#
#
# @router.post("/register/deferred")
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
