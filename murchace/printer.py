import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from escpos.printer import Network

# ESC/POS Commands for Japanese (Kanji mode)
# FS & : Select Kanji mode
# FS . : Cancel Kanji mode
# FS C n : Select Kanji code system (0: JIS, 1: Shift_JIS)
FS_AND = b"\x1c\x26"
FS_DOT = b"\x1c\x2e"
FS_C_SJIS = b"\x1c\x43\x01"


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
    ordered_at: datetime | None = None


class JapaneseNetworkPrinter(Network):
    """
    Network printer subclass with Epson TM series Japanese Kanji support.
    Uses Shift_JIS (CP932) encoding with Kanji mode enabled.
    """

    def enable_kanji(self) -> None:
        """Enable Kanji (Shift_JIS) mode on Epson TM series."""
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
        """
        self.enable_kanji()
        encoded = text.encode("cp932", errors="replace")
        self._raw(encoded)


def format_and_print_receipt(
    printer: JapaneseNetworkPrinter,
    receipt: ReceiptData,
    paper_width: int = 42,
) -> None:
    """Send formatted receipt commands to the printer."""
    # Reset printer
    printer.hw("INIT")

    # Header / Store Name
    printer.set(align="center", bold=True, double_height=True, double_width=True)
    printer.text_ja(f"{receipt.store_name}\n")

    # Order Number
    printer.set(align="center", bold=True, double_height=True, double_width=True)
    printer.text_ja(f"\n注文番号 #{receipt.order_id}\n\n")

    # Date and Time
    now = receipt.ordered_at or datetime.now(UTC).astimezone()
    printer.set(align="left", bold=False, normal_textsize=True)
    printer.text_ja(f"{now.strftime('%Y-%m-%d %H:%M:%S')}\n")
    printer.text_ja("-" * paper_width + "\n")

    # Items
    for item in receipt.items:
        left_text = item.name
        right_text = f"{item.unit_price_str} x {item.count}"
        line = pad_line(left_text, right_text, total_width=paper_width)
        printer.text_ja(f"{line}\n")

    printer.text_ja("-" * paper_width + "\n")

    # Total Count & Total Price
    total_line = pad_line(
        f"合計 ({receipt.total_count}点)",
        receipt.total_price_str,
        total_width=paper_width,
    )
    printer.set(align="left", bold=True, double_height=True)
    printer.text_ja(f"{total_line}\n\n")

    # Footer
    printer.set(align="center", bold=False, normal_textsize=True)
    printer.text_ja("ご利用ありがとうございました\n\n\n")

    # Cut paper
    printer.cut()
