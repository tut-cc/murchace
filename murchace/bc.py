# Best-effort asynchronous broadcast channel

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


class Receiver[T]:
    _queue: asyncio.Queue[T]

    def __init__(self, queue: asyncio.Queue[T]):
        self._queue = queue

    async def recv(self) -> T:
        return await self._queue.get()

    def drain(self) -> list[T]:
        items: list[T] = []
        while not self._queue.empty():
            try:
                items.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        return items


class Broadcaster[T]:
    _receivers: set[Receiver[T]]

    def __init__(self, default: T | None = None):
        self._receivers = set()

    def send(self, value: T) -> None:
        for rx in list(self._receivers):
            rx._queue.put_nowait(value)

    @asynccontextmanager
    async def attach_receiver(self) -> AsyncIterator[Receiver[T]]:
        queue: asyncio.Queue[T] = asyncio.Queue()
        rx = Receiver(queue)
        self._receivers.add(rx)
        try:
            yield rx
        finally:
            self._receivers.discard(rx)
