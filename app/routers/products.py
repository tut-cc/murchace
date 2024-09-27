from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from .. import templates
from ..store import ProductTable

router = APIRouter()


@router.get("/products", response_class=HTMLResponse)
async def get_products(request: Request):
    products = await ProductTable.select_all()
    return HTMLResponse(templates.products(request, products))


# @router.post("/products/{product_id}", response_class=HTMLResponse)
# async def update_product(request: Request, product_id: int):
#     product = await ProductTable.by_product_id(product_id)
#     return HTMLResponse(templates.components.product(request, product))


@router.get("/products/{product_id}/editor", response_class=HTMLResponse)
async def get_product_editor(request: Request, product_id: int):
    product = await ProductTable.by_product_id(product_id)
    return HTMLResponse(templates.components.product_editor(request, product))
