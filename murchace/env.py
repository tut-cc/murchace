import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DEBUG = bool(os.environ.get("MURCHACE_DEBUG"))
RECEIPT_PRINTER_HOST = os.environ.get("MURCHACE_RECEIPT_PRINTER_HOST", "")
RECEIPT_PRINTER_PORT = int(os.environ.get("MURCHACE_RECEIPT_PRINTER_PORT", "9100"))
RECEIPT_STORE_NAME = os.environ.get("MURCHACE_RECEIPT_STORE_NAME", "murchace")
DEFAULT_RECEIPT_STORE_ADDRESS = "愛知県豊橋市天伯町字雲雀ヶ丘1-1"
RECEIPT_STORE_ADDRESS = os.environ.get(
    "MURCHACE_RECEIPT_STORE_ADDRESS", DEFAULT_RECEIPT_STORE_ADDRESS
)
DEFAULT_RECEIPT_LOGO_PATH = str(BASE_DIR / "static" / "favicon.ico")
RECEIPT_LOGO_PATH = os.environ.get(
    "MURCHACE_RECEIPT_LOGO_PATH", DEFAULT_RECEIPT_LOGO_PATH
)
