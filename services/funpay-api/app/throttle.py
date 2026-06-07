import asyncio
import time
from collections import deque


class SlidingWindowThrottle:
    def __init__(self, max_actions: int, window_seconds: int = 60) -> None:
        self.max_actions = max_actions
        self.window_seconds = window_seconds
        self._events: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            self._drop_expired(now)
            if len(self._events) >= self.max_actions:
                wait_for = self.window_seconds - (now - self._events[0])
                if wait_for > 0:
                    await asyncio.sleep(wait_for)
                    now = time.monotonic()
                    self._drop_expired(now)
            self._events.append(now)

    def _drop_expired(self, now: float) -> None:
        while self._events and now - self._events[0] >= self.window_seconds:
            self._events.popleft()

