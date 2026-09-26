from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from murchace.printer import (
    ESC_R_JAPAN,
    FS_AND,
    FS_C_SJIS,
    JapaneseNetworkPrinter,
    PrinterProtocol,
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
    assert printer._raw.call_args_list[0][0][0] == ESC_R_JAPAN
    assert printer._raw.call_args_list[1][0][0] == FS_AND
    assert printer._raw.call_args_list[2][0][0] == FS_C_SJIS

    printer.text_ja("テスト注文 ¥500")
    # Last call should be CP932 encoded bytes with ¥ replaced by \
    assert printer._raw.call_args_list[-1][0][0] == "テスト注文 \\500".encode("cp932")


def test_format_and_print_receipt():
    printer = MagicMock(spec=PrinterProtocol)
    receipt = ReceiptData(
        order_id=42,
        items=[
            ReceiptItem(name="焼きそば", count=2, unit_price_str="¥500"),
            ReceiptItem(name="コーラ", count=1, unit_price_str="¥200"),
        ],
        total_count=3,
        total_price_str="¥1,200",
        store_name="テスト店舗",
        store_address="東京都渋谷区神南1-2-3",
        ordered_at=datetime(2026, 9, 23, 12, 0, 0, tzinfo=UTC),
    )

    format_and_print_receipt(printer, receipt, paper_width=40)

    # Verify key steps were called
    printer.hw.assert_called_with("INIT")
    assert printer.set.called
    assert printer.text_ja.called
    printer.cut.assert_called_once()

    # Check right alignment was used for datetime
    printer.set.assert_any_call(align="right", bold=False, normal_textsize=True)
    # Check order number printed
    printed_texts = [call[0][0] for call in printer.text_ja.call_args_list]
    assert any("注文番号 #42" in text for text in printed_texts)
    assert any("東京都渋谷区神南1-2-3" in text for text in printed_texts)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_printer_queue_serialization():
    queue = ReceiptPrinterQueue(host="192.168.1.100", port=9100)

    printed_orders = []

    with patch.object(
        queue, "_print_job", side_effect=lambda r: printed_orders.append(r.order_id)
    ):
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

        # Wait until all jobs are processed without busy-waiting
        await queue.queue.join()
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


# ---------------------------------------------------------------------------
# B: Retry logic tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_retry_succeeds_on_second_attempt():
    """_print_with_retry should succeed after one initial failure."""
    from murchace.printer_queue import _RETRY_DELAYS  # noqa: F401

    queue = ReceiptPrinterQueue(host="192.168.1.100", port=9100)
    receipt = ReceiptData(order_id=99, items=[], total_count=1, total_price_str="¥100")

    call_count = 0

    def flaky_print_job(r):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise OSError("Connection refused")

    with (
        patch.object(queue, "_print_job", side_effect=flaky_print_job),
        patch("asyncio.sleep"),  # skip real delays in tests
    ):
        await queue._print_with_retry(receipt)

    assert call_count == 2  # 1 failure + 1 success


@pytest.mark.anyio
async def test_retry_exhausted_logs_error():
    """After all attempts fail, an error is logged and no exception propagates."""
    from murchace.printer_queue import _RETRY_DELAYS

    queue = ReceiptPrinterQueue(host="192.168.1.100", port=9100)
    receipt = ReceiptData(order_id=7, items=[], total_count=1, total_price_str="¥100")
    max_attempts = len(_RETRY_DELAYS) + 1

    with (
        patch.object(queue, "_print_job", side_effect=OSError("unreachable")),
        patch("asyncio.sleep"),
        patch("murchace.printer_queue.logger") as mock_logger,
    ):
        # Should not raise
        await queue._print_with_retry(receipt)

    # Verify error-level log was emitted once at the end
    mock_logger.error.assert_called_once()
    # Per attempt: 1 "Retrying…" warning (attempts 2..N) + 1 "attempt N failed" warning
    # Total: (max_attempts - 1) retrying msgs + max_attempts failure msgs
    expected_warnings = (max_attempts - 1) + max_attempts
    assert mock_logger.warning.call_count == expected_warnings


# ---------------------------------------------------------------------------
# C: Environment-variable wiring tests
# ---------------------------------------------------------------------------


def test_print_job_uses_configured_timeout_and_paper_width():
    """_print_job must pass timeout and paper_width from env to the printer."""
    queue = ReceiptPrinterQueue(
        host="192.168.1.100",
        port=9100,
        timeout=5,
        paper_width=48,
    )
    receipt = ReceiptData(order_id=3, items=[], total_count=0, total_price_str="¥0")

    fake_printer = MagicMock()

    with (
        patch(
            "murchace.printer_queue.JapaneseNetworkPrinter",
            return_value=fake_printer,
        ) as mock_cls,
        patch("murchace.printer_queue.format_and_print_receipt") as mock_fmt,
    ):
        queue._print_job(receipt)

    # timeout must come from queue.timeout, not hard-coded
    mock_cls.assert_called_once_with(host="192.168.1.100", port=9100, timeout=5)
    # paper_width must be forwarded to format_and_print_receipt
    mock_fmt.assert_called_once_with(fake_printer, receipt, paper_width=48)
