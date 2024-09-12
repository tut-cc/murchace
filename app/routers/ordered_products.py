from fastapi import APIRouter, Request

from ..db import SortOrderedProductsBy as SortBy
from ..db import select_ordered_products
from ..templates import templates

router = APIRouter()


@router.get("/ordered_products")
async def get_ordered_products(request: Request, sort_by: SortBy = SortBy.PRODUCT_ID):
    print(sort_by)
    return await select_ordered_products(sort_by, False, False)
    # return templates.TemplateResponse(
    #     request, "ordered_products.html", {"ordered_products": ordered_products}
    # )
