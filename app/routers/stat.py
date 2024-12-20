import csv
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal, Mapping

import sqlalchemy
import sqlmodel
from fastapi import APIRouter, Header, Request
from fastapi.responses import HTMLResponse
from sqlmodel import col

from ..templates import macro_template
from ..store import OrderedItem, Order, Product, database, unixepoch

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


@macro_template("stat.html")
def tmp_stat(stat: Stat): ...


@macro_template("wait-estimate.html")
def tmp_wait_estimate_page(estimate: str, waiting_order_count: int): ...


@macro_template("wait-estimate.html", "component")
def tmp_wait_estimate_component(estimate: str, waiting_order_count: int): ...


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
        placements.placement_id,
        placed_items.item_no,
        unixepoch(placements.placed_at) AS placed_at,
        unixepoch(placements.completed_at) AS completed_at,
        placed_items.product_id,
        products.name,
        products.price
    FROM
        placements
    INNER JOIN
        placed_items ON placements.placement_id = placed_items.placement_id
    INNER JOIN
        products ON placed_items.product_id = products.product_id
    WHERE
        placements.canceled_at IS NULL
    ORDER BY
        placements.placement_id ASC;
    """

    with open(CSV_OUTPUT_PATH, "w", newline="") as csv_file:
        csv_writer = csv.writer(csv_file)

        async_gen = database.iterate(query)
        if (row := await anext(async_gen, None)) is None:
            return

        headers = [key for key in dict(row).keys()]
        csv_writer.writerow(headers)

        csv_writer.writerow(_filtered_row(row))
        async for row in async_gen:
            csv_writer.writerow(_filtered_row(row))


def _filtered_row(row: Mapping) -> list:
    filtered_row = []
    for column_name, value in dict(row).items():
        if column_name in ("placed_at", "completed_at") and value is not None:
            value = convert_unixepoch_to_localtime(value)
        filtered_row.append(value)
    return filtered_row


_ordered_today = sqlmodel.func.date(
    col(Order.placed_at), "localtime"
) == sqlmodel.func.date("now", "localtime")
TOTAL_SALES_QUERY: sqlalchemy.Compiled = (
    sqlmodel.select(col(Product.product_id))
    .select_from(sqlmodel.join(OrderedItem, Order))
    .join(Product)
    .add_columns(
        sqlmodel.func.count(col(Product.product_id)).label("count"),
        sqlmodel.func.count(col(Product.product_id))
        .filter(_ordered_today)
        .label("count_today"),
        col(Product.name),
        col(Product.filename),
        col(Product.price),
        sqlmodel.func.sum(col(Product.price)).label("total_sales"),
        sqlmodel.func.sum(col(Product.price))
        .filter(_ordered_today)
        .label("total_sales_today"),
        col(Product.no_stock),
    )
    .where(col(Order.canceled_at).is_(None))
    .group_by(col(Product.product_id))
    .compile(compile_kwargs={"literal_binds": True})
)


class AvgServiceTimeQuery:
    @classmethod
    @lru_cache(1)
    def all_and_recent(cls) -> sqlalchemy.Compiled:
        return (
            sqlmodel.select(
                sqlmodel.func.avg(cls._service_time_diff).label("all"),
                sqlmodel.func.avg(cls._last_30mins).label("recent"),
            )
            .where(col(Order.completed_at).isnot(None))
            .compile()
        )

    @classmethod
    @lru_cache(1)
    def recent(cls) -> sqlalchemy.Compiled:
        return (
            sqlmodel.select(sqlmodel.func.avg(cls._last_30mins).label("recent"))
            .where(col(Order.completed_at).isnot(None))
            .compile()
        )

    _service_time_diff = unixepoch(col(Order.completed_at)) - unixepoch(
        col(Order.placed_at)
    )
    _elapsed_secs = sqlmodel.func.unixepoch() - unixepoch(col(Order.completed_at))
    _last_30mins = sqlmodel.case(
        (_elapsed_secs / sqlmodel.text("60") < sqlmodel.text("30"), _service_time_diff)
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
    return HTMLResponse(tmp_stat(request, await construct_stat()))


WAITING_ORDER_COUNT_QUERY: sqlalchemy.Compiled = (
    sqlmodel.select(sqlmodel.func.count(col(Order.placement_id)))
    .where(col(Order.completed_at).is_(None) & col(Order.canceled_at).is_(None))
    .compile()
)


@router.get("/wait-estimates", response_class=HTMLResponse)
async def get_estimates(
    request: Request, hx_request: Annotated[str | None, Header()] = None
):
    async with database.transaction():
        estimate_record = await database.fetch_one(str(AvgServiceTimeQuery.recent()))
        waiting_order_count = await database.fetch_val(str(WAITING_ORDER_COUNT_QUERY))

    assert estimate_record is not None
    estimate = int(zero_if_null(estimate_record[0]))

    if estimate == 0:
        estimate_str = "待ち時間なし"
    else:
        estimate_str = AvgServiceTimeQuery.seconds_to_jpn_mmss(estimate)

    if hx_request == "true":
        template = tmp_wait_estimate_component
    else:
        template = tmp_wait_estimate_page
    return HTMLResponse(template(request, estimate_str, waiting_order_count))
