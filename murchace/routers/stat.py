import csv
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

import sqlalchemy
import sqlalchemy.sql.expression as sa_exp
from datastar_py import attribute_generator as data
from datastar_py.fastapi import DatastarResponse
from datastar_py.sse import ServerSentEventGenerator as SSE
from fastapi import APIRouter, Header, Request
from fastapi.responses import HTMLResponse
from htpy import (
    Element,
    HTMLElement,
    a,
    div,
    h2,
    header,
    img,
    li,
    main,
    p,
    span,
    table,
    tbody,
    td,
    th,
    thead,
    tr,
    ul,
)
from sqlalchemy.sql.functions import func as sa_func

from ..components import clock, page_layout
from ..store import Order, OrderedItem, Product, database, unixepoch

router = APIRouter()

CSV_OUTPUT_PATH = Path("./static/stat.csv")
GRAPH_OUTPUT_PATH = Path("./static/sales.png")


@dataclass
class Stat:
    @dataclass
    class SalesSummary:
        product_id: int
        name: str
        filename: str
        price: str
        count: int
        count_today: int
        total_sales: str
        total_sales_today: str
        no_stock: int | None

    total_sales_all_time: str
    total_sales_today: str
    total_items_all_time: int
    total_items_today: int
    sales_summary_list: list[SalesSummary]
    avg_service_time_all: str
    avg_service_time_recent: str


def page_stat(req: Request, stat: Stat) -> HTMLElement:
    inner_header = (
        header(
            class_="sticky z-10 inset-0 w-full px-16 py-3 flex gap-3 border-b border-gray-500 bg-white text-2xl"
        )[
            ul(class_="grow flex flex-row gap-3")[
                li(class_="grow")[
                    a(
                        href="/",
                        class_="cursor-pointer px-2 py-1 bg-gray-300 rounded-sm",
                    )["ホーム"]
                ],
                li(class_="hidden sm:block")[
                    a(
                        href="/static/stat.csv",
                        class_="px-2 py-1 text-white bg-blue-600 rounded-lg",
                    )["売上データの取得"]
                ],
                li(class_="hidden sm:block")[clock],
            ]
        ],
    )

    def summary_cell(desc: str, text: str | int):
        return div(class_="p-2")[
            h2(class_="text-2xl")[desc], p(class_="text-4xl text-center")[text]
        ]

    inner_main = main(class_="py-2 px-16")[
        div(
            class_="lg:grid lg:grid-cols-3 border-2 border-b border-gray-300 rounded-t-lg divide-y-2 lg:divide-x-2 lg:divide-y-0 divide-gray-300"
        )[
            summary_cell("売上", stat.total_sales_all_time),
            summary_cell("今日の売上", stat.total_sales_today),
            summary_cell("平均提供時間", stat.avg_service_time_all),
        ],
        div(
            class_="lg:grid lg:grid-cols-3 border-2 border-t border-gray-300 rounded-b-lg divide-y-2 lg:divide-x-2 lg:divide-y-0 divide-gray-300"
        )[
            summary_cell("売上点数", stat.total_items_all_time),
            summary_cell("今日の売上点数", stat.total_items_today),
            summary_cell("予測待ち時間", stat.avg_service_time_recent),
        ],
        div(class_="flex flex-col gap-y-2")[
            h2(class_="p-2 text-2xl")["商品毎売上情報"], _stat_table(stat)
        ],
    ]
    return page_layout(req, [inner_header, inner_main], "統計 - murchace")


def _stat_table(stat: Stat) -> Element:
    return table[
        thead[
            tr(class_="text-xl")[
                th(class_="border border-b-2 border-gray-300")["画像"],
                th(class_="border border-b-2 border-gray-300 text-left px-2")["商品名"],
                th(class_="border border-b-2 border-gray-300")["価格"],
                th(class_="border border-b-2 border-gray-300")["個数"],
                th(class_="border border-b-2 border-gray-300")["今日の個数"],
                th(class_="border border-b-2 border-gray-300")["売上"],
                th(class_="border border-b-2 border-gray-300")["今日の売上"],
                th(class_="border border-b-2 border-gray-300")["在庫（未実装）"],
            ]
        ],
        tbody[
            [
                tr[
                    td(class_="border border-gray-300")[
                        img(
                            src=f"/static/{sale.filename}",
                            alt=sale.name,
                            class_="mx-auto w-16 h-auto aspect-square",
                        )
                    ],
                    td(class_="border border-gray-300 px-2")[sale.name],
                    td(class_="border border-gray-300 text-center")[sale.price],
                    td(class_="border border-gray-300 text-center")[sale.count],
                    td(class_="border border-gray-300 text-center")[sale.count_today],
                    td(class_="border border-gray-300 text-center")[sale.total_sales],
                    td(class_="border border-gray-300 text-center")[
                        sale.total_sales_today
                    ],
                    td(class_="border border-gray-300 text-center")[
                        sale.no_stock if sale.no_stock is not None else "N/A"
                    ],
                ]
                for sale in stat.sales_summary_list
            ]
        ],
    ]


