import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DEBUG = bool(os.environ.get("MURCHACE_DEBUG"))
LOG_LEVEL = os.environ.get("MURCHACE_LOG_LEVEL", "INFO")
IPC_SOCKET_PATH = Path(os.environ.get("IPC_SOCKET_PATH", ".murchace.sock"))
RECEIPT_PRINTER_HOST = os.environ.get("MURCHACE_RECEIPT_PRINTER_HOST", "")
RECEIPT_PRINTER_PORT = int(os.environ.get("MURCHACE_RECEIPT_PRINTER_PORT", "9100"))
RECEIPT_PRINTER_TIMEOUT = int(os.environ.get("MURCHACE_RECEIPT_PRINTER_TIMEOUT", "10"))
RECEIPT_PAPER_WIDTH = int(os.environ.get("MURCHACE_RECEIPT_PAPER_WIDTH", "34"))
RECEIPT_STORE_NAME = os.environ.get("MURCHACE_RECEIPT_STORE_NAME", "murchace")
RECEIPT_STORE_ADDRESS = os.environ.get("MURCHACE_RECEIPT_STORE_ADDRESS", "")
RECEIPT_LOGO_PATH = os.environ.get("MURCHACE_RECEIPT_LOGO_PATH", "")

logging.basicConfig(
    format=f"%(asctime)s [WORKER:{os.getpid()}:%(name)s:%(levelname)s] %(message)s",
    level=LOG_LEVEL,
    stream=sys.stderr,
)
