from dataclasses import dataclass
from uuid import uuid4


@dataclass(frozen=True)
class PendingCredentials:
    manager_telegram_id: int
    credentials: str
    chat_id: str | None


_pending_credentials: dict[str, PendingCredentials] = {}


def create_pending_credentials(manager_telegram_id: int, credentials: str, chat_id: str | None) -> str:
    token = uuid4().hex
    _pending_credentials[token] = PendingCredentials(manager_telegram_id, credentials, chat_id)
    return token


def pop_pending_credentials(token: str) -> PendingCredentials | None:
    return _pending_credentials.pop(token, None)
