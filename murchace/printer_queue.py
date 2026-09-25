import asyncio
import logging

from .env import (
    RECEIPT_PAPER_WIDTH,
    RECEIPT_PRINTER_HOST,
    RECEIPT_PRINTER_PORT,
    RECEIPT_PRINTER_TIMEOUT,
)
from .printer import JapaneseNetworkPrinter, ReceiptData, format_and_print_receipt

logger = logging.getLogger(__name__)

# Seconds to wait before the 2nd, 3rd, … retry attempts (exponential back-off).
# Total attempts = len(_RETRY_DELAYS) + 1
_RETRY_DELAYS: tuple[float, ...] = (3.0, 10.0)


class ReceiptPrinterQueue:
    """
    Asynchronous queue and worker for receipt printing.
    Serializes all print jobs to prevent port 9100 connection collisions.
    Failed jobs are retried up to ``len(_RETRY_DELAYS)`` extra times with
    increasing delays to handle transient network disconnections during busy
    hours.
    """

    def __init__(
        self,
        host: str = RECEIPT_PRINTER_HOST,
        port: int = RECEIPT_PRINTER_PORT,
        timeout: int = RECEIPT_PRINTER_TIMEOUT,
        paper_width: int = RECEIPT_PAPER_WIDTH,
    ):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.paper_width = paper_width
        self.queue: asyncio.Queue[ReceiptData] = asyncio.Queue()
        self._worker_task: asyncio.Task | None = None

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
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("Receipt printer worker stopped")

    async def _worker_loop(self) -> None:
        while True:
            try:
                receipt = await self.queue.get()
            except asyncio.CancelledError:
                break

            try:
                await self._print_with_retry(receipt)
            finally:
                self.queue.task_done()

    async def _print_with_retry(self, receipt: ReceiptData) -> None:
        """Attempt to print with exponential back-off retries.

        Makes up to ``len(_RETRY_DELAYS) + 1`` total attempts.  On each
        failure the worker waits the corresponding delay from *_RETRY_DELAYS*
        before the next attempt, so that a printer that momentarily loses its
        network connection (e.g. during busy-hour TCP resets) has time to
        recover without the job being silently dropped.
        """
        max_attempts = len(_RETRY_DELAYS) + 1
        last_exc: BaseException | None = None

        for attempt, delay in enumerate(
            [0.0, *_RETRY_DELAYS], start=1
        ):
            if delay:
                logger.warning(
                    "Retrying print for order #%d (attempt %d/%d) in %.0f s …",
                    receipt.order_id,
                    attempt,
                    max_attempts,
                    delay,
                )
                await asyncio.sleep(delay)

            try:
                # Run blocking socket I/O off the event loop thread
                await asyncio.to_thread(self._print_job, receipt)
                return  # success — stop retrying
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Print attempt %d/%d failed for order #%d: %s",
                    attempt,
                    max_attempts,
                    receipt.order_id,
                    exc,
                )

        logger.error(
            "All %d print attempts failed for order #%d on %s:%d",
            max_attempts,
            receipt.order_id,
            self.host,
            self.port,
            exc_info=last_exc,
        )

    def _print_job(self, receipt: ReceiptData) -> None:
        logger.info(
            "Connecting to printer %s:%d for order #%d (timeout=%ds) …",
            self.host,
            self.port,
            receipt.order_id,
            self.timeout,
        )
        # Instantiate network printer for this single serialized job
        printer = JapaneseNetworkPrinter(
            host=self.host,
            port=self.port,
            timeout=self.timeout,
        )
        try:
            printer.open(raise_not_found=True)
            format_and_print_receipt(printer, receipt, paper_width=self.paper_width)
            logger.info("Successfully printed receipt for order #%d", receipt.order_id)
        finally:
            printer.close()
