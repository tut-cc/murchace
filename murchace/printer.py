import logging
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from escpos.printer import Network

logger = logging.getLogger(__name__)

# ESC/POS Commands for Japanese (Kanji mode)
# ESC R n : Select international character set (8: Japan, maps 0x5C to Yen sign)
# FS & : Select Kanji mode
# FS . : Cancel Kanji mode
# FS C n : Select Kanji code system (0: JIS, 1: Shift_JIS)
ESC_R_JAPAN = b"\x1b\x52\x08"
FS_AND = b"\x1c\x26"
FS_DOT = b"\x1c\x2e"
FS_C_SJIS = b"\x1c\x43\x01"


class PrinterProtocol(Protocol):
    """Structural interface for the printer used by :func:`format_and_print_receipt`.

    Decouples the formatting logic from the concrete :class:`JapaneseNetworkPrinter`
    implementation, making it easy to substitute mocks or alternative backends.
    """

    def hw(self, hw: str) -> None: ...
    def set(
        self,
        align: str | None = None,
        font: str | None = None,
        bold: bool | None = None,
        underline: int | None = None,
        width: int | None = None,
        height: int | None = None,
        density: int | None = None,
        invert: bool | None = None,
        smooth: bool | None = None,
        flip: bool | None = None,
        normal_textsize: bool | None = None,
        double_width: bool | None = None,
        double_height: bool | None = None,
        custom_size: bool | None = None,
    ) -> None: ...
    def enable_kanji(self) -> None: ...
    def text_ja(self, text: str) -> None: ...
    def image(self, img_source: str) -> None: ...
    def cut(self) -> None: ...


def get_display_width(text: str) -> int:
    """Calculate display width considering fullwidth/halfwidth characters."""
    width = 0
    for ch in text:
        east_asian = unicodedata.east_asian_width(ch)
        if east_asian in ("F", "W", "A"):
            width += 2
        else:
            width += 1
    return width


def pad_line(left: str, right: str, total_width: int = 42) -> str:
    """Format a two-column line with left and right text aligned."""
    w_left = get_display_width(left)
    w_right = get_display_width(right)
    spaces = max(1, total_width - w_left - w_right)
    return left + (" " * spaces) + right


@dataclass
class ReceiptItem:
    name: str
    count: int
    unit_price_str: str


@dataclass
class ReceiptData:
    order_id: int
    items: Sequence[ReceiptItem]
    total_count: int
    total_price_str: str
    store_name: str = "murchace"
    store_address: str = ""
    logo_path: str = ""
    ordered_at: datetime | None = None


class JapaneseNetworkPrinter(Network):
    """
    Network printer subclass with Epson TM series Japanese Kanji support.
    Uses Shift_JIS (CP932) encoding with Kanji mode enabled.
    """

    def enable_kanji(self) -> None:
        """Enable Kanji (Shift_JIS) mode and Japan international character set on Epson TM series."""
        # Select Japan international character set (maps 0x5C to Yen sign)
        self._raw(ESC_R_JAPAN)
        # Enable Kanji mode and select Shift_JIS code system
        self._raw(FS_AND)
        self._raw(FS_C_SJIS)

    def disable_kanji(self) -> None:
        """Disable Kanji mode."""
        self._raw(FS_DOT)

    def text_ja(self, text: str) -> None:
        """
        Print Japanese text safely using CP932 encoding.
        Bypasses standard python-escpos code page switching.
        Replaces U+00A5 (Yen sign) with '\\' (0x5C) which displays as Yen in Japan char set.

        Calls :meth:`enable_kanji` before each block because intermediate
        :meth:`set` calls may send codepage commands that reset kanji mode.
        """
        self.enable_kanji()
        normalized = text.replace("\u00a5", "\\")
        encoded = normalized.encode("cp932", errors="replace")
        self._raw(encoded)


def format_and_print_receipt(
    printer: PrinterProtocol,
    receipt: ReceiptData,
    paper_width: int = 42,
) -> None:
    """Send formatted receipt commands to the printer."""
    # Reset printer and enable Japanese Kanji mode once for this receipt
    printer.hw("INIT")
    printer.enable_kanji()

    # 1. Store Logo (if configured and file exists)
    if receipt.logo_path:
        try:
            printer.set(align="center")
            printer.image(receipt.logo_path)
            printer.text_ja("\n")
        except (OSError, ValueError) as exc:
            logger.warning(
                "Failed to print logo image '%s': %s", receipt.logo_path, exc
            )

    # 2. Store Name (Center, Bold, Double size)
    printer.set(align="center", bold=True, double_height=True, double_width=True)
    printer.text_ja(f"{receipt.store_name}\n")

    # 3. Store Address (Center, Normal text)
    if receipt.store_address:
        printer.set(align="center", bold=False, normal_textsize=True)
        printer.text_ja(f"{receipt.store_address}\n")

    printer.text_ja("\n")

    # 4. Date and Time (Right aligned)
    now = receipt.ordered_at or datetime.now(UTC).astimezone()
    date_str = now.strftime("%Y-%m-%d %H:%M:%S")
    printer.set(align="right", bold=False, normal_textsize=True)
    printer.text_ja(f"{date_str}\n")

    # 5. Divider
    printer.set(align="left", bold=False, normal_textsize=True)
    printer.text_ja("-" * paper_width + "\n")

    # 6. Items
    for item in receipt.items:
        left_text = item.name
        right_text = f"{item.unit_price_str} x {item.count}"
        line = pad_line(left_text, right_text, total_width=paper_width)
        printer.text_ja(f"{line}\n")

    printer.text_ja("-" * paper_width + "\n")

    # 7. Total Count & Total Price
    total_line = pad_line(
        f"合計 ({receipt.total_count}点)",
        receipt.total_price_str,
        total_width=paper_width,
    )
    printer.set(align="left", bold=True, double_height=True)
    printer.text_ja(f"{total_line}\n")

    # 8. Divider before Order Number
    printer.set(align="left", bold=False, normal_textsize=True)
    printer.text_ja("-" * paper_width + "\n\n")

    # 9. Order Number (Center, Bold, Double size)
    printer.set(align="center", bold=True, double_height=True, double_width=True)
    printer.text_ja(f"注文番号 #{receipt.order_id}\n\n")

    # 10. Cut paper
    printer.cut()
