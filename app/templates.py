import os
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Protocol, Optional

import jinja2
from fastapi import Request
from fastapi.datastructures import URL
from jinja2.ext import debug as debug_ext

from .env import DEBUG
from .store import Product, placed_item_t, placement_t
from .store.product import OrderSession

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


def load_macro(template: jinja2.Template, macro_name: str) -> jinja2.runtime.Macro:
    macro = getattr(template.module, macro_name)
    if not isinstance(macro, jinja2.runtime.Macro):
        raise Exception(f"{macro} is not a jinja2.runtime.Macro instance")
    return macro


def hyphen_path_to_underscore_stem(path: str | os.PathLike[str]) -> str:
    return Path(path).stem.replace("-", "_")


class _MacroArgHints[**P](Protocol):
    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> None: ...


class _RenderMacroWithRequest[**P](Protocol):
    def __call__(self, request: Request, *args: P.args, **kwargs: P.kwargs) -> str: ...


def macro_template[**P](
    name: str, macro_name: str | None = None
) -> Callable[[_MacroArgHints[P]], _RenderMacroWithRequest[P]]:
    if macro_name is None:
        macro_name = hyphen_path_to_underscore_stem(name)

    def type_signature(fn: _MacroArgHints[P]) -> _RenderMacroWithRequest[P]:
        @wraps(fn)
        def with_request(request, *args: P.args, **kwargs: P.kwargs) -> str:
            template = env.get_template(name, globals={"request": request, **globals})
            return load_macro(template, macro_name)(*args, **kwargs)

        return with_request

    return type_signature


@macro_template("layout.html")
def layout(
    title: str = "murchace", head: str = "", caller: Callable[[], str] = lambda: ""
): ...


@macro_template("index.html")
def index(): ...


class products:  # namespace
    @macro_template("products.html")
    @staticmethod
    def page(products: list[Product]): ...

    @macro_template("products.html", "editor")
    @staticmethod
    def editor(product: Product): ...

    @macro_template("products.html", "empty_editor")
    @staticmethod
    def empty_editor(): ...


class order:  # namespace
    @macro_template("order.html")
    @staticmethod
    def page(products: list[Product], session: OrderSession): ...

    @macro_template("order.html", "order_session")
    @staticmethod
    def session(session: OrderSession): ...


class placed_items_incoming:  # namespace
    @macro_template("placed-items-incoming.html")
    @staticmethod
    def page(placed_items: list[placed_item_t]): ...

    @macro_template("placed-items-incoming.html", "component")
    @staticmethod
    def component(placed_items: list[placed_item_t]): ...


class incoming_placements:  # namespace
    @macro_template("incoming-placements.html")
    @staticmethod
    def page(placements: list[placement_t]): ...

    @macro_template("incoming-placements.html", "component")
    @staticmethod
    def component(placements: list[placement_t]): ...


class resolved_placements:  # namespace
    @macro_template("resolved-placements.html")
    @staticmethod
    def page(placements: list[placement_t]): ...

    @macro_template("resolved-placements.html", "completed")
    @staticmethod
    def completed(placement: placement_t): ...

    @macro_template("resolved-placements.html", "canceled")
    @staticmethod
    def canceled(placement: placement_t): ...


@macro_template("hx-post.html")
def hx_post(path: str): ...


@macro_template("stat.html")
def stat(
    total_sales_all_time: int,
    total_sales_today: int,
    total_items_all_time: int,
    total_items_today: int,
    sales_summary_list: list[dict[str, Any]],
    average_service_time_all: str,
    average_service_time_recent: str,
): ...


@macro_template("wait-estimates.html")
def wait_estimates(): ...


class components:  # namespace
    @macro_template("components/order-confirm.html")
    @staticmethod
    def order_confirm(session: OrderSession, error_status: Optional[str]): ...

    @macro_template("components/order-issued.html")
    @staticmethod
    def order_issued(
        placement_id: Optional[int], session: OrderSession, error_status: Optional[str]
    ): ...
