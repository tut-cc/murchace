from fastapi import APIRouter, Request

from ..store import SortOrderedProductsBy as SortBy
from ..store import load_ordered_products

# from .. import templates

router = APIRouter()


@router.get("/ordered-products")
async def get_ordered_products(_: Request, sort_by: SortBy = SortBy.PRODUCT_ID):
    ordered_products = await load_ordered_products(sort_by)
    # NOTE: Actually, we might not need this template and instead modify and use templates.placements.
    # templates.ordered_products(request, ordered_products)
    return ordered_products
