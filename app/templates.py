from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Concatenate, ParamSpec

import jinja2
from fastapi import Request
from fastapi.datastructures import URL
from jinja2.ext import debug as debug_ext

from .env import DEBUG
from .store import Product

TEMPLATES_DIR = Path("app/templates")


env = jinja2.Environment(
    extensions=[debug_ext] if DEBUG else [],
    undefined=jinja2.StrictUndefined,
    autoescape=True,
    loader=jinja2.FileSystemLoader(TEMPLATES_DIR),
)
globals: dict[str, Any] = {"DEBUG": DEBUG}


@jinja2.pass_context
def _url_for(context: dict[str, Any], name: str, /, **path_params: Any) -> URL:
    request: Request = context["request"]
    return request.url_for(name, **path_params)


env.globals.setdefault("url_for", _url_for)


def load_macro(
    request: Request, name: str, macro_name: str | None = None
) -> jinja2.runtime.Macro:
    """If the `macro_name` is not specified, this method assumes that the input
    template defines the macro named the same as the stem of `name`. Note that
    `name` with hyphen characters will be converted to underscores to follow the
    convetion of common HTML file names.
    """
    template = env.get_template(name, globals={"request": request, **globals})
    if macro_name is None:
        macro_name = Path(name).stem.replace("-", "_")
    macro = getattr(template.module, macro_name)
    if not isinstance(macro, jinja2.runtime.Macro):
        raise Exception(f"{macro} is not a jinja2.runtime.Macro instance")
    return macro


P = ParamSpec("P")


def macro_template(
    name: str,
    macro_name: str | None = None,
) -> Callable[[Callable[P, None]], Callable[Concatenate[Request, P], str]]:
    def type_signature(_: Callable[P, None]) -> Callable[Concatenate[Request, P], str]:
        def with_request(request: Request, *args: P.args, **kwargs: P.kwargs) -> str:
            return load_macro(request, name, macro_name)(*args, **kwargs)

        return with_request

    return type_signature


@macro_template("index.html")
def index(): ...


@macro_template("products.html")
def products(products: list[Product]): ...


@macro_template("orders.html")
def orders(
    session_id: int,
    products: list[Product],
    order_items: list[Product | None],
    total_price: str,
    placement_status: str = "",
    order_frozen: bool = False,
): ...


@macro_template("placements.html")
def placements(
    placements: list[
        dict[str, int | list[dict[str, int | str]] | str | datetime | None]
    ],
    canceled: bool = False,
    completed: bool = False,
): ...


# namespace
class components:
    @macro_template("components/product-editor.html")
    @staticmethod
    def product_editor(product: Product | None): ...

    @macro_template("components/order-session.html")
    @staticmethod
    def order_session(
        session_id: int,
        order_items: list[Product | None],
        total_price: str,
        placement_status: str = "",
        order_frozen: bool = False,
    ): ...

    @macro_template("components/placements.html")
    @staticmethod
    def placements(
        placements: list[
            dict[str, int | list[dict[str, int | str]] | str | datetime | None]
        ],
        canceled: bool = False,
        completed: bool = False,
    ): ...