def page_wait_estimate(req: Request) -> HTMLElement:
    inner_header = header(
        data.on_interval("@get('/wait-estimates')").duration("5s", leading=True),
        class_="sticky z-10 inset-0 w-full px-16 py-3 border-b border-gray-500 bg-white text-2xl",
    )[
        ul(class_="flex flex-row")[
            li(class_="grow")[
                a(href="/", class_="cursor-pointer px-2 rounded-sm bg-gray-300")[
                    "ホーム"
                ]
            ],
            li(class_="flex flex-row")[span(class_="mr-1")["現在時刻:"], clock],
        ]
    ]
    inner_main = main(id="wait-estimate")
    return page_layout(req, [inner_header, inner_main], "予測待ち時間 - murchace")


def wait_estimate_component(estimate: str, waiting_order_count: int) -> Element:
    return main(id="wait-estimate", class_="px-16 py-3")[
        div(class_="flex-1 p-4 border-2 border-b border-gray-300 rounded-t-lg")[
            h2(class_="text-4xl")["予測待ち時間"],
            p(class_="text-9xl text-center")[estimate],
            p(class_="text-center")["#直近30分の提供時間から算出しています"],
        ],
        div(class_="flex-1 p-4 border-2 border-t border-gray-300 rounded-b-lg")[
            h2(class_="text-4xl")["受取待ち"],
            p(class_="text-9xl text-center")[f"{waiting_order_count}件"],
        ],
    ]


def convert_unixepoch_to_localtime(unixepoch_time: int) -> str:
    local_time = datetime.fromtimestamp(unixepoch_time).astimezone()
    return local_time.strftime("%Y-%m-%d %H:%M:%S")


def zero_if_null[T](v: T | None) -> T | Literal[0]:
    """
    Handles the case where aggregate functions return NULL when no matching rows
    are found
    """
    return v if v is not None else 0


# TODO: Use async operations for writing csv rows so that this function does not block
async def export_orders():
    query = """
    SELECT 
        orders.order_id,
        ordered_items.item_no,
        unixepoch(orders.ordered_at) AS ordered_at,
        unixepoch(orders.completed_at) AS completed_at,
        ordered_items.product_id,
        products.name,
        products.price
    FROM
        orders
    INNER JOIN
        ordered_items ON orders.order_id = ordered_items.order_id
    INNER JOIN
        products ON ordered_items.product_id = products.product_id
    WHERE
        orders.canceled_at IS NULL
    ORDER BY
        orders.order_id ASC;
    """

    with open(CSV_OUTPUT_PATH, "w", newline="") as csv_file:  # noqa: ASYNC230
        csv_writer = csv.writer(csv_file)

        async_gen = database.iterate(query)
        if (row := await anext(async_gen, None)) is None:
            return

        headers = [key for key in dict(row)]
        csv_writer.writerow(headers)

        csv_writer.writerow(_filtered_row(row))
        async for row in async_gen:
            csv_writer.writerow(_filtered_row(row))


def _filtered_row(row: Mapping) -> list:
    filtered_row = []
    for column_name, value in dict(row).items():
        if column_name in ("ordered_at", "completed_at") and value is not None:
            value = convert_unixepoch_to_localtime(value)
        filtered_row.append(value)
    return filtered_row


_ordered_today = sa_func.date(Order.ordered_at, "localtime") == sa_func.date(
    "now", "localtime"
)
TOTAL_SALES_QUERY: sqlalchemy.Compiled = (
    sa_exp.select(Product.product_id)
    .select_from(sa_exp.join(OrderedItem, Order))
    .join(Product)
    .add_columns(
        sa_func.count(Product.product_id).label("count"),
        sa_func.count(Product.product_id).filter(_ordered_today).label("count_today"),
        Product.name,
        Product.filename,
        Product.price,
        sa_func.sum(Product.price).label("total_sales"),
        sa_func.sum(Product.price).filter(_ordered_today).label("total_sales_today"),
        Product.no_stock,
    )
    .where(Order.canceled_at.is_(None))
    .group_by(Product.product_id)
    .compile(compile_kwargs={"literal_binds": True})
)


