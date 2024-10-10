from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse

from .. import templates
from ..store import Product, ProductTable, delete_product

router = APIRouter()


@router.get("/products", response_class=HTMLResponse)
async def get_products(request: Request):
    products = await ProductTable.select_all()
    return HTMLResponse(templates.products.page(request, products))


@router.post("/products", response_class=Response)
async def new_product(
    product_id: Annotated[int, Form()],
    name: Annotated[str, Form(max_length=40)],
    filename: Annotated[str, Form(max_length=100)],
    price: Annotated[int, Form()],
    no_stock: Annotated[int | None, Form()] = None,
):
    new_product = Product(
        product_id=product_id,
        name=name,
        filename=filename,
        price=price,
        no_stock=no_stock,
    )
    maybe_product = await ProductTable.insert(new_product)

    # TODO: report back that the operation has been completed successfully or
    # failed in the process depending on the value of `maybe_product`
    _ = maybe_product
    # if (product := maybe_product) is None:
    #     detail = f"Product {product_id} not updated"
    #     raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    #
    # # return HTMLResponse(templates.products.card(product))

    return Response(headers={"hx-refresh": "true"})


@router.post("/products/{product_id}", response_class=HTMLResponse)
async def update_product(
    product_id: int,
    new_product_id: Annotated[int, Form()],
    name: Annotated[str, Form(max_length=40)],
    filename: Annotated[str, Form(max_length=100)],
    price: Annotated[int, Form()],
    no_stock: Annotated[int | None, Form()] = None,
):
    new_product = Product(
        product_id=new_product_id,
        name=name,
        filename=filename,
        price=price,
        no_stock=no_stock,
    )

    maybe_product = await ProductTable.update(product_id, new_product)

    # TODO: report back that the operation has been completed successfully or
    # failed in the process depending on the value of `maybe_product`
    _ = maybe_product
    # if (product := maybe_product) is None:
    #     detail = f"Product {product_id} not updated"
    #     raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    #
    # # return HTMLResponse(templates.products.card(product))

    return Response(headers={"hx-refresh": "true"})


@router.delete("/products/{product_id}", response_class=Response)
async def delete(product_id: int):
    await delete_product(product_id)
    return Response(headers={"hx-refresh": "true"})


@router.get("/products/{product_id}/editor", response_class=HTMLResponse)
async def get_product_editor(request: Request, product_id: int):
    maybe_product = await ProductTable.by_product_id(product_id)

    if (product := maybe_product) is None:
        detail = f"Product {product_id} not found"
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    return HTMLResponse(templates.products.editor(request, product))


@router.get("/product-editor", response_class=HTMLResponse)
async def get_empty_product_editor(request: Request):
    return HTMLResponse(templates.products.empty_editor(request))
