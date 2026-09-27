import pytest

from ..store import startup_and_shutdown_db
from .register import (
    SESSION_COOKIE_KEY,
    OrderSession,
    add_session_item,
    clear_session_items,
    create_new_session_or_place_order,
    delete_session_item,
    encode_session,
    restore_session,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def init_db(anyio_backend):
    startup_db, shutdown_db = startup_and_shutdown_db
    await startup_db()
    yield
    await shutdown_db()


def test_order_session_empty():
    session = OrderSession(items={}, counted_products={})
    assert session.total_count == 0
    assert session.total_price == 0
    encoded = encode_session(session)
    assert isinstance(encoded, str)


@pytest.mark.anyio
async def test_restore_session_invalid():
    assert await restore_session(None) is None
    assert await restore_session("invalid-base64!!!") is None
    assert await restore_session("W10=") is not None  # base64 for "[]"


@pytest.mark.anyio
async def test_cookie_session_flow(init_db):
    """End-to-end test of the cookie session lifecycle.

    Verifies that items can be added, deleted, and ordered, with the session
    persisting correctly through the cookie across simulated 'requests'.
    """
    # 1. Initial creation (no cookie)
    res = await create_new_session_or_place_order(order_session=None)
    cookie_header = res.headers.get("set-cookie")
    assert cookie_header is not None
    assert f"{SESSION_COOKIE_KEY}=" in cookie_header

    # Extract cookie value
    raw_cookie = cookie_header.split(";")[0].split("=", 1)[1]
    session = await restore_session(raw_cookie)
    assert session is not None
    assert session.total_count == 0

    # 2. Add an item (product_id=1)
    res_add1 = await add_session_item(session, product_id=1)
    cookie_header_add1 = res_add1.headers.get("set-cookie")
    assert cookie_header_add1 is not None
    raw_cookie_add1 = cookie_header_add1.split(";")[0].split("=", 1)[1]

    # Restore on a "different worker" (stateless, from cookie only)
    worker2_session = await restore_session(raw_cookie_add1)
    assert worker2_session is not None
    assert worker2_session.total_count == 1
    assert 1 in worker2_session.counted_products
    item_id = next(iter(worker2_session.items.keys()))

    # 3. Add another item (product_id=2)
    res_add2 = await add_session_item(worker2_session, product_id=2)
    cookie_header_add2 = res_add2.headers.get("set-cookie")
    assert cookie_header_add2 is not None
    raw_cookie_add2 = cookie_header_add2.split(";")[0].split("=", 1)[1]

    # Restore on "worker 3"
    worker3_session = await restore_session(raw_cookie_add2)
    assert worker3_session is not None
    assert worker3_session.total_count == 2

    # 4. Delete first item
    res_del = await delete_session_item(worker3_session, item_id=item_id)
    cookie_header_del = res_del.headers.get("set-cookie")
    assert cookie_header_del is not None
    raw_cookie_del = cookie_header_del.split(";")[0].split("=", 1)[1]

    worker4_session = await restore_session(raw_cookie_del)
    assert worker4_session is not None
    assert worker4_session.total_count == 1
    assert item_id not in worker4_session.items

    # 5. Clear all items
    res_clear = await clear_session_items(worker4_session)
    cookie_header_clear = res_clear.headers.get("set-cookie")
    assert cookie_header_clear is not None
    raw_cookie_clear = cookie_header_clear.split(";")[0].split("=", 1)[1]

    worker5_session = await restore_session(raw_cookie_clear)
    assert worker5_session is not None
    assert worker5_session.total_count == 0

    # 6. Place order when session has items
    await add_session_item(worker5_session, product_id=1)
    res_order = await create_new_session_or_place_order(
        order_session=encode_session(worker5_session)
    )
    # Cookie should be deleted
    set_cookie_headers = (
        res_order.headers.get_list("set-cookie")
        if hasattr(res_order.headers, "get_list")
        else [res_order.headers.get("set-cookie", "")]
    )
    assert any(
        SESSION_COOKIE_KEY in h
        and ("max-age=0" in h.lower() or "expires=" in h.lower())
        for h in set_cookie_headers
    )


@pytest.mark.anyio
async def test_order_session_dep(init_db):
    from fastapi import HTTPException

    from .register import order_session_dep

    with pytest.raises(HTTPException) as exc_info:
        await order_session_dep(order_session=None)
    assert exc_info.value.status_code == 404

    with pytest.raises(HTTPException) as exc_info:
        await order_session_dep(order_session="invalid_session")
    assert exc_info.value.status_code == 404

    session = OrderSession(items={}, counted_products={})
    restored = await order_session_dep(order_session=encode_session(session))
    assert restored.total_count == 0
