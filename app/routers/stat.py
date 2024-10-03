from fastapi import APIRouter , HTTPException, Request, status
from fastapi.responses import HTMLResponse

from .. import templates

import sqlite3
import csv
import os

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


@router.get("/stat", response_class=HTMLResponse)
async def get_stat(request: Request):
    return HTMLResponse(templates.stat(request))


@router.post("/stat/generate-csv", response_class=HTMLResponse)
async def generate_csv():
    write_csv()
    return "出力完了"
