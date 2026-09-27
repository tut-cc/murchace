from enum import Flag, auto

import pytest

from murchace.bc import Broadcaster


@pytest.fixture
def anyio_backend():
    return "asyncio"


class SampleFlag(Flag):
    FLAG_A = auto()
    FLAG_B = auto()
    FLAG_C = auto()


@pytest.mark.anyio
async def test_broadcaster_queue_no_loss():
    bc = Broadcaster[SampleFlag]()
    async with bc.attach_receiver() as rx:
        # Rapid consecutive sends
        bc.send(SampleFlag.FLAG_A)
        bc.send(SampleFlag.FLAG_B)
        bc.send(SampleFlag.FLAG_C)

        first = await rx.recv()
        assert first == SampleFlag.FLAG_A

        drained = rx.drain()
        assert drained == [SampleFlag.FLAG_B, SampleFlag.FLAG_C]

        # Accumulating flags preserves all signals
        accumulated = first
        for item in drained:
            accumulated |= item

        assert accumulated == (
            SampleFlag.FLAG_A | SampleFlag.FLAG_B | SampleFlag.FLAG_C
        )


@pytest.mark.anyio
async def test_broadcaster_receiver_cleanup():
    bc = Broadcaster[int]()
    assert len(bc._receivers) == 0

    async with bc.attach_receiver():
        assert len(bc._receivers) == 1

    assert len(bc._receivers) == 0


@pytest.mark.anyio
async def test_independent_broadcaster_instances():
    bc1 = Broadcaster[str]()
    bc2 = Broadcaster[str]()

    async with bc1.attach_receiver() as rx1, bc2.attach_receiver() as rx2:
        bc1.send("hello")
        msg1 = await rx1.recv()
        assert msg1 == "hello"

        # rx2 should receive nothing from bc1
        assert rx2.drain() == []


@pytest.mark.anyio
async def test_broadcaster_publish_hook():
    import asyncio

    bc = Broadcaster[str]()
    hook_calls: list[str] = []

    async def hook(val: str) -> None:
        hook_calls.append(val)

    bc.set_publish_hook(hook)

    async with bc.attach_receiver() as rx:
        bc.send("event-1")
        assert await rx.recv() == "event-1"
        await asyncio.sleep(0.01)
        assert hook_calls == ["event-1"]


@pytest.mark.anyio
async def test_cross_worker_broadcast_sync(tmp_path):
    import asyncio

    import sqlalchemy
    from databases import Database

    from murchace.store.base import Base
    from murchace.store.broadcast_event import Table as BroadcastEventTable

    db_file = tmp_path / "test.db"
    db = Database(f"sqlite:///{db_file}")
    await db.connect()
    try:
        for table in Base.metadata.tables.values():
            schema = sqlalchemy.schema.CreateTable(table, if_not_exists=True)
            query = str(schema.compile())
            await db.execute(query)

        event_table = BroadcastEventTable(db)

        # Worker 1 broadcaster with SQLite publishing hook
        bc1 = Broadcaster[SampleFlag]()

        async def publish_hook(flag: SampleFlag) -> None:
            await event_table.insert(flag.value)

        bc1.set_publish_hook(publish_hook)

        # Worker 2 broadcaster
        bc2 = Broadcaster[SampleFlag]()

        # Worker 2 poller (simulating a separate worker process with PID 999999)
        stop_poller = asyncio.Event()
        worker2_pid = 999999

        async def worker2_poller():
            last_id = await event_table.get_latest_id()
            while not stop_poller.is_set():
                await asyncio.sleep(0.01)
                events = await event_table.fetch_after(last_id)
                for event in events:
                    last_id = event.id
                    if event.worker_pid != worker2_pid:
                        bc2.send_local(SampleFlag(event.flag))

        poller_task = asyncio.create_task(worker2_poller())

        async with bc1.attach_receiver() as rx1, bc2.attach_receiver() as rx2:
            # Worker 1 sends FLAG_A
            bc1.send(SampleFlag.FLAG_A)

            # Worker 1 receives immediately
            w1_flag = await rx1.recv()
            assert w1_flag == SampleFlag.FLAG_A

            # Worker 2 receives via poller
            w2_flag = await rx2.recv()
            assert w2_flag == SampleFlag.FLAG_A

            # Verify no extra duplicate on Worker 1
            assert rx1.drain() == []

        stop_poller.set()
        await poller_task
    finally:
        await db.disconnect()
