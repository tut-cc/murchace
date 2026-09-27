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
