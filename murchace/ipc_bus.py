import asyncio
import fcntl
import fnmatch
import json
import logging
import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from enum import Enum, auto
from typing import Annotated, Any, Self

from datastar_py import ServerSentEventGenerator as SSE
from datastar_py.fastapi import DatastarResponse
from fastapi import APIRouter, Depends, Request
from htpy import div

from .env import IPC_SOCKET_PATH

logger = logging.getLogger(__name__)

WORKER_PID = os.getpid()


class MessageType(Enum):
    SUBSCRIBE = auto()
    UNSUBSCRIBE = auto()
    PUBLISH = auto()


class AsyncIPCBus:
    """
    Pub-sub communication over Unix domain socket

    The IPC bus automatically orchestrates who gets to be a parent worker and
    its client. When a client-only process die, the process gets killed by
    uvicorn and then restarted. Messages published to that worker might get
    lost.

    What is more catastrophic is when a parent process dies. Then all workers
    (hence clients, server, SSE connections, etc.) will get terminated and
    uvicorn will restart all workers. At the moment we do not handle this case
    very well.
    """

    class ParentRegistry:
        def __init__(self, writer: asyncio.StreamWriter):
            self.writer = writer
            self.subscriptions: dict[uuid.UUID, str] = {}

    def __init__(self):
        self.orchestrator_task: asyncio.Task[None] | None = None
        self.parent_server: asyncio.Server | None = None
        self.worker_connections: list[self.ParentRegistry] = []
        self.writer: asyncio.StreamWriter | None = None

        self.local_queues: dict[uuid.UUID, asyncio.Queue] = {}

    async def handle_worker_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        registry = AsyncIPCBus.ParentRegistry(writer)
        self.worker_connections.append(registry)
        try:
            while True:
                raw_payload = await reader.readuntil(b"\x00")
                if raw_payload == b"":
                    break
                else:
                    raw_payload = raw_payload[:-1]  # Remove \x00 separator at the end

                payload = json.loads(raw_payload.decode("utf-8"))
                assert isinstance(payload, dict)
                msg_type = MessageType(payload.get("type"))

                match msg_type:
                    case MessageType.SUBSCRIBE:
                        queue_id = payload["queue_id"]
                        pattern = payload["pattern"]
                        assert isinstance(queue_id, str) and isinstance(pattern, str)
                        registry.subscriptions[uuid.UUID(hex=queue_id)] = pattern
                        logger.info('subscription[%s] = "%s"', queue_id, pattern)
                    case MessageType.UNSUBSCRIBE:
                        queue_id = payload["queue_id"]
                        assert isinstance(queue_id, str)
                        registry.subscriptions.pop(uuid.UUID(hex=queue_id), None)
                        logger.info("delete subscription[%s]", queue_id)
                    case MessageType.PUBLISH:
                        topic = payload.get("topic", "")
                        body = payload.get("body")
                        assert isinstance(topic, str)
                        for reg in self.worker_connections:
                            for queue_id, pattern in reg.subscriptions.items():
                                if match_topic(pattern, topic):
                                    try:
                                        logger.info(
                                            "publish(%s, %s)", queue_id, repr(body)
                                        )
                                        pub_payload = {
                                            "queue_id": queue_id.hex,
                                            "body": body,
                                        }
                                        reg.writer.write(
                                            f"{json.dumps(pub_payload)}\x00".encode()
                                        )
                                        await reg.writer.drain()
                                    except (ConnectionError, RuntimeError):
                                        if reg in self.worker_connections:
                                            self.worker_connections.remove(reg)
        except asyncio.IncompleteReadError:
            pass
        finally:
            if registry in self.worker_connections:
                self.worker_connections.remove(registry)
            writer.close()
            await writer.wait_closed()

    async def orchestrate(self) -> None:
        # Never unlink this file: a worker locking the old inode and another
        # locking a recreated one would both become the parent.
        lock_fd = os.open(IPC_SOCKET_PATH.with_suffix(".lock"), os.O_CREAT | os.O_RDWR)
        try:
            while True:
                try:
                    self.parent_server = None
                    reader, writer = await asyncio.open_unix_connection(IPC_SOCKET_PATH)
                    self.writer = writer
                    logger.info("IPC client connected.")
                except (ConnectionRefusedError, FileNotFoundError):
                    try:
                        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        IPC_SOCKET_PATH.unlink(missing_ok=True)
                        self.parent_server = await asyncio.start_unix_server(
                            self.handle_worker_client, IPC_SOCKET_PATH
                        )
                        logger.info("IPC server started.")
                    except BlockingIOError:
                        # Another worker is becoming the parent. The socket
                        # is theirs, so we must not unlink it.
                        await asyncio.sleep(1)
                        continue

                    reader, writer = await asyncio.open_unix_connection(IPC_SOCKET_PATH)
                    self.writer = writer
                    logger.info("IPC client connected.")
                # except Exception as e:
                #     logger.warning(
                #         "Failed to connect to socket as a client. Retrying after 100ms... (%s)",
                #         repr(e)
                #     )
                #     await asyncio.sleep(0.1)
                #     continue

                while True:
                    raw_payload = await reader.readuntil(b"\x00")
                    if raw_payload == b"":
                        logger.info("IPC server has died. Restarting orchestration.")
                        break
                    else:
                        raw_payload = raw_payload[
                            :-1
                        ]  # Remove \x00 separator at the end
                    payload = json.loads(raw_payload.decode("utf-8"))
                    assert isinstance(payload, dict)
                    queue_id = uuid.UUID(hex=payload["queue_id"])
                    body = payload.get("body")
                    if (queue := self.local_queues.get(queue_id)) is not None:
                        await queue.put(body)
        finally:
            if self.writer is not None:
                self.writer.close()
                await self.writer.wait_closed()
                logger.warning("IPC client disconnected.")
            if self.parent_server is not None:
                self.parent_server.close()
                await self.parent_server.wait_closed()
                IPC_SOCKET_PATH.unlink(missing_ok=True)
                logger.warning("IPC server closed.")
            self.worker_connections.clear()
            os.close(lock_fd)

    def start(self):
        self.orchestrator_task = asyncio.create_task(self.orchestrate())
        self.orchestrator_task.add_done_callback(self.log_orchestrator_failure)

    @staticmethod
    def log_orchestrator_failure(task: asyncio.Task[None]) -> None:
        if not task.cancelled() and (exc := task.exception()) is not None:
            logger.error("IPC orchestration died.", exc_info=exc)

    async def cancel(self):
        if (task := self.orchestrator_task) is not None and not task.done():
            try:
                task.cancel()
                await task
            except asyncio.CancelledError:
                pass
            self.orchestrator_task = None

    @classmethod
    def from_request(cls: type[Self], request: Request) -> Self:
        assert isinstance(request.app.state.ipc_bus, cls)
        return request.app.state.ipc_bus

    async def restart_and_wait(self, timeout: float = 5):
        await self.cancel()
        self.start()
        await asyncio.sleep(timeout)

    async def publish(self, topic: str, body: Any) -> None:
        assert self.writer is not None

        payload = {"type": MessageType.PUBLISH.value, "topic": topic, "body": body}
        if self.writer.is_closing():
            logger.warning(
                "IPC client seems to be closing/closed. Restarting orchestration."
            )
            await self.restart_and_wait()
        self.writer.write(f"{json.dumps(payload)}\x00".encode())
        await self.writer.drain()

    @asynccontextmanager
    async def subscribe(self, pattern: str) -> AsyncIterator[asyncio.Queue]:
        assert self.writer is not None

        queue_id = uuid.uuid4()
        queue = asyncio.Queue()
        self.local_queues[queue_id] = queue

        try:
            sub_signal = {
                "type": MessageType.SUBSCRIBE.value,
                "queue_id": queue_id.hex,
                "pattern": pattern,
            }
            if self.writer.is_closing():
                logger.warning(
                    "IPC client seems to be closing/closed. Restarting orchestration."
                )
                await self.restart_and_wait()
            self.writer.write(f"{json.dumps(sub_signal)}\x00".encode())
            await self.writer.drain()
            yield self.local_queues[queue_id]
        finally:
            self.local_queues.pop(queue_id, None)
            unsub_signal = {
                "type": MessageType.UNSUBSCRIBE.value,
                "queue_id": queue_id.hex,
            }
            if self.writer.is_closing():
                logger.warning(
                    "IPC client seems to be closing/closed. Restarting orchestration."
                )
                await self.restart_and_wait(0)
            else:
                self.writer.write(f"{json.dumps(unsub_signal)}\x00".encode())
                await self.writer.drain()


def match_topic(pattern: str, topic: str) -> bool:
    return False if pattern == "" else fnmatch.fnmatch(topic, pattern)


type IPCDeps = Annotated[AsyncIPCBus, Depends(AsyncIPCBus.from_request)]

router = APIRouter()


@router.post("/ipc")
async def tpub(ipc: IPCDeps, pat: str, msg: str):
    await ipc.publish(pat, msg)
    return "Published successfully"


@router.get("/ipc")
async def tsub(ipc: IPCDeps, pat: str):
    async def event_generator():
        yield SSE.patch_elements(div(id="ipc")[f"sub({pat})"])
        async with ipc.subscribe(pat) as sub:
            while True:
                yield SSE.patch_elements(div(id="ipc")[await sub.get()])

    return DatastarResponse(event_generator())