class AvgServiceTimeQuery:
    @classmethod
    @lru_cache(1)
    def all_and_recent(cls) -> sqlalchemy.Compiled:
        return (
            sa_exp.select(
                sa_func.avg(cls._service_time_diff).label("all"),
                sa_func.avg(cls._last_30mins).label("recent"),
            )
            .where(Order.completed_at.isnot(None))
            .compile()
        )

    @classmethod
    @lru_cache(1)
    def recent(cls) -> sqlalchemy.Compiled:
        return (
            sa_exp.select(sa_func.avg(cls._last_30mins).label("recent"))
            .where(Order.completed_at.isnot(None))
            .compile()
        )

    _service_time_diff = unixepoch(Order.completed_at) - unixepoch(Order.ordered_at)
    _elapsed_secs = sa_func.unixepoch() - unixepoch(Order.completed_at)
    _last_30mins = sa_exp.case(
        (_elapsed_secs / sa_exp.text("60") < sa_exp.text("30"), _service_time_diff)
    )

    @staticmethod
    def seconds_to_jpn_mmss(secs: int) -> str:
        mm, ss = divmod(secs, 60)
        return f"{mm} 分 {ss} 秒"


async def construct_stat() -> Stat:
    sales_summary_aggregated: dict[int, Stat.SalesSummary] = {}
    total_sales_all_time = 0
    total_sales_today = 0
    total_items_all_time = 0
    total_items_today = 0

    async for row in database.iterate(str(TOTAL_SALES_QUERY)):
        product_id = row["product_id"]
        assert isinstance(product_id, int)

        count, count_today, total_sales, total_sales_today_ = map(
            zero_if_null,
            (
                row["count"],
                row["count_today"],
                row["total_sales"],
                row["total_sales_today"],
            ),
        )

        sales_summary_aggregated[product_id] = Stat.SalesSummary(
            product_id=product_id,
            name=row["name"],
            filename=row["filename"],
            price=Product.to_price_str(row["price"]),
            count=count,
            count_today=count_today,
            total_sales=Product.to_price_str(total_sales),
            total_sales_today=Product.to_price_str(total_sales_today_),
            no_stock=row["no_stock"],
        )

        total_sales_all_time += total_sales
        total_sales_today += total_sales_today_

        total_items_all_time += count
        total_items_today += count_today

    sales_summary_list = list(sales_summary_aggregated.values())

    record = await database.fetch_one(str(AvgServiceTimeQuery.all_and_recent()))
    assert record is not None
    avg_service_time_all, avg_service_time_recent = (
        AvgServiceTimeQuery.seconds_to_jpn_mmss(int(zero_if_null(record[0]))),
        AvgServiceTimeQuery.seconds_to_jpn_mmss(int(zero_if_null(record[1]))),
    )

    return Stat(
        total_sales_all_time=Product.to_price_str(total_sales_all_time),
        total_sales_today=Product.to_price_str(total_sales_today),
        total_items_all_time=total_items_all_time,
        total_items_today=total_items_today,
        sales_summary_list=sales_summary_list,
        avg_service_time_all=avg_service_time_all,
        avg_service_time_recent=avg_service_time_recent,
    )


@router.get("/stat", response_class=HTMLResponse)
async def get_stat(request: Request):
    await export_orders()
    return HTMLResponse(page_stat(request, await construct_stat()))


WAITING_ORDER_COUNT_QUERY: sqlalchemy.Compiled = (
    sa_exp.select(sa_func.count(Order.order_id))
    .where(Order.completed_at.is_(None) & Order.canceled_at.is_(None))
    .compile()
)


@router.get("/wait-estimates", response_class=HTMLResponse)
async def get_estimates(
    request: Request, datastar_request: Annotated[str | None, Header()] = None
):
    if datastar_request != "true":
        return HTMLResponse(page_wait_estimate(request))

    async with database.transaction():
        estimate_record = await database.fetch_one(str(AvgServiceTimeQuery.recent()))
        waiting_order_count = await database.fetch_val(str(WAITING_ORDER_COUNT_QUERY))

    assert estimate_record is not None
    estimate = int(zero_if_null(estimate_record[0]))

    if estimate == 0:
        estimate_str = "待ち時間なし"
    else:
        estimate_str = AvgServiceTimeQuery.seconds_to_jpn_mmss(estimate)

    fragment = wait_estimate_component(estimate_str, waiting_order_count)
    return DatastarResponse(SSE.patch_elements(fragment))
