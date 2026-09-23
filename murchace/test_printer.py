import asyncio
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from murchace.printer import (
    FS_AND,
    FS_C_SJIS,
    JapaneseNetworkPrinter,
    ReceiptData,
    ReceiptItem,
    format_and_print_receipt,
    get_display_width,
    pad_line,
)
from murchace.printer_queue import ReceiptPrinterQueue


def test_get_display_width():
    assert get_display_width("abc") == 3
    assert get_display_width("日本語") == 6
    assert get_display_width("ラーメン 1杯") == 12


def test_pad_line():
    line = pad_line("おにぎり", "100円 x 2", total_width=30)
    # "おにぎり" = 8 chars display width
    # "100円 x 2" = 9 chars display width
    # total = 30 -> 13 spaces
    assert get_display_width(line) == 30
    assert line.startswith("おにぎり")
    assert line.endswith("100円 x 2")


def test_japanese_network_printer_kanji_methods():
    printer = JapaneseNetworkPrinter(host="127.0.0.1")
    printer._raw = MagicMock()

    printer.enable_kanji()
    assert printer._raw.call_args_list[0][0][0] == FS_AND
    assert printer._raw.call_args_list[1][0][0] == FS_C_SJIS

    printer.text_ja("テスト注文")
    # Last call should be CP932 encoded bytes
    assert printer._raw.call_args_list[-1][0][0] == "テスト注文".encode("cp932")


def test_format_and_print_receipt():
    printer = MagicMock(spec=JapaneseNetworkPrinter)
    receipt = ReceiptData(
        order_id=42,
        items=[
            ReceiptItem(name="焼きそば", count=2, unit_price_str="¥500"),
            ReceiptItem(name="コーラ", count=1, unit_price_str="¥200"),
        ],
        total_count=3,
        total_price_str="¥1,200",
        store_name="テスト店舗",
        ordered_at=datetime(2026, 9, 23, 12, 0, 0, tzinfo=UTC),
    )

    format_and_print_receipt(printer, receipt, paper_width=40)

    # Verify key steps were called
    printer.hw.assert_called_with("INIT")
    assert printer.set.called
    assert printer.text_ja.called
    printer.cut.assert_called_once()


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_printer_queue_serialization():
    queue = ReceiptPrinterQueue(host="192.168.1.100", port=9100)

    printed_orders = []
    # Mock _print_job to simulate print latency and record order
    async def fake_worker_job(receipt: ReceiptData):
        await asyncio.sleep(0.01)
        printed_orders.append(receipt.order_id)

    with patch.object(queue, "_print_job", side_effect=lambda r: printed_orders.append(r.order_id)):
        queue.start()

        # Enqueue 5 orders concurrently
        for i in range(1, 6):
            queue.enqueue(
                ReceiptData(
                    order_id=i,
                    items=[],
                    total_count=1,
                    total_price_str="¥100",
                )
            )

        # Wait until all jobs are processed
        while len(printed_orders) < 5:
            await asyncio.sleep(0.02)

        await queue.stop()

    assert printed_orders == [1, 2, 3, 4, 5]


def test_printer_queue_skips_when_host_unconfigured():
    queue = ReceiptPrinterQueue(host="")
    receipt = ReceiptData(
        order_id=1,
        items=[],
        total_count=1,
        total_price_str="¥100",
    )
    assert queue.enqueue(receipt) is False
    assert queue.queue.empty()
