"""Receipt service: builds ReceiptData from an order session and enqueues printing."""

from datetime import datetime
from typing import Annotated, Protocol

from fastapi import Depends, Request

from .env import RECEIPT_LOGO_PATH, RECEIPT_STORE_ADDRESS, RECEIPT_STORE_NAME
from .printer import ReceiptData, ReceiptItem
from .printer_queue import ReceiptPrinterQueue


class _OrderSessionLike(Protocol):
    """Structural protocol – avoids circular import with routers.register."""

    @property
    def counted_products(self) -> dict: ...

    @property
    def total_count(self) -> int: ...

    def total_price_str(self) -> str: ...


def get_printer_queue(request: Request) -> ReceiptPrinterQueue:
    """FastAPI dependency that returns the app-level :class:`ReceiptPrinterQueue`."""
    return request.app.state.printer_queue


PrinterQueueDeps = Annotated[ReceiptPrinterQueue, Depends(get_printer_queue)]


def build_receipt_data(
    order_id: int,
    session: _OrderSessionLike,
    *,
    ordered_at: datetime | None = None,
    store_name: str = RECEIPT_STORE_NAME,
    store_address: str = RECEIPT_STORE_ADDRESS,
    logo_path: str = RECEIPT_LOGO_PATH,
) -> ReceiptData:
    """Construct a :class:`ReceiptData` from an order session.

    *ordered_at* should be the timestamp returned by :meth:`OrderTable.insert`
    so the receipt shows the exact DB-recorded time rather than the print time.
    """
    items = [
        ReceiptItem(
            name=cp.name,
            count=cp.count,
            unit_price_str=cp.price,
        )
        for cp in session.counted_products.values()
    ]
    return ReceiptData(
        order_id=order_id,
        items=items,
        total_count=session.total_count,
        total_price_str=session.total_price_str(),
        ordered_at=ordered_at,
        store_name=store_name,
        store_address=store_address,
        logo_path=logo_path,
    )
