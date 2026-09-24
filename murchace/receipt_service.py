"""Receipt service: builds ReceiptData from an order session and enqueues printing."""

from typing import Annotated

from fastapi import Depends, Request

from .env import RECEIPT_LOGO_PATH, RECEIPT_STORE_ADDRESS, RECEIPT_STORE_NAME
from .printer import ReceiptData, ReceiptItem
from .printer_queue import ReceiptPrinterQueue


def get_printer_queue(request: Request) -> ReceiptPrinterQueue:
    """FastAPI dependency that returns the app-level :class:`ReceiptPrinterQueue`."""
    return request.app.state.printer_queue


PrinterQueueDeps = Annotated[ReceiptPrinterQueue, Depends(get_printer_queue)]


def build_receipt_data(
    order_id: int,
    items: list,
    *,
    store_name: str = RECEIPT_STORE_NAME,
    store_address: str = RECEIPT_STORE_ADDRESS,
    logo_path: str = RECEIPT_LOGO_PATH,
) -> ReceiptData:
    """Construct a :class:`ReceiptData` from an order session."""
    receipt_items = [
        ReceiptItem(
            name=item["name"],
            count=item["count"],
            price=item["price"],
        )
        for item in items
    ]
    total_count = sum((item["count"] for item in items), 0)
    total_price = sum((item["price"] for item in items), 0)
    assert isinstance(total_count, int) and isinstance(total_price, int)
    return ReceiptData(
        order_id=order_id,
        items=receipt_items,
        total_count=total_count,
        total_price=total_price,
        store_name=store_name,
        store_address=store_address,
        logo_path=logo_path,
    )
