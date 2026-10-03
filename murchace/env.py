import logging
import os
import sys
from datetime import datetime, tzinfo
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

LOG_LEVEL = os.environ.get("MURCHACE_LOG_LEVEL", "INFO")

logging.basicConfig(
    format=f"%(asctime)s [WORKER:{os.getpid()}:%(name)s:%(levelname)s] %(message)s",
    level=LOG_LEVEL,
    stream=sys.stderr,
)

logger = logging.getLogger(__name__)


def validate_tzname(tzname: str | None) -> tzinfo:
    if tzname:
        try:
            zoneinfo = ZoneInfo(tzname)
            logger.info("The server timezone is set to '%s'", str(zoneinfo))
            return zoneinfo
        except ZoneInfoNotFoundError as e:
            logger.error("'%s' is an invalid IANA zone key: %s", tzname, str(e))
            sys.exit(1)
    else:
        tz = datetime.now().astimezone().tzinfo
        assert tz is not None
        logger.info("The server timezone is set to '%s' (default)", tz.tzname)
        return tz


DEBUG = bool(os.environ.get("MURCHACE_DEBUG"))
IPC_SOCKET_PATH = Path(os.environ.get("IPC_SOCKET_PATH", ".murchace.sock"))
LOCAL_TZINFO: tzinfo = validate_tzname(os.environ.get("MURCHACE_SREVER_TZNAME"))
RECEIPT_PRINTER_HOST = os.environ.get("MURCHACE_RECEIPT_PRINTER_HOST", "")
RECEIPT_PRINTER_PORT = int(os.environ.get("MURCHACE_RECEIPT_PRINTER_PORT", "9100"))
RECEIPT_PRINTER_TIMEOUT = int(os.environ.get("MURCHACE_RECEIPT_PRINTER_TIMEOUT", "10"))
RECEIPT_PAPER_WIDTH = int(os.environ.get("MURCHACE_RECEIPT_PAPER_WIDTH", "34"))
RECEIPT_STORE_NAME = os.environ.get("MURCHACE_RECEIPT_STORE_NAME", "murchace")
RECEIPT_STORE_ADDRESS = os.environ.get("MURCHACE_RECEIPT_STORE_ADDRESS", "")
RECEIPT_LOGO_PATH = os.environ.get("MURCHACE_RECEIPT_LOGO_PATH", "")
