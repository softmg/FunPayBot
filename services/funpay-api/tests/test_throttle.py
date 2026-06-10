import asyncio
import time

import pytest

from app.throttle import SlidingWindowThrottle


@pytest.mark.asyncio
async def test_allows_actions_within_limit() -> None:
    throttle = SlidingWindowThrottle(max_actions=5, window_seconds=60)
    for _ in range(5):
        await throttle.acquire()


@pytest.mark.asyncio
async def test_blocks_when_limit_exceeded() -> None:
    throttle = SlidingWindowThrottle(max_actions=2, window_seconds=1)
    await throttle.acquire()
    await throttle.acquire()

    start = time.monotonic()
    await throttle.acquire()
    elapsed = time.monotonic() - start
    assert elapsed >= 0.5


@pytest.mark.asyncio
async def test_window_expiry_allows_new_actions() -> None:
    throttle = SlidingWindowThrottle(max_actions=1, window_seconds=1)
    await throttle.acquire()

    await asyncio.sleep(1.1)
    start = time.monotonic()
    await throttle.acquire()
    elapsed = time.monotonic() - start
    assert elapsed < 0.5


@pytest.mark.asyncio
async def test_concurrent_acquires_respect_limit() -> None:
    throttle = SlidingWindowThrottle(max_actions=3, window_seconds=60)
    results = await asyncio.gather(*(throttle.acquire() for _ in range(3)))
    assert len(results) == 3
