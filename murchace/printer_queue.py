import asyncio
import logging

from .env import RECEIPT_PRINTER_HOST, RECEIPT_PRINTER_PORT
from .printer import JapaneseNetworkPrinter, ReceiptData, format_and_print_receipt

logger = logging.getLogger(__name__)


class ReceiptPrinterQueue:
    """
    Asynchronous queue and worker for receipt printing.
    Serializes all print jobs to prevent port 9100 connection collisions.
    """

    def __init__(
        self, host: str = RECEIPT_PRINTER_HOST, port: int = RECEIPT_PRINTER_PORT
    ):
        self.host = host
        self.port = port
        self.queue: asyncio.Queue[ReceiptData] = asyncio.Queue()
        self._worker_task: asyncio.Task | None = None
        self._running = False

    @property
    def is_configured(self) -> bool:
        return bool(self.host)

    def enqueue(self, receipt: ReceiptData) -> bool:
        """Enqueue a receipt to be printed. Non-blocking."""
        if not self.is_configured:
            logger.info(
                "Receipt printer host not configured; skipping print job for order #%d",
                receipt.order_id,
            )
            return False

        self.queue.put_nowait(receipt)
        logger.info(
            "Enqueued receipt print job for order #%d (queue size: %d)",
            receipt.order_id,
            self.queue.qsize(),
        )
        return True

    def start(self) -> None:
        """Start the background printing worker."""
        if self._worker_task is None or self._worker_task.done():
            self._running = True
            self._worker_task = asyncio.create_task(self._worker_loop())
            logger.info(
                "Receipt printer worker started (target: %s:%d)", self.host, self.port
            )

    async def stop(self) -> None:
        """Stop worker after draining all pending jobs (up to 10 s timeout)."""
        # Drain the queue before cancelling so no jobs are silently discarded
        try:
            await asyncio.wait_for(self.queue.join(), timeout=10.0)
        except asyncio.TimeoutError:
            logger.warning(
                "Timed out waiting for print queue to drain; %d job(s) may be lost",
                self.queue.qsize(),
            )
        self._running = False
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("Receipt printer worker stopped")

    async def _worker_loop(self) -> None:
        while self._running:
            try:
                receipt = await self.queue.get()
            except asyncio.CancelledError:
                break

            try:
                # Run the blocking socket I/O in a separate thread to keep event loop responsive
                await asyncio.to_thread(self._print_job, receipt)
            except Exception:
                logger.exception(
                    "Failed to print receipt for order #%d on %s:%d",
                    receipt.order_id,
                    self.host,
                    self.port,
                )
            finally:
                self.queue.task_done()

    def _print_job(self, receipt: ReceiptData) -> None:
        logger.info(
            "Connecting to printer %s:%d for order #%d...",
            self.host,
            self.port,
            receipt.order_id,
        )
        # Instantiate network printer for this single serialized job
        printer = JapaneseNetworkPrinter(
            host=self.host,
            port=self.port,
            timeout=10,
        )
        try:
            printer.open(raise_not_found=True)
            format_and_print_receipt(printer, receipt)
            logger.info("Successfully printed receipt for order #%d", receipt.order_id)
        finally:
            printer.close()


# Global singleton instance
printer_queue = ReceiptPrinterQueue()
