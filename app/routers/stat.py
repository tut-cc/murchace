from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from .. import templates
from ..store import (
    PlacedItemTable,
    ProductTable,
    PlacementTable,
)

import sqlite3
import csv
import os

from datetime import datetime, timedelta
from typing import Tuple, List, Dict, Any
import statistics

router = APIRouter()

DATABASE_URL = os.path.abspath("./db/app.db")
CSV_OUTPUT_PATH = os.path.abspath("./static/stat.csv")


def write_csv():
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    query = """
    SELECT 
        placements.placement_id, 
        placements.placed_at, 
        placements.completed_at, 
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

    cursor.execute(query)
    csv_file_path = os.path.abspath(CSV_OUTPUT_PATH)
    with open(csv_file_path, "w", newline="") as csv_file:
        csv_writer = csv.writer(csv_file)
        headers = [
            i[0]
            for i in cursor.description
            if i[0] not in ("product_id", "canceled_at")
        ]
        csv_writer.writerow(headers)
        for row in cursor.fetchall():
            filtered_row = [
                value
                for index, value in enumerate(row)
                if cursor.description[index][0] not in ("product_id", "canceled_at")
            ]
            csv_writer.writerow(filtered_row)
    conn.close()


async def compute_total_sales() -> Tuple[int, int, List[Dict[str, Any]]]:
    product_table = await ProductTable.select_all()
    placed_item_table = await PlacedItemTable.select_all()
    placement_table = await PlacementTable.select_all()

    product_price_map = {product.product_id: product for product in product_table}
    total_sales_all_time = 0
    total_sales_today = 0
    total_items_all_time = 0
    total_items_today = 0
    sales_summary = []

    today = datetime.utcnow().date()
    print(today)

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

            sales_summary.append(
                {
                    "name": product_info.name,
                    "filename": product_info.filename,
                    "count": 1,
                    "total_sales": product_info.price,
                    "no_stock": product_info.no_stock,
                }
            )

            total_sales_all_time += product_info.price
            total_items_all_time += 1

            placed_date = placement.placed_at.date()
            if placed_date == today:
                total_sales_today += product_info.price
                total_items_today += 1

    sales_summary_aggregated = {}
    for sale in sales_summary:
        product_name = sale["name"]
        if product_name not in sales_summary_aggregated:
            sales_summary_aggregated[product_name] = sale
        else:
            sales_summary_aggregated[product_name]["count"] += 1
            sales_summary_aggregated[product_name]["total_sales"] += sale["total_sales"]

    sales_summary_list = list(sales_summary_aggregated.values())

    return total_sales_all_time, total_sales_today, total_items_all_time, total_items_today, sales_summary_list


async def compute_average_service_time() -> Tuple[str, str]:
    placement_table = await PlacementTable.select_all()

    all_service_times = []
    recent_service_times = []
    thirty_minutes_ago = datetime.now() - timedelta(minutes=30)

    for placement in placement_table:
        if placement.completed_at is not None:
            placed_at = datetime.fromisoformat(str(placement.placed_at))
            completed_at = datetime.fromisoformat(str(placement.completed_at))

            time_diff = (completed_at - placed_at).total_seconds()
            all_service_times.append(time_diff)

            if completed_at >= thirty_minutes_ago:
                recent_service_times.append(time_diff)


    if all_service_times:
        average_service_time_all_seconds = statistics.mean(all_service_times)
        average_all_minutes = int(average_service_time_all_seconds // 60)
        average_all_seconds = int(average_service_time_all_seconds % 60)
        average_service_time_all = f"{average_all_minutes} 分 {average_all_seconds} 秒"
    else:
        average_service_time_all = "0 分 0 秒"


    if recent_service_times:
        average_service_time_recent_seconds = statistics.mean(recent_service_times)
        average_recent_minutes = int(average_service_time_recent_seconds // 60)
        average_recent_seconds = int(average_service_time_recent_seconds % 60)
        average_service_time_recent = (
            f"{average_recent_minutes} 分 {average_recent_seconds} 秒"
        )
    else:
        average_service_time_recent = "0 分 0 秒"

    return average_service_time_all, average_service_time_recent


@router.get("/stat", response_class=HTMLResponse)
async def get_stat(request: Request):
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


@router.post("/stat/generate-csv", response_class=HTMLResponse)
async def generate_csv():
    write_csv()
    return "出力完了"
