import time
from collections import OrderedDict
from dataclasses import dataclass
from uuid import uuid4

# Pending confirmations are short-lived: a manager taps the inline button soon
# after a message is relayed. Bound both age and count so the in-memory store
# cannot grow without limit as messages are polled.
PENDING_TTL_SECONDS = 24 * 60 * 60
MAX_PENDING = 5000


@dataclass(frozen=True)
class PendingCredentials:
    manager_telegram_id: int
    credentials: str
    chat_id: str | None


@dataclass(frozen=True)
class _Entry:
    pending: PendingCredentials
    created_at: float


# Insertion-ordered so the oldest entries are evicted first when over capacity.
_pending_credentials: "OrderedDict[str, _Entry]" = OrderedDict()


def _evict_expired(now: float) -> None:
    expired = [token for token, entry in _pending_credentials.items() if now - entry.created_at > PENDING_TTL_SECONDS]
    for token in expired:
        del _pending_credentials[token]


def create_pending_credentials(manager_telegram_id: int, credentials: str, chat_id: str | None) -> str:
    now = time.monotonic()
    _evict_expired(now)

    token = uuid4().hex
    _pending_credentials[token] = _Entry(
        PendingCredentials(manager_telegram_id, credentials, chat_id),
        now,
    )

    while len(_pending_credentials) > MAX_PENDING:
        _pending_credentials.popitem(last=False)

    return token


def pop_pending_credentials(token: str) -> PendingCredentials | None:
    entry = _pending_credentials.pop(token, None)
    if entry is None:
        return None
    if time.monotonic() - entry.created_at > PENDING_TTL_SECONDS:
        return None
    return entry.pending
