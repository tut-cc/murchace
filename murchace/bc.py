# Best-effort asynchronous broadcast channel

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import ClassVar


# A wrapper class to pass any type of values by reference
@dataclass
class Slot[T]:
    value: T


class Receiver[T]:
    shared: Slot[T]
    modified: asyncio.Event

    def __init__(self, slot: Slot[T], modified: asyncio.Event):
        self.shared = slot
        self.modified = modified

    async def recv(self) -> T:
        await self.modified.wait()
        self.modified.clear()
        return self.shared.value


# A multi-producer multi-consumer channel that can send and receive ephemeral
# messages. The term "ephemeral" means that producers and consumers do not care
# if any previously sent messages are dropped. That means, there is no queuing
# going on in the central broadcaster object.
class Broadcaster[T]:
    shared: Slot[T]
    modified_events: ClassVar[list[asyncio.Event]] = []

    def __init__(self, default: T):
        self.shared = Slot(default)

    def send(self, value: T):
        for modified_event in self.modified_events:
            modified_event.set()
        self.shared.value = value

    @asynccontextmanager
    async def attach_receiver(self) -> AsyncIterator[Receiver[T]]:
        modified = asyncio.Event()
        rx = Receiver(self.shared, modified)
        self.modified_events.append(modified)
        yield rx
        self.modified_events.remove(modified)
