from sqlalchemy import orm as sa_orm


def _colname(attr: sa_orm.Mapped) -> str:
    """
    Returns a fully resolved column name.

    ```
    assert _colname(sqlmodel.col(Product.product_id)) == "products.product_id"
    ```
    """
    return attr.label(None).__str__()
