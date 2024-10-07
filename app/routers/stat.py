from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse

from .. import templates
from ..store import (
    PlacedItemTable,
    ProductTable,
    PlacementTable,
    database,
)

import csv
import os

from datetime import datetime, timedelta
from typing import Any, Mapping
import statistics

router = APIRouter()

DATABASE_URL = os.path.abspath("./db/app.db")
CSV_OUTPUT_PATH = os.path.abspath("./static/stat.csv")
GRAPH_OUTPUT_PATH = os.path.abspath("./static/sales.png")


def convert_unixepoch_to_localtime(unixepoch_time):
    local_time = datetime.fromtimestamp(unixepoch_time).astimezone()
    return local_time.strftime("%Y-%m-%d %H:%M:%S")


async def export_placements():
    query = """
    SELECT 
        placements.placement_id, 
        unixepoch(placements.placed_at) AS placed_at,
        unixepoch(placements.completed_at) AS completed_at, 
        placements.canceled_at, 
        placed_items.product_id, 
        products.product_id, 
        products.name, 
        products.price
    FROM
        placements
    INNER JOIN
        placed_items ON placements.placement_id = placed_items.placement_id
    INNER JOIN
        products ON placed_items.product_id = products.product_id
    WHERE 
        placements.canceled_at IS NULL;
    """

    csv_file_path = os.path.abspath(CSV_OUTPUT_PATH)
    with open(csv_file_path, "w", newline="") as csv_file:
        csv_writer = csv.writer(csv_file)

        async_gen = database.iterate(query)
        if (row := await anext(async_gen, None)) is None:
            return

        headers = [
            key for key in dict(row).keys() if key not in ("product_id", "canceled_at")
        ]
        csv_writer.writerow(headers)

        csv_writer.writerow(_filtered_row(row))

        async for row in async_gen:
            csv_writer.writerow(_filtered_row(row))


def _filtered_row(row: Mapping) -> list:
    filtered_row = []
    for column_name, value in dict(row).items():
        if column_name in ("placed_at", "completed_at") and value is not None:
            value = convert_unixepoch_to_localtime(value)
        if column_name not in ("product_id", "canceled_at"):
            filtered_row.append(value)
    return filtered_row


async def compute_total_sales() -> tuple[int, int, int, int, list[dict[str, Any]]]:
    product_table = await ProductTable.select_all()
    placed_item_table = await PlacedItemTable.select_all()
    placement_table = await PlacementTable.select_all()

    product_price_map = {product.product_id: product for product in product_table}
    total_sales_all_time = 0
    total_sales_today = 0
    total_items_all_time = 0
    total_items_today = 0
    sales_summary_aggregated = {}

    today = datetime.today().date()

    for item in placed_item_table:
        product_id = item.product_id
        placement = next(
            (p for p in placement_table if p.placement_id == item.placement_id), None
        )

        if (
            placement
            and placement.canceled_at is None
            and product_id in product_price_map
        ):
            product_info = product_price_map[product_id]

            if product_info.name not in sales_summary_aggregated:
                sales_summary_aggregated[product_info.name] = {
                    "name": product_info.name,
                    "filename": product_info.filename,
                    "count": 1,
                    "total_sales": product_info.price,
                    "no_stock": product_info.no_stock,
                }
            else:
                sales_summary_aggregated[product_info.name]["count"] += 1
                sales_summary_aggregated[product_info.name]["total_sales"] += (
                    product_info.price
                )

            total_sales_all_time += product_info.price
            total_items_all_time += 1

            if placement.completed_at is not None:
                placed_date = (
                    datetime.fromisoformat(str(placement.placed_at))
                    + (datetime.now().astimezone().utcoffset() or timedelta(0))
                ).date()
                if placed_date == today:
                    total_sales_today += product_info.price
                    total_items_today += 1

    sales_summary_list = list(sales_summary_aggregated.values())

    return (
        total_sales_all_time,
        total_sales_today,
        total_items_all_time,
        total_items_today,
        sales_summary_list,
    )


async def compute_average_service_time() -> tuple[str, str]:
    placement_table = await PlacementTable.select_all()

    all_service_times = []
    recent_service_times = []
    now = datetime.now().astimezone()
    offset = now.utcoffset() or timedelta(0)
    thirty_minutes_ago = now - timedelta(minutes=30) - offset

    for placement in placement_table:
        if placement.completed_at is not None:
            placed_at = datetime.fromisoformat(str(placement.placed_at)).astimezone()
            completed_at = datetime.fromisoformat(
                str(placement.completed_at)
            ).astimezone()

            time_diff = (completed_at - placed_at).total_seconds()
            all_service_times.append(time_diff)

            if completed_at >= thirty_minutes_ago:
                recent_service_times.append(time_diff)

    if all_service_times:
        average_service_time_all_seconds = statistics.mean(all_service_times)
        average_all_minutes, average_all_seconds = divmod(
            int(average_service_time_all_seconds), 60
        )
        average_service_time_all = f"{average_all_minutes} 分 {average_all_seconds} 秒"
    else:
        average_service_time_all = "0 分 0 秒"

    if recent_service_times:
        average_service_time_recent_seconds = statistics.mean(recent_service_times)
        average_recent_minutes, average_recent_seconds = divmod(
            int(average_service_time_recent_seconds), 60
        )
        average_service_time_recent = (
            f"{average_recent_minutes} 分 {average_recent_seconds} 秒"
        )
    else:
        average_service_time_recent = "0 分 0 秒"

    return average_service_time_all, average_service_time_recent


async def compute_waiting_orders() -> int:
    placement_table = await PlacementTable.select_all()
    waiting_orders = 0
    for placement in placement_table:
        if placement.completed_at is None and placement.canceled_at is None:
            waiting_orders += 1
    return waiting_orders


@router.get("/stat", response_class=HTMLResponse)
async def get_stat(request: Request):
    await export_placements()
    (
        total_sales_all_time,
        total_sales_today,
        total_items_all_time,
        total_items_today,
        sales_summary_list,
    ) = await compute_total_sales()
    (
        average_service_time_all,
        average_service_time_recent,
    ) = await compute_average_service_time()
    return HTMLResponse(
        templates.stat(
            request,
            total_sales_all_time,
            total_sales_today,
            total_items_all_time,
            total_items_today,
            sales_summary_list,
            average_service_time_all,
            average_service_time_recent,
        )
    )


@router.get("/wait-estimates", response_class=HTMLResponse)
async def get_estimates(request: Request):
    return HTMLResponse(templates.wait_estimates(request))


@router.post("/wait-estimates/service-time", response_class=Response)
async def post_estimates():
    (
        average_service_time_all,
        average_service_time_recent,
    ) = await compute_average_service_time()
    if average_service_time_recent == "0 分 0 秒":
        average_service_time_recent = "待ち時間なし"
    return average_service_time_recent


@router.post("/wait-estimates/waiting-orders", response_class=Response)
async def post_orders():
    waiting_orders = await compute_waiting_orders()
    waiting_orders = str(waiting_orders) + "人"
    return waiting_orders
