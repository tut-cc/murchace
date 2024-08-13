from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .db import (
    PlacedOrderTable,
    PlacementStatusTable,
    ProductTable,
    startup_and_shutdown_db,
)
from .env import DEBUG
from .routers import order, placements
from .templates import templates


# https://stackoverflow.com/a/65270864
# https://fastapi.tiangolo.com/advanced/events/
@asynccontextmanager
async def lifespan(_: FastAPI):
    startup_db, shutdown_db = startup_and_shutdown_db
    await startup_db()
    yield
    await shutdown_db()


app = FastAPI(debug=DEBUG, lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(order.router)
app.include_router(placements.router)


@app.get("/", response_class=HTMLResponse)
async def get_root(request: Request):
    return templates.TemplateResponse(request, "index.html")


if DEBUG:

    @app.get("/test")
    async def test():
        return {
            "product_table": await ProductTable.select_all(),
            "order_sessions": order.order_sessions,
            "placed_order_table": await PlacedOrderTable.select_all(),
            "placement_status_table": await PlacementStatusTable.select_all(),
        }

    @app.get("/test/placed_order_sessions/{placement_id}", response_class=HTMLResponse)
    async def test_placed_order_sessions(request: Request, placement_id: int):
        order_items = await PlacedOrderTable.by_placement_id(placement_id)
        # NOTE: this is a performance nightmare; should use a proper SQL stmt
        idx_item_pairs = [
            (idx, await ProductTable.by_product_id(item.product_id))
            for idx, item in enumerate(order_items)
            if item is not None
        ]
        return templates.TemplateResponse(
            "components/order-session.html",
            {
                "request": request,
                "session_id": placement_id,
                "idx_item_pairs": idx_item_pairs,
            },
        )
